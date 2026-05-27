"""
IoT データソースリポジトリ管理 (IOTDSRepository)
作成者: Lynn
----------------------------------
【役割】
IoTDS（IoT DataShare）関連のDB操作を一元管理するリポジトリクラス。
PLC信号のミラーテーブル（t_input / t_output）および
業務状態テーブル（t_pallet_status）への更新処理を担当する。

【設計方針】
・m_signal_list を「信号定義の唯一の正解」として扱う
・t_input / t_output は PLC のビット状態を反映するだけのテーブル
・業務イベント（FILL / 完了）は t_pallet_status のみで管理する
・value=0（PLCリセット）は業務ロジックでは扱わない

【責務の分離】
・信号の意味解釈：Service層
・DB更新処理：Repository層
・SQL実装詳細：SQLQuery層

【チームへのメリット】
1. 業務ロジックとPLCロジックの明確な分離:
   PLC信号のON/OFFと業務状態を切り離すことで、
   誤った巻き戻しや副作用を防止できる。
2. 冪等性の担保:
   同じ信号が複数回検知されても業務状態が壊れない設計。
3. 保守性の向上:
   信号追加・変更時は m_signal_list を更新するだけで対応可能。
"""
# app/infrastructure/repositories/iotds_repository.py
from app.interfaces.sql.iotds_sql_query import IOTDSSQLQuery
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ使用
logger = setup_log(
    cfg.LOG_FOLDER,
    cfg.IOTDS_REPO_LOG_FILE,
    cfg.BACKUP_DAYS,
    logger_name="iotds_repo"
)

class IOTDSRepository:
    def __init__(self, wcs_sql: WCSSQLQuery, iotds_sql: IOTDSSQLQuery):
        self._wcs_sql = wcs_sql
        self._iotsql = iotds_sql

    # -------------------- SIGNAL DEFINITIONS --------------------

    def get_signal_input_definitions(self):    
        """
        m_signal_list は「信号の意味」を定義するマスタ
        ・どの signal_id が
        ・どの plat_no に対応し
        ・input / output のどちらで
        ・START / ACCEPTED 等、何を意味するか
        を判定するための唯一の正解データ
        """

        with self._wcs_sql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT signal_id, plat_no, signal_class, signal_type
                FROM m_signal_list WHERE signal_class = "input"
            """)
            return cur.fetchall()
        
    def get_signal_output_definitions(self):    
        """
        m_signal_list は「信号の意味」を定義するマスタ
        ・どの signal_id が
        ・どの plat_no に対応し
        ・input / output のどちらで
        ・START / ACCEPTED 等、何を意味するか
        を判定するための唯一の正解データ
        """

        with self._wcs_sql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT signal_id, plat_no, signal_class, signal_type
                FROM m_signal_list WHERE signal_class = "output"
            """)
            return cur.fetchall()

    
    # -------------------- PLC SIGNAL MIRROR --------------------
    
    def set_input_signal(self, signal_id: int): 
        """ Updates t_input (Machine -> PLC) """
        with self._iotsql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_input
                SET value = 1
                WHERE signal_id = %s
            """, (signal_id,))

    def set_output_signal(self, signal_id: int):
        """ Updates t_output (PLC -> Machine) """
        with self._iotsql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_output
                SET value = 1
                WHERE signal_id = %s
            """, (signal_id,))
            
    def update_request_flag(self, request_flag: int, line_id: int):
        """
        update request_flag by line_id
        """
        with self._wcs_sql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_line_status
                SET
                    request_flag = %s
                WHERE line_id = %s
            """, (request_flag, line_id))
    
    # -------------------- BUSINESS STATE --------------------
    # ここからが「業務データ」
    # PLC信号を受けて t_pallet_status を更新する
    def update_pallet_fill(self, pallet_id: int):
        """
        INPUT START 検知時の処理
        ・パレットを FILL 状態に変更
        ・input_time を現在時刻でセット
        ・すでに FILL の場合は更新しない（冪等性）
        """
        with self._wcs_sql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_pallet_status
                SET
                    status = 'FILL',
                    input_time = NOW()
                WHERE pallet_id = %s
            """, (pallet_id,))
    
    # -------------------- PLC MIRROR READ --------------------
    def get_input_signals(self):
        """
        PLC INPUT ミラーの現在値を取得
        signal_id ごとの value(0/1) を返す
        """
        with self._iotsql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT SQL_NO_CACHE signal_id, value
                FROM t_input
            """)
            return cur.fetchall()

    def get_output_signals(self):
        """
        PLC OUTPUT ミラーの現在値を取得
        signal_id ごとの value(0/1) を返す
        """
        with self._iotsql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT signal_id, value
                FROM t_output
            """)
            return cur.fetchall()
        
    # -------------------- PALLET RESOLUTION --------------------
    def get_pallet_id_by_plat_no(self, plat_no: int) -> int | None:
        """
        plat_no から pallet_id を解決する
        t_line_station → pallet_id → t_pallet_status の前提
        """
        with self._wcs_sql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT pallet_id, line_id
                FROM t_line_station
                WHERE plat_no = %s
            """, (plat_no,))
            row = cur.fetchone()
            return row["pallet_id"], row["line_id"]
        
    def select_carry_pattern(self, line_id):
        with self._wcs_sql.cursor_ctx(dictionary=True) as cur:
            cur.execute("""
                SELECT carry_pattern
                FROM m_line
                WHERE line_id = %s
            """, (line_id,))

            row = cur.fetchone()

            if not row:
                return None

            # ✅ Defensive access (works for dict or tuple)
            if isinstance(row, dict):
                return row.get("carry_pattern")

            # tuple fallback
            return row[0]
        
    def update_t_output_value(self, signal_id: int):
        with self._iotsql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_output
                SET
                    value = 1,
                    update_datetime = NOW()
                WHERE signal_id = %s
            """, (signal_id,))
            
    def update_request_execution(self, line_id):
        with self._wcs_sql.write_cursor_ctx() as cur:
            cur.execute("""
            UPDATE t_line_status
                SET
                    request_execution = 1
                WHERE line_id = %s
            """, (line_id,))
            
    def update_pallet_completion(self, pallet_id):
        with self._wcs_sql.write_cursor_ctx() as cur:
            cur.execute("""
            UPDATE t_pallet_status
            SET completion_time = NOW()
            WHERE pallet_id = %s
        """, (pallet_id,))
    
    def update_permition(self, permition: int, line_id: int):
        """
        update permition by line_id
        """
        with self._wcs_sql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_line_status
                SET permition = %s
                WHERE line_id = %s
            """, (permition, line_id))
    
    def reset_t_output_value(self, signal_id: int):
        with self._iotsql.write_cursor_ctx() as cur:
            cur.execute("""
                UPDATE t_output
                SET value = 0
                WHERE signal_id = %s
            """, (signal_id,))
        
