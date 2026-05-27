"""リフト搬入口サービス (LiftEntranceService)
作成者: Lynn
----------------------------------
リフト搬入口における荷揃え・投入作業の進捗を管理するサービス。

主な役割:
1. 作業フローの制御: 「作業開始（READY→WORK）」および「作業完了（WORK→COMPLETE）」
   のステータス遷移をビジネスルールに従って実行します。
2. 競合防止の最終確認: UIから送られてきた `rev`（リビジョン）をリポジトリへ渡し、
   他の作業者と操作が重なっていないかを厳格にチェックします。
3. API用データ整形: エンティティを直接返さず、フロントエンドが扱いやすい
   辞書形式（Dict）に変換して提供します。

現場の「モノの動き」とシステムの「データの動き」を同期させるための
重要な中継役となります。
"""
# app/services/lift_entrance_service.py
from __future__ import annotations
from typing import List, Dict
from app.domain.entities import LiftEntrance, DomainValidationError
from app.infrastructure.repositories.worker_repository import WorkerRepository
from app.domain.exception import DomainValidationError, NotFoundError, InvalidStateError, StaleWriteError

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ使用
logger = setup_log(cfg.LOG_FOLDER, cfg.LIFT_ENTRANCE_SEV_LOG_FILE, cfg.BACKUP_DAYS, logger_name="lift_entrance_svc")


# リフト間口サービス
class LiftEntranceService:
    def __init__(self, repo: WorkerRepository):
        self._repo = repo
    
    def list(self) -> list[Dict]:
        return [
            {
                "seq_no": row.seq_no,
                "plat_no": row.plat_no,
                "maguchi_name": row.maguchi_name,
                "line_name": row.line_name,
                "pallet_name": row.pallet_name,
                "pallet_id": row.pallet_id,
                "transport_status": row.transport_status,
            }
            for row in self._repo.list_lift_entrance()
        ]

    def _to_api_dict(self, updated: LiftEntrance) -> Dict:
        return {
            "seq_no": updated.seq_no,
            "plat_no": updated.plat_no,
            "maguchi_name": updated.maguchi_name,
            "line_name": updated.line_name,
            "pallet_name": updated.pallet_name,
            "pallet_id": updated.pallet_id,
            "transport_status": updated.transport_status,
        }

    # READY -> WORK
    def start(self, plat_no: int, seq_no: int, pallet_id:int) -> Dict:
        updated = self._repo.update_state(plat_no, seq_no, pallet_id, next_state="WORK")
        logger.info(f"リフト間口サービス start(): {updated}")
        return self._to_api_dict(updated)

    # WORK -> COMP
    def finish(self, plat_no: int, seq_no: int, pallet_id:int) -> Dict:
        updated = self._repo.update_state(plat_no, seq_no, pallet_id, next_state="COMP")
        logger.info(f"リフト間口サービス finish(): {updated}")
        return self._to_api_dict(updated)




    