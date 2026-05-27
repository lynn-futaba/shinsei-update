"""
システム共通設定ファイル (Global Configuration)
作成者: Lynn
最終更新: 2026/03/16 - 岡崎工場環境向けに最適化
----------------------------------
アプリケーション全体の動作を制御する静的な設定値を一括管理するモジュール。

主な役割:
1. 接続先の一元管理:
   - 4つの異なるデータベース (WCS, EIP, IOTDS, ATHENA) の接続情報を定義。
   - ロボット管理システム (RMS) のIP/ポート、および認証情報を保持。
2. ログ出力の設計:
   - 各サービス・コントローラー・リポジトリごとに専用のログファイルを割り当て。
   - 120日間のローテーション設定により、長期のトレーサビリティを確保。
3. セキュリティと保守性:
   - 環境変数への依存を排除し、設定ファイル単体での完結性を高めることで
"""     

# --- RMS Credentials (Added for Login fix) ---
RMS_USER_ID = "geekplus"
RMS_USER_KEY = "111111"

# --- DB 設定 (岡崎 10.102.12.81) (高橋 192.168.3.10) (岡崎仮想 10.108.3.5) ---
MYSQL_WCS_DB = {
    "host": "10.108.3.5",
    "port": 3306,
    "user": "athena",
    "password": "WGQKJPL8V/xQ",
    "database": "futaba_ok2_shippment",
}

MYSQL_EIP_DB = {
    "host": "10.108.3.5",
    "port": 3306,
    "user": "athena",
    "password": "WGQKJPL8V/xQ",
    "database": "eip_signal",
}

MYSQL_IOTDS_DB = {
    "host": "10.108.3.5",
    "port": 3306,
    "user": "athena",
    "password": "WGQKJPL8V/xQ",
    "database": "futaba_ok2_iot",
}

MYSQL_ATHENA_DB = {
    "host": "10.108.3.5",
    "port": 3306,
    "user": "athena",
    "password": "WGQKJPL8V/xQ",
    "database": "athena",
}

# --- RMS Network 設定 ---
RMS_IP = "10.108.3.5"
RMS_PORT = 8895
RESPONSE = "clientid"

# --- LOG 設定 ---
LOG_FOLDER = "../logs"
LOG_FILE = "init_debug.log"
BACKUP_DAYS = 120
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARN, ERROR
ENCODING = "utf-8"
LOG_ROTATE_WHEN = "D"
LOG_ROTATE_INTERVAL = 1

# --- Controller ログフィイル ---
ADMIN_CTRL_LOG_FILE = "admin_controller.log"
WORKER_CTRL_LOG_FILE = "worker_controller.log"
TEST_CTRL_LOG_FILE = "test_controller.log"

# --- Runner ログフィイル ---
RUN_CONTROLL_LOG_FILE = "run_controll.log"

# --- Service ログフィイル ---
MANAGE_SEV_LOG_FILE = "manage_service.log"
LIFT_ENTRANCE_SEV_LOG_FILE = "lift_entrance_service.log"
PALLET_SUPPLY_SEV_LOG_FILE = "pallet_supply_service.log"
IOTDS_SEV_LOG_FILE = "iotds_service.log"
OPERATION_SEV_LOG_FILE = "operation_service.log"
OPERATION_NI_SEV_LOG_FILE = "operation_ni_service.log"

# --- RMS Service ログフィイル ---
RMS_CALLBACK_SEV_LOG_FILE = "rms_callback_service.log"
RMS_MANUAL_SEV_LOG_FILE = "rms_manual_service.log"
RMS_MONITORING_SEV_LOG_FILE = "rms_monitoring_service.log"
RUN_INITIALIZATION_SEV_LOG_FILE = "run_initialization_service.log"

# --- Repository ログフィイル ---
MANAGE_REPO_LOG_FILE = "manage_repository.log"
WORKER_REPO_LOG_FILE = "worker_repository.log"
IOTDS_REPO_LOG_FILE = "iotds_repository.log"
OPERATION_REPO_LOG_FILE = "operation_repository.log"

# --- RMS API ログフィイル ---
RMS_CALLBACK_API_LOG_FILE = "rms_callback_api.log"
RMS_MANUAL_API_LOG_FILE = "rms_manual_api.log"
POST_RMS_API_LOG_FILE = "post_rms_api.log"
OPERATION_RMS_API_LOG_FILE = "operation_rms_api.log"

# --- SQL クエリ ログフィイル ---
WCS_SQL_QUERY_LOG_FILE = "wcs_sql_query.log"
EIP_SQL_QUERY_LOG_FILE = "eip_sql_query.log"
IOTDS_SQL_QUERY_LOG_FILE = "iotds_sql_query.log"
ATHENA_SQL_QUERY_LOG_FILE = "athena_sql_query.log"

# --供給パレット MAX_PAIRS
PALLET_SUPPLY_MAX_PAIRS = 10

PERMISSION_SIGNAL_BY_LINE = {
    1: 1301,
    2: 1401,
    3: 1601,
    4: 1801,
}