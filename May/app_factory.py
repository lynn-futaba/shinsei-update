"""
アプリケーションファクトリー (create_app)
作成者: Lynn
--------------------------------------
Flaskアプリケーションの初期化と依存関係の注入（DI）を行う中心的なファイル。

主な処理フロー:
1. 設定の読み込み: config.py から環境設定を取得。
2. DB初期化: DbFactory を使用して各データベースの接続プールを作成。
3. SQLクライアント生成: 各DB（WCS, IOT, Athena）専用のクエリ操作クラスを生成し、疎通確認（ping）を実施。
4. サービスコンテナ構築: ビジネスロジックをまとめた container を作成。
5. ルーティング登録: 各コントローラー（Admin, Worker等）をBlueprintとして登録。
"""
import threading
from typing import Tuple
from flask import Flask

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

from app.infrastructure.factory.db_factory import DbFactory
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.interfaces.sql.iotds_sql_query import IOTDSSQLQuery
from app.interfaces.sql.athena_sql_query import AthenaSQLQuery

from app.services.operation_ni_service import OperationNiService
from app.services.operation_service import OperationService
from app.services.services_container import build_container

# Operation APScheduler setup  (自動搬送処理を1秒ごとに実行する)
from apscheduler.schedulers.background import BackgroundScheduler
from app.controller_runner.run_controll import RunControll

from app.infrastructure.repositories.operation_repository import OperationRepository


# Logger setup
logger = setup_log(cfg.LOG_FOLDER, cfg.LOG_FILE, cfg.BACKUP_DAYS, logger_name="app_factory")


def _build_sql_clients(db_factory: DbFactory) -> Tuple[WCSSQLQuery, IOTDSSQLQuery, AthenaSQLQuery]:
    """
    Constructs the specialized query handlers using a shared DbFactory.
    Always uses REAL database names and performs connectivity pings.
    """
    wcs_name = cfg.MYSQL_WCS_DB["database"]
    iot_name = cfg.MYSQL_IOTDS_DB["database"]
    athena_name = cfg.MYSQL_ATHENA_DB["database"]

    logger.info(
        "[_build_sql_clients] Instantiating SQL clients (wcs=%s, iot=%s, athena=%s)",
        wcs_name, iot_name, athena_name
    )

    wcs = WCSSQLQuery(db_factory=db_factory, db_name=wcs_name)
    iot_ds = IOTDSSQLQuery(db_factory=db_factory, db_name=iot_name)
    athena = AthenaSQLQuery(db_factory=db_factory, db_name=athena_name)

    # Connectivity check (always)
    logger.info("[_build_sql_clients] Performing connectivity pings...")
    wcs.ping();     logger.info("[_build_sql_clients] WCS ping OK")
    iot_ds.ping();  logger.info("[_build_sql_clients] IOT DS ping OK")
    athena.ping();  logger.info("[_build_sql_clients] Athena ping OK")

    return wcs, iot_ds, athena


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="app/static",
        template_folder="app/templates",
        static_url_path="/static",
    )

    # Initialize Logging
    setup_log(cfg.LOG_FOLDER, cfg.LOG_FILE, cfg.BACKUP_DAYS)
    logger.info("[create_app] Starting application")

    # 1) Initialize the shared Pool Manager (always REAL)
    db_factory = DbFactory()

    # 2) Build SQL clients (+ ping)
    wcs, iot_ds, athena = _build_sql_clients(db_factory)

    # 3) Build Services Container
    container = build_container(
        wcs=wcs,
        iot_ds=iot_ds,
        athena=athena,
        default_db_name=cfg.MYSQL_WCS_DB["database"],
    )
    app.extensions["container"] = container
    
    run = RunControll(wcs, iot_ds)
    run_controller = threading.Thread(target=run.run_cycle, daemon=True)
    run_controller.start()
    
    # 4) Register Blueprints
    from app.controllers.admin_controller import create_admin_blueprint
    from app.controllers.worker_controller import create_worker_blueprint

    app.register_blueprint(create_admin_blueprint(container), url_prefix="/manage")
    app.register_blueprint(create_worker_blueprint(container), url_prefix="/worker")

    logger.info("[App] 起動完了. モード: REAL")
    print("=== DB モード: REAL ===")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=59900, debug=True)