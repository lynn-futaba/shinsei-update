"""
管理者用サービス (ManageService)
作成者: Lynn
----------------------------------
管理者画面（ダッシュボード）の業務ロジックを統括するクラス。

主な役割:
1. 業務ロジックの実行:
   - 搬送許可のトグル切り替えや、RMS（ロボット管理システム）の
     自動運転シーケンス（準備・開始・実行）などの具体的な手順を制御。
2. データの橋渡し:
   - コントローラーからの要求を受け取り、リポジトリを介して
     エンティティを取得・加工して返却。
3. 疎結合設計（DI による注入）:
   - 実行時には具体クラスに依存せず、DI コンテナからリポジトリを注入。
     テスト容易性と保守性を担保。

この層にロジックを集中させることで、将来的な仕様変更（例：許可設定時のバリデーション追加）
にも柔軟かつ迅速に対応可能です。
"""
# app/services/manage_service.py
from __future__ import annotations
from typing import TYPE_CHECKING

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定 (名前を付ける)
logger = setup_log(cfg.LOG_FOLDER, cfg.MANAGE_SEV_LOG_FILE, cfg.BACKUP_DAYS, logger_name="manage_service")

# 型チェック時のみ具体的な実装を参照（実行時はDIで注入されるため依存しない）
if TYPE_CHECKING:
    from app.infrastructure.repositories.manage_repository import ManageRepository
    from app.infrastructure.repositories.athena_repository import AthenaRepository


class ManageService:
    """
    Service layer for management features.
    Concrete repositories are injected by the DI container at runtime.
    """

    def __init__(self, repo: 'ManageRepository', athena_repo: 'AthenaRepository'):
        self._repo = repo
        self._athena_repo = athena_repo

    # ライン状態
    def get_line_state_list(self):
        return self._repo.get_line_state_list()

    # ★★★ ラインIDの transport_permission を 0⇄1 でトグルする ★★★
    def toggle_transport_permission(self, line_id: int) -> bool:
        """
        transport_permission をトグルして、更新後の値（True/False）を返す
        """
        return bool(self._repo.toggle_transport_permission(line_id))

    # タスク状態
    def get_task_status(self, minutes=10, limit=10, page=1):
        return self._repo.get_task_status(
            minutes=minutes,
            limit=limit,
            page=page
        )

    # リフト間口操作状態
    def get_lift_entrance(self):
        return self._repo.get_lift_entrance()

    # エラー状態
    def get_error_list(self):
        return self._repo.get_error_list()
    
    def reset_error(self, source: str, error_num):
        if source == "RMS":
            try:
                athena_id = int(error_num)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid RMS athena_id: {error_num}")

            self._repo.resolve_rms_error(athena_id)

        elif source == "WCS":
            self._repo.resolve_wcs_error(int(error_num))

        else:
            raise ValueError(f"Unknown error source: {source}")

    # --- RMS モード ---
    def get_rms_current_mode(self):
        return self._repo.get_rms_current_mode()

    def rms_set_mode(self, mode) -> bool:
        """
        Set mode explicitly: 1=自動, 0=各個
        Returns final mode as bool (True=自動, False=各個)
        """
        return bool(self._repo.rms_set_mode(1 if int(mode) == 1 else 0))

    # --- RMS 自動モード steps ---
    def rms_auto_prepare(self):
        """
        Force Auto mode and set: preparation_ok=1, auto_running=0.
        Return updated RMSCurrentMode entity.
        """
        return self._repo.rms_auto_prepare()

    def rms_auto_start(self):
        """
        Force Auto mode and set: preparation_ok=1, auto_running=0.
        (Same flags as prepare for now; step semantics handled in UI or future column)
        """
        return self._repo.rms_auto_start()

    def rms_auto_run(self):
        """
        Force Auto mode and set: preparation_ok=1, auto_running=1.
        """
        return self._repo.rms_auto_run()

    def sync_and_get_all_errors(self, rms_boot_ts: str):
        """
        1. Athena から取得
        2. ローカルの WCS エラー取得
        3. 両方を統合して返却
        """
        # 1. Athena から取得
        rms_errors = self._athena_repo.get_active_errors_since(rms_boot_ts)

        # 2. ローカル（WCS エラー）
        wcs_errors = self._repo.get_error_list()

        # 3. フロントエンド向けに結合
        return {
            "wcs_errors": wcs_errors,
            "rms_errors": rms_errors
        }

    def sync_rms_errors(self, rms_boot_ts: str):
        """
        Athena 側のエラーをローカルDBに同期（upsert）し、反映件数を返す。
        """
        athena_data = self._athena_repo.get_active_errors_since(rms_boot_ts)

        if not athena_data:
            logger.info("Sync skipped: No data found in Athena.")
            return 0

        count = 0
        for row in athena_data:
            error_data = {
                "athena_id": row['athena_id'],        # AS athena_id と一致
                "system_code": row['system_code'],
                "occurrence_time": row['occurrence_time'],
                "fault_status": row['fault_status'],
                "device_id": row.get('device_id'),
                "cell_code": row.get('cell_code')
            }
            if self._repo.upsert_rms_error(error_data):
                count += 1

        logger.info(f"Sync complete: {count} rows updated in local DB.")
        return count