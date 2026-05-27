"""
ドメインファクトリー (DomainFactory)
作成者: Lynn
----------------------------------
【役割】
データベースから取得した「生のデータ（辞書形式/Row）」を、
プログラム内で扱いやすい「ドメインエンティティ（クラスオブジェクト）」に変換する専用クラスです。

【チームへのメリット】
- DB側のカラム名変更や型変更があっても、このファイルだけを修正すればOK。
- ビジネスロジック（Service層など）で、型定義された安全なオブジェクトとしてデータを扱えます。
- MySQL特有の型（BIT型など）の判定ロジックを共通化し、バグを防ぎます。
"""
# app/infrastructure/factory/domain_factory.py
from __future__ import annotations
from typing import Protocol, Optional, Iterable, List, Dict
from datetime import datetime

from app.domain.entities import Maguchi, TransportTask, LiftEntrance, PalletPair, PalletScheduleLine, RMSCurrentMode, ErrorListItem


# ---------- ヘルパー関数 (型変換の共通処理) ----------
def _bit_to_bool(v) -> bool:
    """MySQLのBIT型や様々な入力値をPythonのbool型(True/False)に安全に変換します。"""
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, (bytes, bytearray)):
        return any(b != 0 for b in v)  # 0以外のバイトがあればTrue
    if isinstance(v, str):
        return v not in ("", "0", "\x00")
    return bool(v)

def _bit_to_int(v) -> Optional[int]:
    """MySQLのBIT型などをPythonのint型に変換します。"""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v, byteorder="big", signed=False)
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return int(v, 2) # 2進数文字列のフォールバック
            except ValueError:
                return None
    return None

def _to_int_or_none(v) -> Optional[int]:
    """数値を安全にintに変換し、失敗した場合はNoneを返します。"""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except Exception:
        return None
    

def _to_datetime_or_now(v) -> datetime:
    """
    DBの日時データをdatetimeオブジェクトに正規化します。
    - 文字列の場合は主要なフォーマットで解析。
    - データが空や不正な場合は、フォールバックとして現在時刻(now)を返します。
    """
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        # Try ISO-like first (e.g., '2025-04-28 17:40:00')
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                pass
        # Last resort: attempt datetime.fromisoformat (Py3.7+)
        try:
            return datetime.fromisoformat(v)
        except Exception:
            return datetime.now()
    # If None or any unexpected type:
    return datetime.now()

# ==========================================
# 管理画面向けファクトリー (ManageFactory)
# ==========================================
class ManageFactory(Protocol):
    """管理画面（Admin）で使用するデータの生成を担います。"""
    
    @staticmethod
    def get_rms_current_mode(row: dict) -> RMSCurrentMode:
        """システムの現在の運転モード（自動/準備完了など）の状態を生成します。"""
        def b(v):
            try:
                return bool(int(v))
            except Exception:
                return bool(v)
        return RMSCurrentMode(
            system_id=str(row.get("system_id", "")),
            system_name=str(row.get("system_name", "")),
            mode=b(row.get("mode", 0)),
            preparation_ok=b(row.get("preparation_ok", 0)),
            auto_running=b(row.get("auto_running", 0)),
        )
        
    @staticmethod
    def get_error_list(row: dict) -> ErrorListItem:
        """DBのエラー履歴情報を、画面表示用のエラーアイテムに変換します。"""
        return ErrorListItem(
            error_num = _to_int_or_none(row.get("error_num")) or 0,  # 0 if somehow missing
            error_code = str(row.get("error_code") or ""),
            error_category = str(row.get("error_category") or ""),
            error_summary = str(row.get("error_summary") or ""),
            error_operation = str(row.get("error_operation") or ""),
            error_description = str(row.get("error_description") or ""),
            error_level = str(row.get("error_level") or ""),
            rms_error_code = _bit_to_int(row.get("rms_error_code")),    # BIT(50) -> Optional[int]
            task_id = _to_int_or_none(row.get("task_id")),
            robot_id = _to_int_or_none(row.get("robot_id")),
            # If cursor returns string for datetime, you can parse it; mysql-connector usually gives datetime already
            error_datetime = _to_datetime_or_now(row.get("error_datetime")),  # <-- normalize here
            is_completed = _bit_to_bool(row.get("is_completed")),
        )

    @staticmethod
    def get_task_status(row: dict) -> TransportTask:
        """搬送タスク（どのロボットがどこへ運んでいるか）の状態を生成します。"""
        return TransportTask(
            task_id=row["task_id"],
            status=str(row["status"]),
            phase=str(row["phase"]),
            robot_id=row["robot_id"],
            dest_cell=row["dest_cell"],
            task_type=str(row["task_type"]),
            instruction=str(row["instruction"]),
            updated_date=str(row["updated_date"])
        )

    @staticmethod
    def get_line_state_list(row: dict) -> Maguchi:
        return Maguchi(
            line_id=int(row["line_id"]),
            line_name=str(row["line_name"]),
            transport_permission=bool(row["transport_permission"]),
            maguchi_no=row.get("maguchi_no"),
            pallet_name=row.get("pallet_name")
        )
    
    @staticmethod
    def get_lift_entrance(row: dict) -> LiftEntrance:
        """Create LiftEntrance safely from DB row."""

        raw_pallet_id = row.get("pallet_id")

        try:
            pallet_id = int(raw_pallet_id) if raw_pallet_id not in (None, "", "null") else None
        except (TypeError, ValueError):
            pallet_id = None

        return LiftEntrance(
            maguchi_name=str(row.get("maguchi_name") or ""),
            line_name=str(row.get("line_name") or ""),
            pallet_name=str(row.get("pallet_name") or ""),
            pallet_id=pallet_id,              # ✅ always int or None
            transport_status=str(row.get("transport_status") or "")
        )
        
    
# 作業者ファクトリー
class WorkerFactory(Protocol):
    """現場端末（Worker）画面で使用するデータの生成を担います。"""

    #-----------------#
    # リフト間口操作画面 #
    #-----------------#
    @staticmethod
    def get_lift_entrance(row: dict) -> LiftEntrance:
        """リフト者が確認するリフトの状況を生成します（順序番号や版情報を含む）。"""
        return LiftEntrance(
            maguchi_name=str(row.get("maguchi_name") or ""),
            line_name=str(row.get("line_name") or ""),
            pallet_name=str(row.get("pallet_name") or ""),
            pallet_id=str(row.get("pallet_id") or ""),
            transport_status=str(row.get("transport_status") or ""),
            seq_no=row.get("seq_no"),
            plat_no=row.get("plat_no")
        )
    
    # ---------------------------
    # 供給パレット画面向け
    # ---------------------------
    @staticmethod
    def pallet_pair_from_row(row: Dict) -> PalletPair:
        """パレットの種類と個数のセット（1ペア）を生成します。"""
        return PalletPair(
            id = row["id"],
            pallet_type = row["pallet_type"],
            pallet_name = row["pallet_name"],  
            count       = row["count"],
        )
    
    @staticmethod
    def pallet_schedule_line_from_rows(
        line_name: str,
        rows: List[Dict],
        line_id: Optional[int],
    ) -> PalletScheduleLine:
        """特定のラインにおける、パレットの供給スケジュール（複数ペアのリスト）を生成します。"""
        pairs = [WorkerFactory.pallet_pair_from_row(r) for r in rows]
        return PalletScheduleLine(
            line_name=line_name,
            line_id=line_id,
            pairs=pairs,
        )

        
    
    
        
    
    
    




    
 
   