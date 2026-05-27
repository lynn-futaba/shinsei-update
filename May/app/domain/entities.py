"""
ドメインエンティティ定義 (Domain Entities)
作成者: Lynn
----------------------------------
【役割】
システム全体で扱う「データの正しい形」を定義する最重要ファイルです。
各クラス（エンティティ）は、単なるデータの入れ物ではなく、業務ルールを保証する役割を持ちます。

【チームへのメリット】
1. 明確な型定義: どの値が必須で、どの値が数値なのかが一目でわかります。
2. データのガード: __post_init__ によるチェックで、不正なデータ（空文字や型違い）が
   システム内部に侵入してバグを引き起こすのを未然に防ぎます。
3. ロジックの集約: PalletScheduleLineのように、リストの操作（追加・削除）を
   エンティティ自身に行わせることで、コードの散らばりを防ぎ、再利用性を高めます。
"""
# app/domain/entities.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

class DomainValidationError(Exception):
    """データの内容がドメインのルールに違反している場合に投げられるエラーです。"""
    pass

# ==========================================
# 管理画面用エンティティ
# ==========================================    
@dataclass
class RMSCurrentMode:
    """
    RMS（管理システム）の稼働モード状態
    - mode: 自動（True） / 各個（False）
    - preparation_ok: 運転準備が完了しているか
    - auto_running: 現在、自動運転中か
    """
    system_id: str
    system_name: str
    mode: bool
    preparation_ok: bool
    auto_running: bool

    def __post_init__(self) -> None:
        """必須項目のチェックと型チェックを実施します。"""
        if not isinstance(self.system_id, str) or not self.system_id.strip():
            raise DomainValidationError("system_id は必須入力（空文字不可）です")
        if not isinstance(self.system_name, str) or not self.system_name.strip():
            raise DomainValidationError("system_name は必須入力（空文字不可）です")
        if not isinstance(self.mode, bool):
            raise DomainValidationError("mode は bool型である必要があります")
        if not isinstance(self.preparation_ok, bool):
            raise DomainValidationError("preparation_ok は bool型である必要があります")
        if not isinstance(self.auto_running, bool):
            raise DomainValidationError("auto_running は bool型である必要があります")
        
# ---------------------------
# エラー表示用
# ---------------------------
@dataclass
class ErrorListItem:
    """
    エラー一覧表示および詳細モーダル用のデータ構造
    （エラーログとマスタ情報を結合した表示用モデル）
    """
    error_num: int
    error_code: str
    error_category: str
    error_summary: str
    error_operation: str
    error_description: str
    error_level: str
    rms_error_code: Optional[int]  # マスタに存在しない場合は None を許容
    task_id: Optional[int]  # nullable
    robot_id: Optional[int]
    error_datetime: datetime
    is_completed: bool

# ---------------------------
# ライン・間口状態用
# ---------------------------   
@dataclass
class Maguchi:
    """
    各ラインの「間口」状態
    """
    line_id: int
    line_name: str
    transport_permission: bool
    maguchi_no: int | None
    pallet_name: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.line_id, int) or self.line_id < 0:
            raise DomainValidationError("line_id は0以上の数値である必要があります")

        if not self.line_name:
            raise DomainValidationError("line_name は必須入力です")

        if self.maguchi_no is not None and self.maguchi_no not in (1, 2):
            raise DomainValidationError("maguchi_no は 1 または 2 です")

        if not isinstance(self.transport_permission, bool):
            raise DomainValidationError("transport_permission は bool 型である必要があります")

#------------------#
# ステータス状態画面 #
#------------------#        
@dataclass
class TransportTask:
    """
    AMR（自律走行搬送ロボット）の現在のタスク状況 (t_task_status)
    - status: 実行中(EXECUTING), 完了(COMPLETED) などの全体状態
    - phase: 棚取込完了(SHELF_FETCHED) などの詳細フェーズ
    - instruction: 指示コマンド（READY, GO_RETURNなど）
    """
    task_id: int
    status: str
    phase: str
    robot_id: int
    dest_cell: int
    task_type: str
    instruction: str
    updated_date: str
        
# ==========================================
# 共通 / 作業者画面用エンティティ
# ==========================================
@dataclass
class LiftEntrance:
    """
    リフト間口の操作および管理画面共通エンティティ
    ※作業者用リポジトリで使用する場合は、seq_no などの追加フィールドがセットされます。
    """
    maguchi_name: str
    line_name: str
    pallet_name: str
    pallet_id: Optional[int]
    transport_status: str
    
    # 現場操作画面でのみ使用するフィールド（デフォルトNone）
    seq_no: Optional[int] = None
    plat_no: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.maguchi_name:
            raise DomainValidationError("maguchi_name は必須です")
        # 値が存在する場合のみ型チェックを行う
        if self.seq_no is not None and not isinstance(self.seq_no, int):
            raise DomainValidationError("seq_no は数値である必要があります")

# ---------------------------
# 供給パレット（現場作業用）
# ---------------------------          
@dataclass(frozen=True)
class PalletPair:
    """
    パレット供給情報の最小単位（パレット種類 + 供給数）
    ※frozen=Trueにより、一度作成したペアの内容変更を禁止（不変オブジェクト）にしています。
    """
    id: int
    count: int
    pallet_type: Optional[int] = None
    pallet_name: Optional[str] = None  # display/use only; may be None if type is NULL or unknown
    

    def __post_init__(self) -> None:
        # count
        if not isinstance(self.count, int) or self.count < 0:
            raise DomainValidationError("count（供給数）は0以上の数値である必要があります")

        # pallet_type
        if self.pallet_type is not None:
            if not isinstance(self.pallet_type, int) or self.pallet_type < 0:
                raise DomainValidationError("pallet_type は0以上の数値またはNoneである必要があります")

        # pallet_name
        if self.pallet_name is not None and not isinstance(self.pallet_name, str):
            raise DomainValidationError("pallet_name は文字列またはNoneである必要があります")

@dataclass
class PalletScheduleLine:
    """
    特定のラインにおけるパレット供給スケジュールの全体像
    - pairs: 供給予定のパレットペア（PalletPair）のリスト
    """
    line_name: str
    line_id: Optional[int] = None
    pairs: List[PalletPair] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.line_name, str) or not self.line_name.strip():
            raise DomainValidationError("line_name は必須入力です")
        if self.line_id is not None and not isinstance(self.line_id, int):
            raise DomainValidationError("line_id は数値である必要があります")
        for p in self.pairs:
            if not isinstance(p, PalletPair):
                raise DomainValidationError("pairs リストの中身は PalletPair オブジェクトである必要があります")

    # --- 業務ルール（データ操作メソッド） ---
    def add_pair(self, pair: PalletPair, before_index: Optional[int]) -> None:
        """新しいパレット供給ペアを指定位置（または末尾）に追加します。"""
        if before_index is None or before_index < 0 or before_index > len(self.pairs):
            self.pairs.append(pair)
        else:
            self.pairs.insert(before_index, pair)

    def update_pair(self, pair_index: int, pair: PalletPair) -> None:
        """指定したインデックスの供給情報を更新します。"""
        if pair_index < 0 or pair_index >= len(self.pairs):
            raise IndexError("指定されたパレットインデックスが範囲外です")
        self.pairs[pair_index] = pair

    def delete_pair(self, pair_index: int) -> None:
        """指定したインデックスの供給情報を削除します。"""
        if pair_index < 0 or pair_index >= len(self.pairs):
            raise IndexError("指定されたパレットインデックスが範囲外です")
        self.pairs.pop(pair_index)

    def move_to_group0(self, pair_index: int) -> None:
        """指定したパレットをリストの最優先（先頭）に移動させます。"""
        if pair_index < 0 or pair_index >= len(self.pairs):
            raise IndexError("指定されたパレットインデックスが範囲外です")
        item = self.pairs.pop(pair_index)
        self.pairs.insert(0, item)



      