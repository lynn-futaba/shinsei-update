"""
データベースファクトリー (DbFactory)
作成者: Lynn
----------------------------------
【役割】
工場内の各システム（WCS, IOT, ATHENA）が持つMySQLデータベースへの「接続窓口」を管理します。

【チームへのメリット】
1. コネクションプールの自動管理: 
   毎回DBにログインし直すのではなく、あらかじめ「接続の予備（プール）」を作っておくことで、
   アクセスの高速化とDBへの負荷軽減を実現しています。
2. 接続先の隠蔽: 
   利用側（Repositoryなど）は、DBのパスワードやホスト名を知る必要はありません。
   `get_connection("DB名")` と呼ぶだけで、適切な接続を取得できます。

【注意点】
- このクラスは「REALモード（本番稼働）」専用です。
- 初期化に失敗するとシステムが起動しません（例外をそのまま上位へ投げます）。
"""

# app/infrastructure/factory/db_factory.py
from mysql.connector import Error
from mysql.connector import pooling
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# DB操作専用のロガーをセットアップ
logger = setup_log(cfg.LOG_FOLDER, cfg.LOG_FILE, cfg.BACKUP_DAYS, logger_name="db_factory")

class DbFactory:
    """
    MySQLコネクションプールを保持・提供するファクトリークラスです。
    インスタンス化される際に、設定ファイル(config.py)を読み込み、4種類のDB接続プールを作成します。
    """

    def __init__(self):
        logger.info("[DbFactory] MySQLプールの初期化を開始します (REALモード)...")
        try:
            # 各システムごとに独立したプールを作成（1つの障害が他へ波及しないように分離）
            self.wcs_pool = pooling.MySQLConnectionPool(pool_name="wcs", **cfg.MYSQL_WCS_DB, pool_size=10, pool_reset_session=True)
            self.iot_pool = pooling.MySQLConnectionPool(pool_name="iot", **cfg.MYSQL_IOTDS_DB)
            self.athena_pool = pooling.MySQLConnectionPool(pool_name="athena", **cfg.MYSQL_ATHENA_DB)
            logger.info("[DbFactory] すべてのMySQLプールが正常に初期化されました。")
        except Error:
            # DBの起動忘れやパスワード間違い、ネットワーク不通時にここを通ります
            logger.exception("[DbFactory] プールの初期化に失敗しました。設定値とDBの状態を確認してください。")
            raise

    def get_connection(self, db_name: str):
        """
        指定されたデータベース名のプールから、空いているコネクション（接続権）を1つ貸し出します。
        
        Args:
            db_name (str): 接続したいデータベースの名前（configで定義された名称）
        Returns:
            MySQLConnection: プールから取得された接続オブジェクト
        Raises:
            ValueError: 定義されていないDB名が指定された場合
        """
        # 各DB名に対応するプールを判定して接続を返す
        if db_name == cfg.MYSQL_WCS_DB["database"]:
            return self.wcs_pool.get_connection()
        elif db_name == cfg.MYSQL_IOTDS_DB["database"]:
            return self.iot_pool.get_connection()
        elif db_name == cfg.MYSQL_ATHENA_DB["database"]:
            return self.athena_pool.get_connection()
        else:
            # プログラムの記述ミス（スペルミスなど）を防ぐためのガード
            raise ValueError(f"No pool configured for database: {db_name}")