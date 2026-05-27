"""
APIレスポンスフォーマッター (api_response_format)
作成者: Lynn
----------------------------------
【役割】
フロントエンド（UI）へ返却するJSONレスポンスの「形」をプロジェクト全体で統一するためのツールです。

【チームへのメリット】
1. フロントエンドの負担軽減: 成功時も失敗時も常に同じ構造（status, message, data...）で
   データが届くため、UI側の共通処理が書きやすくなります。
2. エラーハンドリングの明確化: 独自の「ErrorCode」を返すことで、UI側で「404ならこのメッセージを出す」
   といった分岐処理を確実に行えるようになります。
3. ページネーションの自動化: `paged` 関数を使うだけで、全ページ数などの計算を自動で行います。
"""

# app/domain/api_response_format.py
from __future__ import annotations
from typing import Any, Optional, Tuple, Dict
from flask import jsonify


class ErrorCode:
    """
    システム共通のエラーコード定義。
    UI側はこの文字列を見て動作を分岐させます。
    ※名前を変更するとUI側の実装が壊れる可能性があるため、追加時は慎重に行いましょう。
    """
    NOT_FOUND = "NOT_FOUND" # データが見つからない
    BAD_REQUEST = "BAD_REQUEST" # リクエスト形式が不正
    INVALID = "INVALID" # 入力値のバリデーションエラー
    INVALID_STATE = "INVALID_STATE" # 現在のステータスでは実行不能な操作
    STALE_WRITE = "STALE_WRITE" # 他のユーザーが更新済み（競合）
    UNKNOWN_ACTION = "UNKNOWN_ACTION" # 未定義の操作
    CONFLICT = "CONFLICT" # 重複などの衝突
    UNAUTHORIZED = "UNAUTHORIZED" # ログインが必要
    FORBIDDEN = "FORBIDDEN" # 権限不足
    INTERNAL_ERROR = "INTERNAL_ERROR" # サーバー内部エラー（予期せぬ例外）


# ---------- 成功時（Success）のレスポンス作成ヘルパー ----------

def success(data: Any = None, message: str = "OK", status: int = 200) -> Tuple[Any, int]:
    """
    標準的な成功レスポンスを返します。
    例: { "status": 200, "message": "OK", "data": { ... } }
    """
    return jsonify({"status": status, "message": message, "data": data}), status


def created(data: Any = None, message: str = "Created") -> Tuple[Any, int]:
    """新規登録成功時 (HTTP 201) に使用します。"""
    return success(data=data, message=message, status=201)


def no_content(message: str = "No Content") -> Tuple[Any, int]:
    """削除成功時など、返すデータがない場合 (HTTP 204) に使用します。"""
    return jsonify({"status": 204, "message": message, "data": None}), 204


def paged(
    data: Any,
    *,
    total: int,
    page: int,
    page_size: int,
    message: str = "OK",
    status: int = 200,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, int]:
    """
    一覧画面などで「ページ番号」や「全件数」を含めたレスポンスを返します。
    - meta 内に自動計算された総ページ数 (pages) などが含まれます。
    """
    pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    meta = {"total": total, "page": page, "page_size": page_size, "pages": pages}
    if extra_meta:
        meta.update(extra_meta)
    return jsonify({"status": status, "message": message, "data": data, "meta": meta}), status


# ---------- エラー時（Error）のレスポンス作成ヘルパー ----------

def error(status: int, code: str, message: str, details: Optional[Any] = None) -> Tuple[Any, int]:
    """
    共通のエラー構造を生成します。
    例: { "status": 400, "message": "エラー内容", "error": { "code": "BAD_REQUEST", "details": ... } }
    """
    return jsonify({
        "status": status,
        "message": message,
        "error": {"code": code, "details": details}
    }), status

def bad_request(message: str = "Bad Request", details: Optional[Any] = None):
    """リクエストが不正な場合 (HTTP 400)"""
    return error(400, ErrorCode.BAD_REQUEST, message, details)

def not_found(message: str = "Not Found", details: Optional[Any] = None):
    """対象が存在しない場合 (HTTP 404)"""
    return error(404, ErrorCode.NOT_FOUND, message, details)

def invalid(message: str = "Invalid", details: Optional[Any] = None):
    """入力値エラー (HTTP 422)"""
    return error(422, ErrorCode.INVALID, message, details)

def invalid_state(message: str = "Invalid State", details: Optional[Any] = None):
    """「完了済みのためキャンセル不可」など状態異常の場合 (HTTP 422)"""
    return error(422, ErrorCode.INVALID_STATE, message, details)

def stale_write(message: str = "Stale Write", details: Optional[Any] = None):
    """編集中に他の人が更新してしまった場合 (HTTP 409)"""
    return error(409, ErrorCode.STALE_WRITE, message, details)

def unauthorized(message: str = "Unauthorized", details: Optional[Any] = None):
    """未認証（要ログイン）の場合 (HTTP 401)"""
    return error(401, ErrorCode.UNAUTHORIZED, message, details)

def forbidden(message: str = "Forbidden", details: Optional[Any] = None):
    """権限がない操作をしようとした場合 (HTTP 403)"""
    return error(403, ErrorCode.FORBIDDEN, message, details)

def conflict(message: str = "Conflict", details: Optional[Any] = None):
    """重複登録など、リソースの衝突が発生した場合 (HTTP 409)"""
    return error(409, ErrorCode.CONFLICT, message, details)

def internal_error(message: str = "Internal Error", details: Optional[Any] = None):
    """サーバー側で予期せぬエラーが発生した場合 (HTTP 500)"""
    return error(500, ErrorCode.INTERNAL_ERROR, message, details)