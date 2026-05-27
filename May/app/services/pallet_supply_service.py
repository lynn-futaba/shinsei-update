"""
パレット供給サービス (PalletSupplyService)
作成者: Lynn
----------------------------------
各ラインへのパレット供給スケジュール（投入順序と数量）を管理するサービス。

主な役割:
1. スケジュール操作: パレットペア（型式と数量のセット）の追加、更新、削除、
   および優先順位変更（先頭移動）のロジックを提供します。
2. データ変換 (DTO): ドメインエンティティを、フロントエンド（JavaScript）が
   そのまま処理しやすい単純な辞書形式（DTO）に変換します。
3. 入力バリデーション: パレット名が空でないか、数量が0以上かなど、
   不正なデータがDBに登録されるのを未然に防ぎます。

現場の作業順序を動的に変更するための「司令塔」となるコンポーネントです。
"""
# app/services/pallet_supply_service.py
from __future__ import annotations
from typing import List, Dict
from app.infrastructure.repositories.worker_repository import WorkerRepository
from app.domain.exception import DomainValidationError, NotFoundError, InvalidStateError, StaleWriteError
from app.domain.entities import PalletScheduleLine

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ使用
logger = setup_log(cfg.LOG_FOLDER, cfg.PALLET_SUPPLY_SEV_LOG_FILE, cfg.BACKUP_DAYS, logger_name="pallet_supply_svc")

class PalletSupplyService:
    """
    パレット供給サービス（Worker用）
    - Controller/JS に返す DTO:
      line = {
        "line_name": str,
        "pairs": [
          { "pallet_type": int, "pallet_name": str | None, "count": int }, ...
        ]
      }
    """

    def __init__(self, repo: WorkerRepository, *, max_pairs: int = 10):
        self._repo = repo
        self._max_pairs = max_pairs  # fallback if repo doesn't provide

    # --- DTO mappers ---
    
    @staticmethod
    def to_line_dto(line: PalletScheduleLine) -> Dict:
        # ✅ Build pairs first
        pairs = [
            {
                "pair_id": p.id,
                "pallet_type": p.pallet_type,
                "pallet_name": p.pallet_name,
                "count": p.count
            }
            for p in (line.pairs or [])
        ]

        # ✅ Return final structure
        return {
            "line_id": line.line_id,
            "line_name": line.line_name,
            "pairs": pairs
        }


    # --- Reads ---
    def list_all(self) -> List[Dict]:
        return [self.to_line_dto(line) for line in self._repo.ps_list_all()]

    def get_line(self, line_id: str) -> Dict:
        line = self._repo.ps_get_line(line_id)
        if not line:
            raise NotFoundError(f"{line_id} は存在しません。")
        return self.to_line_dto(line)
    
    def list_names(self, line_name: str) -> List[Dict]:
        if not self._repo.ps_line_exists(line_name):
            raise NotFoundError(f"{line_name} は存在しません。")
        # Recommended: have repo return [{"pallet_type": int, "pallet_name": str}, ...]
        return self._repo.ps_list_names(line_name)
    
    
    def apply_pattern(self, pattern_no: int):
        """
        Apply pallet supply pattern.
        Supported: Pattern 1, Pattern 2
        """
        updated_lines = self._repo.ps_apply_pattern(pattern_no)

        if not updated_lines:
            raise InvalidStateError("パターン適用後データが取得できません。")

        return [self.to_line_dto(line) for line in updated_lines]


    def add_pair(self, line_id: str, pallet_type: int, count: int, before_index: int | None) -> Dict:
        self._validate_type_and_count(pallet_type, count)
        updated = self._repo.ps_add_pair(
            line_id=line_id,
            pallet_type=int(pallet_type),
            count=int(count),
            before_index=before_index
        )
        if not updated:
            raise StaleWriteError(f"{line_id} は他のユーザーによって更新されました。")
        return self.to_line_dto(updated)

    def update_pair(self, line_id: str, pair_id: int, pallet_type: int, count: int) -> Dict:
        self._validate_type_and_count(pallet_type, count)
        updated = self._repo.ps_update_pair(
            line_id=line_id,
            pair_id=int(pair_id),
            pallet_type=int(pallet_type),
            count=int(count)
        )
        if not updated:
            raise StaleWriteError("更新に失敗しました（排他エラー）。")
        return self.to_line_dto(updated)


    def delete_pair(self, line_id: str, pair_id: int) -> Dict:
        updated = self._repo.ps_delete_pair(
            line_id=line_id,
            pair_id=int(pair_id)
        )
        if not updated:
            raise StaleWriteError(f"{line_id} の削除に失敗しました（排他エラー）。")
        return self.to_line_dto(updated)

    def move_to_group0(self, line_id: str, pair_index: int) -> Dict:
        updated = self._repo.ps_move_to_group0(
            line_id=line_id,
            pair_index=int(pair_index)
        )
        if not updated:
            raise StaleWriteError(f"{line_id} の移動に失敗しました。")
        return self.to_line_dto(updated)
    
    def get_master_pallet_list(self) -> List[Dict]:
        """
        Returns: [ { "pallet_type": int, "pallet_name": str, "versatility": 0|1, "kotatsu_type": int }, ... ]
        """
        return self._repo.get_all_master_pallets()

    
    # ===== Helpers =====
    @staticmethod
    def _validate_type_and_count(pallet_type: int, count: int) -> None:
        if not isinstance(pallet_type, int):
            raise DomainValidationError("pallet_type は必須です。")
        if pallet_type < 0:
            raise DomainValidationError("pallet_type は 0 以上で指定してください。")
        try:
            c = int(count)
        except Exception:
            raise DomainValidationError("count は整数で指定してください。")
        if c < 0:
            raise DomainValidationError("count は 0 以上で指定してください。")
        
