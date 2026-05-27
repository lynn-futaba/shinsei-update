"""
共通ログ設定ユーティリティ (setup_log.py)
作成者: Lynn
----------------------------------
システム全体の「トレーサビリティ（追跡可能性）」を支えるログ管理モジュール。

主な役割:
1. 名前付きロガーの生成 (Named Loggers):
   - 各サービス（Service/Controller/Repository）ごとに独立したロガーを生成し、
     ログの混線を防止します。
2. 自動ローテーション機能:
   - `TimedRotatingFileHandler` を採用。毎日深夜（midnight）にログを切り替え、
     古いログを自動でアーカイブします。
3. 詳細なログフォーマットの統一:
   - 日時、ログレベル、モジュール名、行番号を標準化。
   - 例: `2026/03/18 10:50:00.123,INFO,admin_ctrl,manage_service,0042,Task started`
4. パフォーマンスと信頼性:
   - `propagate = False` により二重出力を防止し、ディスク容量の圧迫を防ぎます。
   - `get_rollover_count` によるデバッグ用世代数カウント機能を搭載。

工場の稼働停止（ダウンタイム）を最小限に抑えるための、強力なデバッグ基盤です。
"""
import os
import logging
from logging import Formatter, INFO
from logging.handlers import TimedRotatingFileHandler
import glob

# ログレベルの設定
LOG_LEVEL = INFO
ENCODING = "utf-8"

def get_rollover_count(folder_path: str, file_name: str) -> int:
    """
    現在フォルダ内に存在する、ローテーションされたログファイルの数を返す
    """
    # 例: admin_controller.log.2024-01-01 などのパターンに一致するファイルを検索
    search_pattern = os.path.join(folder_path, f"{file_name}*")
    files = glob.glob(search_pattern)
    return len(files)

def setup_log(folder_name: str, file_name: str, backup_day: int, logger_name: str = None):
    """
    :param logger_name: 各ファイル固有の名前 (None の場合はルートロガー)
    """
    path = os.path.dirname(__file__)
    folder_path = os.path.abspath(os.path.join(path, folder_name))
    os.makedirs(folder_path, exist_ok=True)

    file_fullpath = os.path.join(folder_path, file_name)

    # 1. 名前付きロガーを取得 (重要: これにより複数ファイルでの衝突を防ぐ)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # 既存のハンドラがあれば追加しない (二重出力を防ぐ)
    
    if not any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
        file_handler = TimedRotatingFileHandler(
            file_fullpath, 
            when='midnight',
            interval=1,
            backupCount=backup_day,
            encoding=ENCODING
        )

        file_handler.setFormatter(
            Formatter(
                "%(asctime)s.%(msecs)03d,%(levelname)-5s,%(name)s,%(module)s,%(lineno)04d,%(message)s",
                datefmt="%Y/%m/%d %H:%M:%S",
            )
        )
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        
        # コンソールやルートへの伝播を止める (admin_ctrl.log にだけ書き込むため)
        logger.propagate = False

    # ロールオーバー（世代数）のカウントを表示（デバッグ用）
    count = get_rollover_count(folder_path, file_name)
    logger.debug(f"Log initialized for {file_name}. Current history count: {count}")

    return logger