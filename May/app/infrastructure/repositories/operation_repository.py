# app/infrastructure/repositories/operation_repository.py

from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.interfaces.sql.iotds_sql_query import IOTDSSQLQuery

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定 (名前を付ける)
logger = setup_log(
    cfg.LOG_FOLDER, 
    cfg.OPERATION_REPO_LOG_FILE, 
    cfg.BACKUP_DAYS, 
    logger_name="operation_repo"
)

class OperationRepository:
    """
    ライン作業に必要なDBアクセスを提供するリポジトリ
    ・システム状態
    ・ライン状態
    ・セル / コタツ情報
    ・タスク情報
    """

    def __init__(self, w, i):
        # w: WCSSQLQuery, i: IOTDSSQLQuery
        self._sql = w
        self._iotds_sql = i

    # --------------------------
    # システム状態取得
    # --------------------------
    def get_system_status(self):
        sql = self._sql.get_system_status()
        with self._sql.cursor_ctx(dictionary=True) as cur:
            cur.execute(sql)
            return cur.fetchall()
    
    # ------------------------------------------------
    # [WCSDB] t_line_statusのrequest_execution=1 更新
    # ------------------------------------------------
    def update_request_execution(self, line_id):
        sql = self._sql.update_request_execution()
        with self._sql.write_cursor_ctx() as cur:
            cur.execute(sql, (line_id,))
            
    # ---------------------------------------------
    # [iOTDB] t_outputのvalue=1 更新
    # ---------------------------------------------
    def update_output_value(self, line_id):
        sql = self._iotds_sql.update_t_output_value()
        with self._iotds_sql.write_cursor_ctx() as cur:
            cur.execute(sql, (line_id,))
            
    # ---------------------------------------------
    # [WCSDB] t_pallet_statusのcompletion_time=NOW() 更新
    # ---------------------------------------------
    def update_pallet_completion(self, pallet_id):
        sql = self._sql.update_pallet_completion()
        with self._sql.write_cursor_ctx() as cur:
            cur.execute(sql, (pallet_id,))

    # --------------------------
    # ライン状態取得
    # --------------------------
    def get_line_status(self):
        sql = self._sql.get_line_status()
        with self._sql.cursor_ctx(dictionary=True) as cur:
            cur.execute(sql)
            return cur.fetchall()