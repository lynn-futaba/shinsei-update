"""
管理者リポジトリ (ManageRepository)
作成者: Lynn
----------------------------------
【役割】
工場全体の稼働状態の監視、およびRMS（ロボット管理システム）の動作モードを制御する
システム管理の中心的データアクセス層です。

【チームへのメリット】
1. システム一括制御: 
   ロボットの「準備・開始・停止」といったフェーズ管理をメソッド一つで安全に実行できます。
2. 複数ソースの統合: 
   LocalのMySQLデータとAthenaのエラー情報を統合し、管理画面に一元化した情報を提供します。
3. インターロックの保護: 
   ラインごとの搬送許可（トグル操作）を、レコードの有無にかかわらず「INSERT or UPDATE」ロジックで
   確実に制御し、システムのデッドロックを防ぎます。
4. データのクレンジング: 
   `upsert_rms_error` のように、アクティブなエラーのみを残し、解消済みエラーを自動削除する
   メンテナンス機能も内包しています。
"""

# app/infrastructure/repositories/manage_repository.py
from __future__ import annotations
from typing import Iterable, Dict, List
from mysql.connector.cursor import MySQLCursorDict

from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.infrastructure.factory.domain_factory import ManageFactory
from app.domain.entities import LiftEntrance, Maguchi, TransportTask, RMSCurrentMode, ErrorListItem

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定 (名前を付ける)
logger = setup_log(cfg.LOG_FOLDER, cfg.MANAGE_REPO_LOG_FILE, cfg.BACKUP_DAYS, logger_name="manage_repo")

class ManageRepository(ManageFactory):
    """
    ManageRepository extends ManageFactory.
    db:          your pooled DB factory for WCS (local MySQL)
    wcs_sql:     WCSSQLQuery instance (existing)
    db_name:     WCS DB name (e.g., futaba_ok2_shippment)
    athena_sql_query: instance of AthenaSQLQuery (internal Athena)
    """

    def __init__(self, db, wcs_sql: WCSSQLQuery, db_name: str = "futaba_ok2_shippment"):
        """
        Args:
            db: DbFactoryインスタンス（コネクション取得用）
            wcs_sql: WCS向けSQLクエリビルダ
        """
        super().__init__(db=db, db_name=db_name)
        self._manage_factory = ManageFactory  # for static method mapping
        self._db = db
        self._db_name = db_name
        self._sql = wcs_sql
        logger.info("[ManageRepository] initialized", extra={"db_name": db_name})

    # ---------- ライン状態 ----------
    def get_line_state_list(self) -> Iterable[Maguchi]:
        sql = self._sql.t_line_station_select_all() # m_location, t_kotatsu_status, t_pallet_status, m_line
        conn = self._db.get_connection(self._db_name)
        try:
            cur: MySQLCursorDict = conn.cursor(dictionary=True)
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            return [self._manage_factory.get_line_state_list(r) for r in rows]
        finally:
            conn.close()
            
    # ---------- エラ一覧表状態 ----------
    def get_error_list(self):
        """
        Local MySQLとAthenaの両方からエラー情報を収集し、分類して返します。
        管理画面の「エラー一覧」パネルで使用されます。
        """
        sql_local = self._sql.m_error_select_local()
        sql_athena = self._sql.m_error_select_athena()
        
        conn = self._db.get_connection(self._db_name)
        try:
            cur = conn.cursor(dictionary=True)
            
            # Local取得
            cur.execute(sql_local)
            rows_local = cur.fetchall()
            local_data = [self._manage_factory.get_error_list(r) for r in rows_local]
            
            # Athena取得
            cur.execute(sql_athena)
            rows_athena = cur.fetchall()
            athena_data = [self._manage_factory.get_error_list(r) for r in rows_athena]
            
            cur.close()
            
            # 辞書形式で返す
            return {
                "local": local_data,   # List of ErrorListItem objects
                "athena": athena_data  # List of ErrorListItem objects
            }
        finally:
            conn.close()
            
    
    def resolve_rms_error(self, athena_id: int):
        sql = self._sql.t_rms_error_resolve()
        conn = self._db.get_connection(self._db_name)

        try:
            cur = conn.cursor()
            cur.execute(sql, (athena_id,))
            # if cur.rowcount == 0:
            #    raise ValueError(f"RMS error not found: athena_id={athena_id}")
            conn.commit()
        finally:
            conn.close()


    def resolve_wcs_error(self, error_num: str):
        sql = self._sql.t_error_log_resolve()
        conn = self._db.get_connection(self._db_name)
        try:
            cur = conn.cursor()
            cur.execute(sql, (error_num,))
            conn.commit()
        finally:
            conn.close()

    
    # ---------- システム制御: インターロック (搬送許可) ----------
    def toggle_transport_permission(self, line_id: int) -> bool:
        """
        指定ラインの搬送許可(0:禁止 / 1:許可)を反転させます。
        レコードが存在しない場合は「許可(1)」状態で新規作成します。
        """
        conn = self._db.get_connection(self._db_name)
        try:
            with conn.cursor() as cur:
                # 1) 既存レコードの値を反転（1→0, 0→1）
                cur.execute(self._sql.m_system_interlock_toggle_by_line_id(), (line_id,))
                updated = cur.rowcount

                # 2) 行が存在しなかった場合はONで新規作成
                if updated == 0:
                    cur.execute(self._sql.m_system_interlock_insert_on_by_line_id(), (line_id,))

            conn.commit()

            # 3) Read back the current value
            cur2: MySQLCursorDict = conn.cursor(dictionary=True)
            cur2.execute(self._sql.m_system_interlock_select_by_line_id(), (line_id,))
            row = cur2.fetchone()
            cur2.close()

            if not row or "transport_permission" not in row:
                # Extremely unlikely here, but keep a clear error
                raise KeyError(f"line_id not found after toggle: {line_id}")

            return bool(int(row["transport_permission"]))

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_task_status(self, minutes=10, limit=10, page=1) -> Iterable[TransportTask]:
        offset = (page - 1) * limit
        sql = self._sql.t_callback_task_status_select_all()

        conn = self._db.get_connection(self._db_name)
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, (minutes, limit, offset))
            rows = cur.fetchall()
            return [self._manage_factory.get_task_status(r) for r in rows]
        finally:
            cur.close()
            conn.close()

    # --------- リフト間口画面 ----------
    # def get_lift_entrance(self) -> Iterable[LiftEntrance]:
    #     """
    #     Get lift station list and map to LiftEntrance.
    #     """
    #     sql = self._sql.t_lift_station_select_all()
    #     conn = self._db.get_connection(self._db_name)
    #     try:
    #         cur: MySQLCursorDict = conn.cursor(dictionary=True)
    #         cur.execute(sql)
    #         rows = cur.fetchall()
            
    #         logger.info(f"[ManageRepository] get_lift_entrance: {rows}")
    #         cur.close()
    #         return [self._manage_factory.get_lift_entrance(r) for r in rows]
    #     finally:
    #         conn.close()
    
    # --------- リフト間口画面 ----------
    def get_lift_entrance(self) -> Iterable[LiftEntrance]:
        sql = self._sql.t_lift_station_select_all()
        conn = self._db.get_connection(self._db_name)

        try:
            cur: MySQLCursorDict = conn.cursor(dictionary=True)
            cur.execute(sql)
            rows = cur.fetchall()

            for row in rows:
                pallet_id = row.get("pallet_id")

                if not pallet_id:
                    continue

                pallet_name = None

                # =========================
                # ✅ 1. Check supply_pairs FIRST (CRITICAL)
                # =========================
                cur.execute("""
                    SELECT p.pallet_type, m.pallet_name
                    FROM t_pallet_supply_pairs p
                    JOIN m_pallet m ON p.pallet_type = m.pallet_type
                    WHERE p.line_id = (
                        SELECT mp.line_id
                        FROM m_pallet mp
                        JOIN t_pallet_status ts 
                            ON mp.pallet_type = ts.pallet_type
                        WHERE ts.pallet_id = %s
                        LIMIT 1
                    )
                    AND p.pair_index = 0
                    LIMIT 1
                """, (pallet_id,))
                supply_row = cur.fetchone()

                if supply_row:
                    # ✅ THIS IS YOUR KANBAN SOURCE
                    pallet_name = supply_row["pallet_name"]

                else:
                    # =========================
                    # ✅ 2. fallback to normal pallet
                    # =========================
                    cur.execute("""
                        SELECT m.pallet_name
                        FROM t_pallet_status t
                        JOIN m_pallet m 
                            ON t.pallet_type = m.pallet_type
                        WHERE t.pallet_id = %s
                        LIMIT 1
                    """, (pallet_id,))
                    normal_row = cur.fetchone()

                    if normal_row:
                        pallet_name = normal_row["pallet_name"]

                # =========================
                # ✅ 3. Apply to UI
                # =========================
                if pallet_name:
                    row["pallet_name"] = pallet_name

            logger.info(f"[ManageRepository] get_lift_entrance: {rows}")

            cur.close()
            return [self._manage_factory.get_lift_entrance(r) for r in rows]

        finally:
            conn.close()

    # --- RMS MODE: SELECT ---
    def get_rms_current_mode(self) -> Iterable[RMSCurrentMode]:
        sql = self._sql.m_system_status_select_all()
        conn = self._db.get_connection(self._db_name)
        try:
            cur: MySQLCursorDict = conn.cursor(dictionary=True)
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            return [self._manage_factory.get_rms_current_mode(r) for r in rows]
        finally:
            conn.close()

    # --- RMS MODE: SET (1=auto / 0=indv) ---
    def rms_set_mode(self, mode: int) -> bool:
        conn = self._db.get_connection(self._db_name)
        try:
            with conn.cursor() as cur:
                cur.execute(self._sql.m_system_status_update_mode(), (int(mode),))
            conn.commit()

            # Read back to confirm
            cur2: MySQLCursorDict = conn.cursor(dictionary=True)
            cur2.execute(self._sql.m_system_status_get_mode())
            row = cur2.fetchone()
            cur2.close()
            if not row or "mode" not in row:
                raise KeyError("mode not found after update")
            return bool(int(row["mode"]))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- RMS Auto steps (SQL-backed) ---
    def _fetch_one_rms(self) -> RMSCurrentMode:
        """Helper: read back one row and map to entity"""
        conn = self._db.get_connection(self._db_name)
        try:
            cur: MySQLCursorDict = conn.cursor(dictionary=True)
            cur.execute(self._sql.m_system_status_get_one())
            row = cur.fetchone()
            cur.close()
        finally:
            conn.close()

        if not row:
            raise KeyError("m_system_status is empty")
        return self._manage_factory.get_rms_current_mode(row)

    # ---------- RMS 自動運転フェーズ制御 ----------
    def rms_auto_prepare(self) -> RMSCurrentMode:
        """RMSを『準備状態』へ遷移させます。"""
        conn = self._db.get_connection(self._db_name)
        try:
            with conn.cursor() as cur:
                cur.execute(self._sql.m_system_status_set_prepare())
            conn.commit()

            cur2: MySQLCursorDict = conn.cursor(dictionary=True)
            cur2.execute(self._sql.m_system_status_get_one())
            row = cur2.fetchone()
            cur2.close()
            if not row:
                raise KeyError("m_system_status is empty after prepare")
            return self._manage_factory.get_rms_current_mode(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def rms_auto_start(self) -> RMSCurrentMode:
        """RMSを『開始状態』へ遷移させます。"""
        conn = self._db.get_connection(self._db_name)
        try:
            with conn.cursor() as cur:
                cur.execute(self._sql.m_system_status_set_start())
            conn.commit()

            cur2: MySQLCursorDict = conn.cursor(dictionary=True)
            cur2.execute(self._sql.m_system_status_get_one())
            row = cur2.fetchone()
            cur2.close()
            if not row:
                raise KeyError("m_system_status is empty after start")
            return self._manage_factory.get_rms_current_mode(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def rms_auto_run(self) -> RMSCurrentMode:
        conn = self._db.get_connection(self._db_name)
        try:
            with conn.cursor() as cur:
                cur.execute(self._sql.m_system_status_set_running())
            conn.commit()

            cur2: MySQLCursorDict = conn.cursor(dictionary=True)
            cur2.execute(self._sql.m_system_status_get_one())
            row = cur2.fetchone()
            cur2.close()
            if not row:
                raise KeyError("m_system_status is empty after run")
            return self._manage_factory.get_rms_current_mode(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def upsert_rms_error(self, data):
        """
        Athenaから届いたエラー情報をLocal DBへ同期します。
        
        - 状態が '0' (Active) の場合: Local DBへ保存（既にあれば更新）。
        - 状態が '0' 以外の場合: 解決済みとみなし、管理画面を汚さないようLocal DBから削除します。
        """
        athena_id = data.get('athena_id')
        fault_status = str(data.get('fault_status', ''))

        # 1. Decision Logic: Only "0" is an active error we want to show
        if fault_status != "0":
            # If the error is now resolved (status != 0), remove it from our display table
            sql_delete = "DELETE FROM t_rms_error WHERE athena_id = %s"
            try:
                with self._db.write_cursor_ctx() as cur:
                    cur.execute(sql_delete, (athena_id,))
                # logger.debug(f"Removed resolved error {athena_id} from local DB")
                return True
            except Exception as e:
                logger.error(f"MYSQL DELETE ERROR for ID {athena_id}: {e}")
                return False

        sql_upsert = """
            INSERT INTO t_rms_error (
                athena_id, 
                system_code, 
                occurrence_time, 
                fault_status, 
                device_id, 
                cell_code
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                fault_status = VALUES(fault_status),
                occurrence_time = VALUES(occurrence_time),
                updated_at = CURRENT_TIMESTAMP
        """

        try:
            with self._db.write_cursor_ctx() as cur:
                cur.execute(sql_upsert, (
                    athena_id,
                    data.get('system_code'),
                    data.get('occurrence_time'),
                    fault_status,
                    data.get('device_id'),
                    data.get('cell_code')
                ))
            return True
        except Exception as e:
            logger.error(f"MYSQL UPSERT ERROR for ID {athena_id}: {e}")
            return False