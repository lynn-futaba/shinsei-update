"""
WCS データベースクエリ管理 (WCSSQLQuery)
作成者: Lynn
----------------------------------
【役割】
WCS（倉庫制御システム）の全データベース操作を一手に引き受けるデータアクセス層です。
ライン状態、タスク管理、リフト操作、パレット供給管理など、現場の動きに直結するクエリを管理します。

【チームへのメリット】
1. データの整合性（楽観的ロック）:
   `ps_bump_status_rev_cas` 等の実装により、「他の誰かが更新していたら書き込まない」
   という排他制御をDBレベルで保証します。
2. 複雑なビジネスロジックのSQL化:
   リフト間口の名称からラインID（T63-65）を判定するロジックなどをSQL側に集約。
   アプリケーション側のコードをシンプルに保ちます。
3. リソースの自動洗浄:
   `cursor_ctx` 内の徹底した Drain 処理により、高頻度な更新が発生する WCS 環境でも
   「Unread result found」による接続エラーを根絶します。
"""
from contextlib import contextmanager
from typing import Any, Dict
import json

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# Logger setup
logger = setup_log(cfg.LOG_FOLDER, cfg.WCS_SQL_QUERY_LOG_FILE, cfg.BACKUP_DAYS, logger_name="wcs_sql_query")


class WCSSQLQuery:
    def __init__(self, db_factory, db_name: str):
        """
        Initialize with the factory instead of raw credentials to support pooling.
        """
        self._db_factory = db_factory
        self._db_name = db_name

    # -------------- DB接続ロジック --------------

    def get_connection(self, autocommit: bool = False):
        """
        Provides the 'get_connection' attribute required by repositories.
        Returns a connection directly from the pool manager.
        """
        conn = self._db_factory.get_connection(self._db_name)

        # Ensure connection is alive
        try:
            if hasattr(conn, "is_connected") and not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)
        except Exception:
            # Some drivers don't expose is_connected; ignore
            pass

        # Best effort autocommit
        try:
            conn.autocommit = autocommit
        except Exception:
            pass

        return conn

    # 読み込む
    @contextmanager
    def cursor_ctx(self, dictionary: bool = False):
        """
        The primary way to interact with the DB safely.
        Borrows a connection from the pool and returns it automatically.
        """
        conn = self.get_connection()
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception(f"[WCSSQLQuery] SQL Execution error in {self._db_name}")
            raise e
        finally:
            # Attempt to drain unread results to avoid "Unread result found"
            try:
                if getattr(cur, "with_rows", False):
                    try:
                        cur.fetchall()
                    except Exception:
                        pass
                # Drain any remaining multi-result sets if supported
                if hasattr(cur, "nextset"):
                    while True:
                        try:
                            more = cur.nextset()
                        except Exception:
                            break
                        if not more:
                            break
                        try:
                            if getattr(cur, "with_rows", False):
                                cur.fetchall()
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()  # Return to pool
            except Exception:
                pass

    # 書き込む
    @contextmanager
    def write_cursor_ctx(self, dictionary: bool = False):
        """
        Use this for single-statement writes that should be auto-committed on success.
        Leaves the original cursor_ctx unchanged for backwards compatibility.
        """
        conn = self.get_connection()  # autocommit is False by default
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
            try:
                conn.commit()
            except Exception:
                logger.exception(f"[WCSSQLQuery] Commit failed for {self._db_name}")
                raise
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    # -------------- Legacy Support Helpers --------------

    @property
    def cursor(self):
        """Helper for legacy code accessing self.db.cursor.execute(...)"""
        return self.get_connection().cursor()

    @property
    def dict_cursor(self):
        """Helper for legacy code accessing self.db.dict_cursor.execute(...)"""
        return self.get_connection().cursor(dictionary=True)

    def commit(self):
        """No-op: Managed by connection object or cursor_ctx."""
        pass

    def rollback(self):
        """No-op: Managed by connection object or cursor_ctx."""
        pass

    def ping(self):
        """Connectivity check used by app_factory."""
        with self.cursor_ctx() as cur:
            cur.execute("SELECT 1")
            _ = cur.fetchall()
        return True

    # ------------------ SQL Methods ------------------ #

    # ---------------------------#
    # エラー表示 ⇒ SQL クエリ     #
    # ---------------------------#
    def m_error_select_local(self) -> str:
        return """
            SELECT
                IFNULL(T.error_num, 0) AS error_num,
                M.error_code,
                M.error_summary,
                IFNULL(T.error_datetime, NOW()) AS error_datetime,
                M.error_level,
                'LOCAL' AS error_category,
                IFNULL(T.is_completed, 0) AS is_completed
            FROM t_error_log T
            LEFT JOIN m_error M
                ON M.error_code = T.error_code
            WHERE (T.is_completed = 0 OR T.is_completed IS NULL)
            ORDER BY T.error_datetime DESC;
        """
    
    def m_error_select_athena(self) -> str:
        # return """
        #     SELECT
        #         athena_id AS error_num,
        #         system_code AS error_code,
        #         'Exception' AS error_summary,
        #         occurrence_time AS error_datetime,
        #         'High' AS error_level,
        #         'RMS_ATHENA' AS error_category,
        #         0 AS is_completed
        #     FROM t_rms_error
        #     WHERE fault_status = 0 AND is_completed = 0
        #     ORDER BY occurrence_time DESC
        # """
        return """
            SELECT
                TRE.athena_id AS error_num,
                ME.error_code,
                ME.error_summary,
                TRE.occurrence_time AS error_datetime,
                ME.error_level,
                ME.error_category,
                ME.error_description,
                ME.error_operation,
                0 AS is_completed

            FROM t_rms_error TRE

            LEFT JOIN m_error ME
                ON ME.rms_error_code = TRE.system_code

            WHERE
                TRE.fault_status = 0
                AND TRE.is_completed = 0

            ORDER BY
                TRE.occurrence_time DESC;
        """
    
    def t_rms_error_resolve(self) -> str:
        return """
            UPDATE t_rms_error
            SET is_completed = 1,
                updated_at = NOW()
            WHERE athena_id = %s
        """

    def t_error_log_resolve(self) -> str:
        return """
            UPDATE t_error_log
            SET is_completed = 1,
                updated_date = NOW()
            WHERE error_num = %s
        """

    # ---------------------------#
    # ライン状態　表示 ⇒ SQL クエリ #
    # ---------------------------#
    def t_line_station_select_all(self) -> str:
        # return """
        #     SELECT
        #         ML.line_id,
        #         ML.line_name,
        #         MSI.transport_permission,

        #         CASE
        #             WHEN MLO.cell_type = 'input' THEN 1
        #             WHEN MLO.cell_type = 'wait'  THEN 2
        #             # ELSE NULL
        #         END AS maguchi_no,

        #         MP.pallet_name

        #     FROM m_line ML

        #     LEFT JOIN m_system_interlock MSI
        #         ON MSI.line_id = ML.line_id

        #     LEFT JOIN t_line_station TLS
        #         ON TLS.line_id = ML.line_id
        #     AND TLS.plat_no BETWEEN 60 AND 63

        #     LEFT JOIN m_location MLO
        #         ON MLO.plat_no = TLS.plat_no
        #     AND MLO.cell_type IN ("input", "wait")
            
        #     LEFT JOIN t_kotatsu_status
        #         ON TKS.loaded_pallet_id = TLS.pallet_id

        #     LEFT JOIN t_pallet_status TPS
        #         ON TKS.loaded_pallet_id = TPS.pallet_id

        #     LEFT JOIN m_pallet MP
        #         ON TPS.pallet_type = MP.pallet_type

        #     ORDER BY
        #         ML.line_name,
        #         maguchi_no;

        # """
        return """
            SELECT
                ML.line_id,
                ML.line_name,
                MSI.transport_permission,

                CASE
                    WHEN MLO.cell_type = 'input' THEN 1
                    WHEN MLO.cell_type = 'wait'  THEN 2
                END AS maguchi_no,

                MP.pallet_name

            FROM m_line ML

            LEFT JOIN m_system_interlock MSI
                ON MSI.line_id = ML.line_id

            LEFT JOIN m_location MLO
                ON MLO.plat_no = ML.plat_no
            AND MLO.cell_type IN ('input', 'wait')

            LEFT JOIN t_kotatsu_status TKS
                ON TKS.cell_code = MLO.cell_code

            LEFT JOIN t_pallet_status TPS
                ON TPS.pallet_id = TKS.loaded_pallet_id

            LEFT JOIN m_pallet MP
                ON MP.pallet_type = TPS.pallet_type

            ORDER BY
                ML.line_name,
                maguchi_no;
        """

    # -----------------------------------------------------#
    # --- ライン状態搬送許可　⇒ SQL クエリ　m_system_interlock ---#
    # -----------------------------------------------------#
    def m_system_interlock_toggle_by_line_id(self) -> str:
        return (
            "UPDATE m_system_interlock "
            "   SET transport_permission = CASE WHEN transport_permission = 1 THEN 0 ELSE 1 END "
            " WHERE line_id = %s"
        )

    def m_system_interlock_insert_on_by_line_id(self) -> str:
        return "INSERT INTO m_system_interlock (line_id, transport_permission) VALUES (%s, 1)"

    def m_system_interlock_select_by_line_id(self) -> str:
        return (
            "SELECT CAST(transport_permission AS UNSIGNED) AS transport_permission "
            "FROM m_system_interlock WHERE line_id=%s LIMIT 1"
        )

    # -----------------------------------------------------#
    # --- ステータス表示　⇒ SQL t_callback_task_status ---#
    # -----------------------------------------------------#
    def t_callback_task_status_select_all(self) -> str:
        return """
                SELECT
                    task_id,
                    status,
                    phase,
                    robot_id,
                    dest_cell,
                    task_type,
                    instruction,
                    updated_date
                FROM t_callback_task_status
                WHERE updated_date >= UTC_TIMESTAMP() - INTERVAL %s MINUTE
                ORDER BY updated_date DESC
                LIMIT %s OFFSET %s
            """

            
    # -------------------------------------------#
    # --- リフト間口操作画面表示　⇒ SQL クエリ --- #
    # -------------------------------------------#
    # -------------------------------------------#
    # --- リフト間口操作画面表示　⇒ SQL クエリ --- #
    # -------------------------------------------#
    def t_lift_station_select_all(self) -> str:
        return """
            SELECT
                MLS.maguchi_name,
                ML.line_name,
                MP.pallet_name,
                MLS.plat_no,
                MLS.seq_no,
                TLS.pallet_id,
                TLS.transport_status

            FROM t_lift_station TLS

            LEFT JOIN m_lift_station MLS
                ON MLS.plat_no = TLS.plat_no
            AND MLS.seq_no  = TLS.seq_no

            LEFT JOIN t_pallet_status TPS
                ON TLS.pallet_id = TPS.pallet_id

            LEFT JOIN m_pallet MP
                ON TPS.pallet_type = MP.pallet_type

            LEFT JOIN m_line ML
                ON ML.line_id = MP.line_id

            ORDER BY
                MLS.plat_no ASC,
                MLS.seq_no ASC;
            """

    def t_lift_station_lock_status_by_pk(self) -> str:
        return (
            "SELECT transport_status "
            "FROM t_lift_station "
            "WHERE plat_no = %s AND seq_no = %s "
            "FOR UPDATE"
        )

    def t_lift_station_update_status_by_pk(self) -> str:
        return (
            "UPDATE t_lift_station "
            "SET transport_status = %s, pallet_id = %s, updated_date = NOW() "
            "WHERE plat_no = %s AND seq_no = %s"
        )
    
    def update_t_lift_station_pallet_id(self) -> str:
        return "UPDATE t_lift_station SET pallet_id = %s WHERE plat_no = %s AND seq_no = %s"

    def t_lift_station_select_one_by_pk(self) -> str:
        return """
            SELECT
                MLS.maguchi_name,
                ML.line_name,
                IFNULL(MP.pallet_name, '') AS pallet_name,
                TLS.pallet_id,
                TLS.transport_status,
                MLS.seq_no,
                MLS.plat_no
                
            FROM t_lift_station TLS
            JOIN m_lift_station MLS
            ON MLS.plat_no = TLS.plat_no
            AND MLS.seq_no  = TLS.seq_no
            
            LEFT JOIN t_pallet_status TPS
            ON TLS.pallet_id = TPS.pallet_id
            LEFT JOIN m_pallet MP
            ON TPS.pallet_type = MP.pallet_type
            
            LEFT JOIN t_line_station TLT
            ON TLS.pallet_id = TLT.pallet_id
            LEFT JOIN m_line ML
            ON TLT.line_id = ML.line_id
            
            WHERE TLS.plat_no = %s
            AND TLS.seq_no  = %s
            LIMIT 1
        """
    
    def m_location_select_cell_by_pk(self) -> str:
        return """
            SELECT ML.cell_code, TL.kotatsu_id, TKS.loaded_pallet_id AS pallet_id
            FROM m_location ML
            LEFT JOIN t_location TL
            ON ML.cell_code = TL.cell_code
            LEFT JOIN t_kotatsu_status TKS
            ON TL.kotatsu_id = TKS.kotatsu_id
            WHERE plat_no = %s AND seq_no = %s
            GROUP BY ML.cell_code
        """

    def t_kotatsu_select_by_cell(self) -> str:
        return (
            "SELECT kotatsu_id, loaded_pallet_id "
            "FROM t_kotatsu_status "
            "WHERE cell_code = %s"
        )

    def t_kotatsu_update_loaded_pallet(self) -> str:
        return (
            "UPDATE t_kotatsu_status "
            "SET loaded_pallet_id = %s, updated_date = NOW() "
            "WHERE kotatsu_id = %s"
        )
        
    def t_pallet_status_update(self) -> str:
        return (
            "UPDATE t_pallet_status SET status = %s WHERE pallet_id = %s"
        )
    
    def t_kotatsu_status_update(self) -> str:
        return (
            "UPDATE t_kotatsu_status SET booking = 0 WHERE kotatsu_id = %s"
        )
    
    def t_pallet_status_select(self) -> str:
        return (
            "SELECT m1.line_id, t1.pallet_type FROM t_pallet_status t1 LEFT JOIN m_pallet m1 ON t1.pallet_type = m1.pallet_type WHERE pallet_id = %s LIMIT 1"
        )
    
    def m_pallet_select(self) -> str:
        return """
            SELECT t2.line_id, t2.pallet_type, t2.count
            FROM m_pallet m1
            LEFT JOIN t_pallet_status t1 ON m1.pallet_type = t1.pallet_type
            LEFT JOIN t_pallet_supply_pairs t2 ON m1.line_id = t2.line_id
            WHERE t1.pallet_id = %s AND t2.pair_index = 0 AND t2.line_id = (
                SELECT line_id
                FROM m_pallet
                LEFT JOIN t_pallet_status t3 ON m_pallet.pallet_type = t3.pallet_type
                WHERE pallet_id = %s
                GROUP BY line_id
            ) LIMIT 1
        """
        
    def t_pallet_supply_pairs(self) -> str:
        return (
            "SELECT psp.id AS pair_id, psp.line_id FROM t_pallet_supply_pairs psp WHERE psp.pallet_type = %s AND psp.line_id = %s ORDER BY psp.pair_index LIMIT 1"
        )
    
    def select_pair_index(self) -> str:
        return (
            "SELECT pair_index FROM t_pallet_supply_pairs WHERE id = %s AND line_id = %s"
        )
        
    def ps_decrease_pair_count_if_positive(self) -> str:
        """
        Decrease count by 1 only if count > 0
        Returns affected rows = 1 if decremented, 0 if already 0 or not found
        """
        return """
            UPDATE t_pallet_supply_pairs
            SET count = count - 1
            WHERE line_id = %s
            AND pallet_type = %s
            AND pair_index = 0
            AND count > 0
            LIMIT 1
        """


    # -----------------------------------------------------#
    # --- RMSモード表示　⇒ SQL クエリ　m_system_status -----#
    # -----------------------------------------------------#
    def m_system_status_select_all(self) -> str:
        return (
            "SELECT system_id, system_name, mode, preparation_ok, auto_running FROM m_system_status ORDER BY system_id"
        )

    def m_system_status_update_mode(self) -> str:
        return "UPDATE m_system_status SET mode=%s, preparation_ok=0, auto_running=0"

    def m_system_status_get_mode(self) -> str:
        return "SELECT mode FROM m_system_status LIMIT 1"

    def m_system_status_set_prepare(self) -> str:
        return "UPDATE m_system_status SET mode=1, preparation_ok=1, auto_running=0"

    def m_system_status_set_start(self) -> str:
        return "UPDATE m_system_status SET mode=1, preparation_ok=1, auto_running=1"

    def m_system_status_set_running(self) -> str:
        return "UPDATE m_system_status SET mode=1, preparation_ok=1, auto_running=1"

    def m_system_status_get_one(self) -> str:
        """
        Returns one row from m_system_status with consistent columns for mapping.
        CAST is used so repositories can safely bool(int(...)).
        """
        return (
            "SELECT "
            "  system_id, "
            "  system_name, "
            "  CAST(mode AS UNSIGNED) AS mode, "
            "  CAST(preparation_ok AS UNSIGNED) AS preparation_ok, "
            "  CAST(auto_running AS UNSIGNED) AS auto_running "
            "FROM m_system_status "
            "LIMIT 1"
        )

    # -----------------------------------------------------#
    # --- RMSコールバック　⇒ SQL クエリ　m_system_status -----#
    # -----------------------------------------------------#
    def insert_task_event_json(self, *, task_id: str, request_id: str, event_json: Dict[str, Any], ts: int) -> None:
        sql = """
            INSERT INTO t_callback_task_events
                (task_id, request_id, event_json, created_date)
            VALUES
                (%s, %s, CAST(%s AS JSON), FROM_UNIXTIME(%s))
            ON DUPLICATE KEY UPDATE
                updated_date = NOW()
        """
        payload = json.dumps(event_json, ensure_ascii=False, separators=(",", ":"))
        with self.write_cursor_ctx() as cur:
            cur.execute(sql, (task_id, request_id, payload, ts))

    def upsert_task_status(self, *, task_id: str, status: str, phase: str,
                           robot_id: str, dest_cell: str, ts: int,
                           task_type: str = "", instruction: str = "") -> None:
        sql = """
        INSERT INTO t_callback_task_status
            (task_id, status, phase, robot_id, dest_cell, task_type, instruction, updated_date)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s))
        ON DUPLICATE KEY UPDATE
            status      = VALUES(status),
            phase       = VALUES(phase),
            robot_id    = VALUES(robot_id),
            dest_cell   = VALUES(dest_cell),
            task_type   = VALUES(task_type),
            instruction = VALUES(instruction),
            updated_date= VALUES(updated_date)
        """
        args = (task_id, status, phase, robot_id, dest_cell, task_type, instruction, ts)
        with self.write_cursor_ctx() as cur:
            cur.execute(sql, args)
      
    # -------------------------------------#
    # --- 供給パレット　⇒ SQL クエリ　 -----#
    # -------------------------------------#
    # --- Master Data ---
    def ps_get_all_master_pallets(self) -> str:
        return """
            SELECT pallet_type, pallet_name, versatility, kotatsu_type
            FROM m_pallet WHERE pallet_type NOT IN (0, 10, 20, 30)
            ORDER BY pallet_name ASC
        """

    # --- Read Queries ---
    def ps_get_all_lines(self) -> str:
        return """
            SELECT
                l.line_id,
                l.line_name
            FROM m_line l
            ORDER BY l.line_id
        """
    
    def ps_get_line_by_id(self) -> str:
        return """
            SELECT
                l.line_id,
                l.line_name
            FROM m_line l
            WHERE l.line_id = %s
            LIMIT 1
        """

    def ps_get_pairs_by_line(self) -> str:
        # (kept) — Optionally include updated_date if you want to expose it
        return """
            SELECT
                p.id,
                p.pair_index,
                p.pallet_type,
                COALESCE(m.pallet_name, '') AS pallet_name,
                p.count
            FROM t_pallet_supply_pairs p
            LEFT JOIN m_pallet m ON p.pallet_type = m.pallet_type
            WHERE p.line_id = %s
            ORDER BY p.pair_index ASC
        """
    
    def ps_update_pair(self) -> str:
        return """
            UPDATE t_pallet_supply_pairs
            SET pallet_type = %s, count = %s, updated_date = NOW()
            WHERE id = %s
        """

    def ps_insert_pair(self) -> str:
        return """
            INSERT INTO t_pallet_supply_pairs (line_id, pair_index, pallet_type, count)
            VALUES (%s, %s, %s, %s)
        """

    def ps_delete_pair(self) -> str:
        return """
            DELETE FROM t_pallet_supply_pairs
            WHERE id = %s
        """
    
    def ps_shift_pairs_up(self) -> str:
        return """
            UPDATE t_pallet_supply_pairs
            SET pair_index = pair_index + 1
            WHERE line_id = %s AND pair_index >= %s
        """

    def ps_shift_pairs_down(self) -> str:
        return """
            UPDATE t_pallet_supply_pairs
            SET pair_index = pair_index - 1
            WHERE line_id = %s AND pair_index > %s
        """
            
    def ps_check_pallet_type_exists(self) -> str:
        # Optional: data integrity for writes
        return "SELECT 1 FROM m_pallet WHERE pallet_type = %s LIMIT 1"
    
    # -------------------------------------#
    # --- RMS初期化サービス　⇒ SQL クエリ　 -----#
    # -------------------------------------#
    
    # 自動搬送開始時のRMS情報をDBに保存するクエリ
    def clear_t_location(self) -> str:
        return """
            UPDATE t_location SET
            transport_permission = 0, kotatsu_id = NULL, has_reservation = 0
        """
    
    def clear_t_kotatsu_status(self):
        # t_kotatsu_statusテーブルの情報をクリアするクエリ
        return """
            UPDATE t_kotatsu_status
            SET cell_code = NULL, booking = 0
        """
    
    def get_t_location(self):
        # t_locationテーブルの情報を取得するクエリ
        return """
            SELECT * FROM t_location
        """
    
    def update_t_location(self):
        # t_locationテーブルの情報を更新するクエリ
        return """
            UPDATE t_location SET kotatsu_id = %s
            WHERE cell_code = %s
        """
        
    def update_t_kotatsu_status(self):
        # t_kotatsu_statusテーブルの情報を更新するクエリ
        return """
            UPDATE t_kotatsu_status SET cell_code = %s
            WHERE kotatsu_id = %s
        """
        
    def clear_t_robot(self):
        """
        t_robot テーブルの情報を初期化するクエリ
        """
        return """
            UPDATE t_robot SET
                task_id = NULL,
                current_cell_position = 0,
                operation_status = '',
                loaded_kotatsu_id = 0
        """
    
    def update_t_robot_from_rms(self):
        """
        RMS Robot 情報を t_robot に登録／更新するクエリ
        """
        return """
            INSERT INTO t_robot (
                id,
                task_id,
                current_cell_position,
                operation_status,
                loaded_kotatsu_id
            ) VALUES (%s, NULL, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                current_cell_position = VALUES(current_cell_position),
                operation_status       = VALUES(operation_status),
                loaded_kotatsu_id      = VALUES(loaded_kotatsu_id)
        """

    # ============================================================
    # initialization_service で使用するクエリ
    # ============================================================
    def get_t_lift_station(self):
        """
        t_lift_station テーブルの情報を取得するクエリ
        """
        return """
            SELECT 
                tls.plat_no,
                tls.seq_no,
                ml.cell_code,
                tls.pallet_id,
                tls.transport_status,
                tks.kotatsu_id
            FROM m_location as ml
            LEFT JOIN t_lift_station as tls
            ON tls.plat_no = ml.plat_no AND tls.seq_no = ml.seq_no
            LEFT JOIN t_kotatsu_status as tks
            ON tls.pallet_id = tks.loaded_pallet_id
            WHERE ml.cell_type = "complete"
        """
    def get_t_kotatsu_status(self):
        """
        t_kotatsu_status テーブルの情報を取得するクエリ
        """
        return """
            SELECT *
            FROM t_kotatsu_status
        """

    def updata_t_lift_station_status(self):
        """
        t_lift_station テーブルの情報を更新するクエリ
        """
        return """
            UPDATE t_lift_station
            SET pallet_id = %s, transport_status = %s
            WHERE plat_no = %s AND seq_no = %s
        """
    
    # ============================================================
    # Operation RMS API 用 SQL
    # ============================================================

    def op_system_status_select(self) -> str:
        return """
            SELECT system_id, system_name, mode, preparation_ok, auto_running
            FROM m_system_status
        """

    def op_line_status_select(self) -> str:
        return """
            SELECT line_id, transport_permission
            FROM m_system_interlock
        """
    
    def op_get_kotatsu_status(self) -> str:
        """完成品搬送に使えるコタツのみ取得"""
        return """
            SELECT
                ks.kotatsu_id        AS kotatsu_id,
                ks.loaded_pallet_id AS loaded_pallet_id,
                tl.cell_code        AS cell_code,
                ml.cell_type        AS cell_type
            FROM
                t_kotatsu_status AS ks
            JOIN
                t_location AS tl
                ON ks.kotatsu_id = tl.kotatsu_id
            JOIN
                m_location AS ml
                ON tl.cell_code = ml.cell_code
            WHERE
                ml.cell_type = 'complete'
                AND ks.loaded_pallet_id IS NOT NULL
                AND tl.has_reservation = 0
                AND (ks.booking IS NULL OR ks.booking = 0)
        """

        
    def op_get_pallet_status(self):
        """パレットの状態を取得するクエリ"""
        return """
            SELECT
            t1.pallet_id            AS pallet_id,
            t1.pallet_type          AS pallet_type,
            t1.status               AS status,
            t1.input_time           AS input_time,
            t1.completion_time      AS completion_time,
            t2.kanban_angle         AS kanban_angle
            FROM
                t_pallet_status AS t1
            LEFT JOIN
                m_pallet AS t2
                ON t1.pallet_type = t2.pallet_type
        """

    def op_update_cell(self) -> str:
        return """
            UPDATE t_location
            SET transport_permission = %s, kotatsu_id=%s, has_reservation=%s
            WHERE cell_code=%s
        """

    def op_update_kotatsu(self) -> str:
        return """
            UPDATE t_kotatsu_status
            SET cell_code=%s, loaded_pallet_id=%s, booking=%s
            WHERE kotatsu_id=%s
        """

    def op_update_lift_station(self) -> str:
        return """
            UPDATE t_lift_station
            SET pallet_id=%s,
                transport_status=%s
            WHERE plat_no=%s AND seq_no=%s
        """
        
    def op_get_operation(self):
        return """
            SELECT  
                SQL_NO_CACHE
                t1.request_flag,
                t1.request_time,
                t6.pallet_id,
                t7.kanban_angle
                FROM
                    t_line_status as t1
                LEFT JOIN
                    t_line_station as t2
                    ON t1.line_id = t2.line_id
                LEFT JOIN
                    m_location as t3
                    ON t2.plat_no = t3.plat_no
                LEFT JOIN
                    t_location as t4
                    ON t3.cell_code = t4.cell_code
                LEFT JOIN
                    t_kotatsu_status as t5
                    ON t4.kotatsu_id = t5.kotatsu_id
                LEFT JOIN
                    t_pallet_status as t6
                    ON t5.loaded_pallet_id = t6.pallet_id
                LEFT JOIN
                    m_pallet as t7
                    ON t6.pallet_type = t7.pallet_type
                WHERE
                    t1.line_id=%s AND
                    t3.cell_type = "input" AND
                    t1.request_flag = 1
                ORDER BY
                    t1.request_time DESC
        """
    
    def op_update_complete_pallet(self):
        return """
            UPDATE t_pallet_status
            SET status='FILL',
                completion_time=%s
            WHERE pallet_id=%s
        """

    def op_request_reset(self):
        return """
            UPDATE t_line_status
            SET request_flag=%s, permition=%s, request_execution=%s
            WHERE line_id=%s
        """

    def op_request_receive(self):
        return """
            UPDATE t_line_status
            SET request_execution=%s
            WHERE line_id=%s
        """

    def op_request(self):
        return """
            SELECT SQL_NO_CACHE
                request_flag
            FROM t_line_status
            WHERE line_id = %s
        """

    def op_get_empty_cells(self):
        """ラインの情報からセルの情報を取得するクエリ"""
        return """
            SELECT
                t2.cell_code          AS cell_code,
                t2.cell_type          AS cell_type,
                t2.angle              AS angle,
                t3.kotatsu_id         AS kotatsu_id,
                t3.has_reservation    AS has_reservation
            FROM
                t_line_station t1
            LEFT JOIN
                m_location t2
                ON t1.distination_plat = t2.plat_no
            LEFT JOIN
                t_location t3
                ON t2.cell_code = t3.cell_code
            WHERE
                t1.line_id = %s
                AND t3.has_reservation = 0
            GROUP BY
                t2.cell_code
        """
    
    # 作業に必要な情報を取得するクエリ
    def op_get_line_cells(self) -> str:
        return """
            SELECT
                t2.cell_code          AS cell_code,
                t2.cell_type          AS cell_type,
                t2.angle              AS angle,
                t3.kotatsu_id         AS kotatsu_id,
                t3.has_reservation    AS has_reservation
            FROM
                t_line_station t1
            LEFT JOIN
                m_location t2
                ON t1.plat_no = t2.plat_no
            LEFT JOIN
                t_location t3
                ON t2.cell_code = t3.cell_code
            WHERE
                t1.line_id = %s
            GROUP BY
                t2.cell_code
        """
        
    def op_get_kotatsu_status2(self):
        return """
            SELECT *
            FROM t_kotatsu_status t5
            LEFT JOIN t_pallet_status t6 ON t5.loaded_pallet_id = t6.pallet_id
            LEFT JOIN m_pallet t7 ON t6.pallet_type = t7.pallet_type
            LEFT JOIN m_kotatsu t8 ON t5.kotatsu_id = t8.kotatsu_id
            GROUP BY t5.kotatsu_id
        """
    
    def op_clear_lift_station(self):
        """リフト間口の情報更新(フラグONの場合はクリア)"""
        return """
            UPDATE t_lift_station
            SET pallet_id=NULL,
                transport_status='WAIT'
            WHERE (plat_no, seq_no) IN (
                SELECT plat_no, seq_no FROM m_location WHERE cell_code=%s
            )
        """
        
    def op_set_lift_station_pallet(self):
        return """
            UPDATE t_lift_station
            SET pallet_id = (
                SELECT loaded_pallet_id
                FROM t_kotatsu_status
                WHERE kotatsu_id=%s
            ),
            transport_status='READY'
            WHERE (plat_no, seq_no) IN (
                SELECT plat_no, seq_no FROM m_location WHERE cell_code=%s
            )
        """
         
    def op_get_lift_pallet_status(self):
        """パレットの状態を取得するクエリ"""
        return """
            SELECT SQL_NO_CACHE
                t1.pallet_id        AS pallet_id,
                t2.cell_code        AS cell_code
            FROM
                t_lift_station AS t1
            LEFT JOIN
                m_location AS t2
                ON t1.plat_no = t2.plat_no
            AND t1.seq_no = t2.seq_no
            LEFT JOIN
                t_pallet_status AS t3
                ON t1.pallet_id = t3.pallet_id
            LEFT JOIN
                m_pallet AS t4
                ON t3.pallet_type = t4.pallet_type
            WHERE
                t1.transport_status = 'COMP'
                AND t3.status = 'EMPTY'
                AND t4.line_id = %s
            ORDER BY
                t3.input_time ASC
        """
      
    def op_get_task_status(self):
        """
        タスクの状態を取得するクエリ
        """
        return """
            SELECT
                task_id,
                task_type,
                status,
                instruction,
                phase,
                robot_id,
                dest_cell
            FROM
                t_callback_task_status
            WHERE
                task_id = %s
        """
        
    def get_op_task_status(self):
        """タスクの状態を取得するクエリ"""
        return """
            SELECT SQL_NO_CACHE
                *
            FROM
                t_callback_task_status
            WHERE
                task_id = %s
        """
        
    def op_task_exists(self):
        return """
            SELECT COUNT(*) AS cnt
            FROM t_task
            WHERE task_id = %s
        """

    def op_insert_task(self):
        return """
            INSERT INTO t_task (
                task_id,
                robot_id,
                status,
                end_cell,
                task_phase
            )
            VALUES (%s, %s, %s, %s, %s)
        """

    def op_update_task(self):
        return """
            UPDATE t_task
            SET
                robot_id = %s,
                status = %s,
                end_cell = %s,
                task_phase = %s
            WHERE task_id = %s
        """

    # t_line_stationにパレットIDを保存するクエリ
    def line_status(self):
        return """
            UPDATE t_line_station
            SET pallet_id = %s
            WHERE line_id = %s
        """

    # t_pallet_statusにライン供給時間を設定するクエリ
    def pallet_time_set(self, slot):
        if slot not in ["supply_time", "input_time", "completion_time"]:
            slot = "updated_date"
        return f"""
            UPDATE t_pallet_status
            SET {slot} = now()
            WHERE pallet_id = %s
        """

    # ============================================================
    # Operation Repository 用 SQL
    # ============================================================
    # --------------------------
    # システム状態取得
    # --------------------------
    def get_system_status(self):
        return """
            SELECT SQL_NO_CACHE
            system_id, system_name, mode, preparation_ok, auto_running
            FROM m_system_status
        """
    
    def update_request_execution(self):
        return """
            UPDATE t_line_status
                SET
                    request_execution = 1
                WHERE line_id = %s
        """
    
    def update_pallet_completion(self):   
        return """
            UPDATE t_pallet_status
            SET completion_time = NOW()
            WHERE pallet_id = %s
        """
        
    # --------------------------
    # ライン状態取得
    # --------------------------
    def get_line_status(self):
        return """
            SELECT
                msi.line_id AS line_id,
                msi.transport_permission AS transport_permission,
                ml.carry_pattern AS carry_pattern,
                tls.request_flag AS request_flag,
                tls.request_execution AS execution
            FROM m_system_interlock msi
            LEFT JOIN m_line ml
                ON msi.line_id = ml.line_id
            LEFT JOIN t_line_status tls
                ON msi.line_id = tls.line_id
            GROUP BY msi.line_id
        """
        
    # --------------------------
    # request_flag = 0
    # --------------------------
    def reset_request_flag(self):
        return """
            UPDATE t_line_status
                SET request_flag = %s
                WHERE line_id = %s
            """

    # --------------------------
    # ラインのパレットの更新
    # --------------------------
    def update_line_pallet(self):
        return """
            UPDATE t_line_station
            SET pallet_id = %s
            WHERE line_id = %s
        """

    def update_t_pallet_status_pallet_id(self):
        return """
            UPDATE t_pallet_status SET pallet_type = %s WHERE pallet_id = %s
        """
        
    # ================================================================
    # t_line_status の permission_flag 取得
    # ================================================================
    def select_permition(self):
        return """
            SELECT permition
            FROM t_line_status
            WHERE line_id = %s
        """

    # ================================================================
    # t_line_status の permission_flag 取得
    # ================================================================
    def get_reservation(self):
        return """
            SELECT has_reservation
            FROM t_location
            WHERE cell_code = %s
        """
