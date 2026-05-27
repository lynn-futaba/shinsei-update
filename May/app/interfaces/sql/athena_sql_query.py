"""
Athena データベースクエリ管理 (AthenaSQLQuery)
作成者: Lynn
----------------------------------
【役割】
Athena系テーブル（主にシステムログや例外キャプチャ）へのアクセスを管理するユーティリティです。
DbFactoryから払い出されたコネクションプールを使い、安全かつ効率的にクエリを実行します。

【チームへのメリット】
1. リソース管理の自動化:
   `with self.cursor_ctx()` を使うだけで、接続の取得からプールへの返却までが完結します。
   手動で `conn.close()` を書く必要がなく、接続漏れによるシステムダウンを防ぎます。
2. 防御的なクエリ実行:
   マルチセット（複数の結果を返すSQL）や、未読データのクリーニング処理を内包しており、
   プール内のコネクションを常に「綺麗な状態」で次に回します。
3. 堅牢なエラーハンドリング:
   SQL実行中にエラーが発生した場合、自動的にロールバックを行い、エラー内容をログに詳細に記録します。
"""
from contextlib import contextmanager
from typing import List, Dict, Any

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# Logger setup
logger = setup_log(cfg.LOG_FOLDER, cfg.ATHENA_SQL_QUERY_LOG_FILE, cfg.BACKUP_DAYS, logger_name="athena_sql_query")


class AthenaSQLQuery:
    """
    AthenaDBへのSQL実行をラップし、コンテキストマネージャを提供します。
    """
    
    def __init__(self, db_factory, db_name: str):
        """
        Args:
            db_factory: コネクションプールを管理する DbFactory インスタンス
            db_name: 接続先のデータベース名
        """
        self._db_factory = db_factory
        self._db_name = db_name

    # -------------- コア・コネクションロジック --------------

    def get_connection(self, autocommit: bool = False):
        """
        プールからコネクションを取得し、生存確認（Ping）と設定を行って返します。
        """
        conn = self._db_factory.get_connection(self._db_name)

        # 接続が生きているか確認し、切れていれば再接続を試みる（防御的アプローチ）
        try:
            if hasattr(conn, "is_connected") and not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)
        except Exception:
            pass

        try:
            conn.autocommit = autocommit
        except Exception:
            pass

        return conn

    @contextmanager
    def cursor_ctx(self, dictionary: bool = False):
        """
        【推奨】DB操作のための標準的なコンテキストマネージャ。
        読み取り主体の操作に使用します。
        
        Usage:
            with self.cursor_ctx(dictionary=True) as cur:
                cur.execute("SELECT ...")
                result = cur.fetchall()
        """
        conn = self.get_connection()
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
        except Exception as e:
            # SQL実行失敗時は即座にロールバック
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception(f"[AthenaSQLQuery] SQL Execution error in {self._db_name}")
            raise e
        finally:
            # [重要] コネクションをプールに戻す前に、未処理の結果を完全にクリアする（防御的処理）
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
        書き込み（INSERT/UPDATE/DELETE）用のコンテキストマネージャ。
        処理が成功した場合のみ自動的にコミットを行います。
        """
        conn = self.get_connection()
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
            try:
                conn.commit()
            except Exception:
                logger.exception(f"[AthenaSQLQuery] Commit failed for {self._db_name}")
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

    # -------------- 互換性維持のためのヘルパー --------------

    @property
    def cursor(self):
        """レガシーコード（self.db.cursor.execute...）との互換用"""
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
        """システム起動時のDB疎通確認用"""
        with self.cursor_ctx() as cur:
            cur.execute("SELECT 1")
            _ = cur.fetchall()
        return True

    # ------------------ 業務SQLメソッド ------------------

    def fetch_active_errors_since(self, rms_boot_ts: str) -> List[Dict[str, Any]]:
        """
        指定された時刻（例：RMSの起動時刻）以降に発生した例外データをAthenaから取得します。
        """
        logger.info(f"Athenaから '{rms_boot_ts}' 以降の例外レコードを照会します。")
        query = """
            SELECT 
                id AS athena_id,
                system_code, 
                create_time AS occurrence_time, 
                fault_status, 
                ext3 AS device_id,
                cell_code
            FROM 
                t_monitor_exception_capture
            WHERE 
                create_time > %s
            ORDER BY 
                create_time DESC
        """
        try:
            with self.cursor_ctx(dictionary=True) as cur:
                cur.execute(query, [str(rms_boot_ts)])
                result = cur.fetchall()
                logger.info(f"Athenaからの取得件数: {len(result)} 件")
                return result
        except Exception as e:
            logger.error(f"Athenaクエリ実行失敗: {e}")
            return []