"""
IoT データソースクエリ管理 (IOTDSSQLQuery)
作成者: Lynn
----------------------------------
【役割】
IoTデバイスやセンサーから収集された稼働データ（IOTDS）へのアクセスを管理します。
デバイスの最新ステータスや実績データの照会・更新を安全に行うための窓口です。

【チームへのメリット】
1. 統一されたアクセスパターン:
   他のSQLQueryクラスとインターフェースを統一しているため、
   どのデータソースを操作する場合も同じ `with cursor_ctx()` の書き方で実装できます。
2. 堅牢なリソース解放:
   IoTデータは件数が多くなりがちですが、`finally` ブロックでの `fetchall()` 漏れ防止策により、
   「Unread result found」エラーでプールが汚染されるのを防ぎます。
3. 自動再試行（Self-heal）:
   ネットワークが不安定になりがちな環境でも、`get_connection` 時の再接続ロジックにより、
   一時的な接続断に対して強い耐性を持っています。
"""
# app/infrastructure/db/iotds_sql_query.py
from contextlib import contextmanager
from typing import List, Dict, Any

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# Logger setup
logger = setup_log(cfg.LOG_FOLDER, cfg.IOTDS_SQL_QUERY_LOG_FILE, cfg.BACKUP_DAYS, logger_name="iotds_sql_query")


class IOTDSSQLQuery:
    def __init__(self, db_factory, db_name: str):
        """
        Initialize with the factory instead of raw credentials to support pooling.
        """
        self._db_factory = db_factory
        self._db_name = db_name

    # -------------- Core Connection Logic --------------

    def get_connection(self, autocommit: bool = False):
        """
        Provides the 'get_connection' attribute required by repositories.
        Returns a connection directly from the pool manager.
        """
        conn = self._db_factory.get_connection(self._db_name)

        # Ensure connection is alive if driver supports it
        try:
            if hasattr(conn, "is_connected") and not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)
        except Exception:
            pass

        # Best-effort autocommit
        try:
            conn.autocommit = autocommit
        except Exception:
            pass

        return conn

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
            logger.exception(f"[IOTDSSQLQuery] SQL Execution error in {self._db_name}")
            raise e
        finally:
            # Drain any unread result / multi-sets to avoid "Unread result found"
            try:
                if getattr(cur, "with_rows", False):
                    try:
                        cur.fetchall()
                    except Exception:
                        pass
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

    @contextmanager
    def write_cursor_ctx(self, dictionary: bool = False):
        """
        Use this for single-statement writes that should be auto-committed on success.
        """
        conn = self.get_connection()
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
            try:
                conn.commit()
            except Exception:
                logger.exception(f"[IOTDSSQLQuery] Commit failed for {self._db_name}")
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
        """No-op: Managed by connection object or context managers."""
        pass

    def rollback(self):
        """No-op: Managed by connection object or context managers."""
        pass

    def ping(self):
        """Connectivity check used by app_factory."""
        with self.cursor_ctx() as cur:
            cur.execute("SELECT 1")
            _ = cur.fetchall()
        return True

    # -------------- SQL String Definitions --------------

    def t_input_select_all(self) -> str:
        return "SELECT * FROM t_input"

    # -------------- SQL method --------------

    def fetch_t_input(self) -> List[Dict[str, Any]]:
        """
        Standardized way to execute and fetch using the pool context.
        """
        sql = self.t_input_select_all()
        with self.cursor_ctx(dictionary=True) as cur:
            cur.execute(sql)
            return cur.fetchall()
    
    # --- t_line_status を取得 ---
    def t_line_status_select(self):
        return """
            SELECT line_id, request_flag, request_time, updated_date
            FROM t_line_status
        """

    # --- t_pallet_status を取得 ---
    def t_pallet_status_select(self):
        return """
            SELECT pallet_id, status, completion_time, input_time, updated_date
            FROM t_pallet_status
        """

    # --- t_input へ挿入（後でカラム変更してもここだけ直せばOK） ---
    def t_input_insert(self):
        return """
            INSERT INTO t_input (signal_id, controller, item, array, value, comment)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                value = VALUES(value),
                comment = VALUES(comment)
        """

    # --- t_pallet_status.input_time を NULL にする ---
    def t_pallet_status_clear_input_time(self):
        return """
            UPDATE t_pallet_status
            SET input_time = NULL
            WHERE pallet_id = %s
        """
        
    # --- t_output.value を 1 にする ---
    def update_t_output_value(self):
        return """
            UPDATE t_output
            SET value = 1
            WHERE signal_id = %s
        """
        
    