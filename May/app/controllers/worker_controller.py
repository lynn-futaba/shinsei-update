"""
作業者用コントローラー (WorkerController)
作成者: Lynn
----------------------------------
リフト間口画面および空パレット登録画面のバックエンドAPIを統括するクラス。

主な役割:
1. HTTPリクエストの受付: ブラウザやタブレットからのGET/POST/PUT/DELETEリクエストを
   受け取り、適切なサービス（LiftEntrance / PalletSupply）へ振り分けます。
2. エラーハンドリングの共通化: サービス層で発生したカスタム例外（NotFoundError, 
   StaleWriteError等）を捕捉し、フロントエンドが理解できる標準的なAPIレスポンス
   （success, stale_write等）に変換して返却します。
3. UIテンプレートの提供: 各作業画面の初期HTML（Jinja2テンプレート）を表示する
   ルートを提供します。

フロントエンド（HTML/JS）とビジネスロジック（Service）を繋ぐ「窓口」となるコンポーネントです。
"""
# app/controllers/worker_controller.py
from __future__ import annotations
from flask import Blueprint, request, render_template
from werkzeug.exceptions import BadRequest
from app.domain.exception import NotFoundError, StaleWriteError, InvalidStateError, DomainValidationError
from app.domain.api_response_format import (
    success, bad_request, not_found, stale_write, invalid_state, error, invalid, internal_error,
    ErrorCode
)

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ使用
logger = setup_log(cfg.LOG_FOLDER, cfg.WORKER_CTRL_LOG_FILE, cfg.BACKUP_DAYS, logger_name="worker_ctrl")


def create_worker_blueprint(container) -> Blueprint:
    bp = Blueprint("worker_controller", __name__)
    lift_entrance_service = container.lift_entrance_service
    pallet_supply_service = container.pallet_supply_service

    # ---------- リフト間口 UI ----------
    @bp.get("/lift_entrance_ui")
    def lift_entrance_ui():
        return render_template("worker/lift-entrance.html", title="リフト間口操作画面")

    # ==================
    # リフト間口一覧表 APIs
    # ==================
    @bp.get("/api/v1/lift_entrance")
    def list_lift_entrance():
        rows = lift_entrance_service.list()
        return success(data=rows)

    # =======================
    # リフト間口操作画面 APIs
    # =======================
    @bp.post("/api/v1/lift_entrance/<seq_no>/action")
    def do_action(seq_no: str):
        payload = request.get_json(silent=True) or {}
        action = str(payload.get("action", "")).upper().strip()
        plat_no = payload.get("plat_no")
        pallet_id = payload.get("pallet_id")

        if not action or plat_no is None:
            return bad_request("action と plat_no は必須です")

        # normalize types early
        try:
            plat_no_int = int(plat_no)
            seq_no_int = int(seq_no)
        except ValueError:
            return bad_request("plat_no と seq_no は整数である必要があります")

        try:
            if action == "START":
                row = lift_entrance_service.start(plat_no_int, seq_no_int, pallet_id)
            elif action == "FINISH":
                row = lift_entrance_service.finish(plat_no_int, seq_no_int, pallet_id)
            else:
                return error(422, ErrorCode.UNKNOWN_ACTION, "不明な操作です")
            return success(data=row)
        
        except (NotFoundError, InvalidStateError) as ex:
            if isinstance(ex, NotFoundError):
                return not_found(str(ex))
            return invalid_state(str(ex))
        except Exception as ex:
            logger.error(f"Unexpected error in do_action: {str(ex)}")
            return internal_error(str(ex))


    # ---------- 空パレット登録 UI ----------
    @bp.get("/pallet_supply_ui")
    def pallet_supply_ui():
        return render_template("worker/pallet-supply.html", title="空パレット登録画面")

    # ==================
    # Pallet Supply APIs
    # ==================
    @bp.get("/api/v1/pallet_supply")
    def pallet_supply_list():
        """全ラインのスケジュールと最大列数を取得"""
        lines = pallet_supply_service.list_all()
        return success(data={"lines": lines, "max_pairs": cfg.PALLET_SUPPLY_MAX_PAIRS})

    @bp.get("/api/v1/pallet_supply/<int:line_id>")
    def pallet_supply_get(line_id: int):
        """特定ラインのスケジュールを取得"""
        try:
            line = pallet_supply_service.get_line(line_id)
            return success(data={"line": line})
        except NotFoundError as ex:
            return not_found(str(ex))

    @bp.get("/api/v1/pallet_supply/<line_name>/names")
    def pallet_supply_names(line_name: str):
        """読出モーダル用：過去に使用されたパレット名一覧を取得"""
        try:
            names = pallet_supply_service.list_names(line_name)
            return success(data={"names": names})
        except NotFoundError as ex:
            return not_found(str(ex))

    
    # 追加
    @bp.post("/api/v1/pallet_supply/<line_id>/pair")
    def pallet_supply_add(line_id: str):
        """パレットの追加"""
        body = request.get_json(silent=True) or {}
        try:
            pallet_type = body.get("pallet_type")  # ← ここを採用
            if pallet_type is None:
                return invalid("pallet_type が必要です。")

            line = pallet_supply_service.add_pair(
                line_id=line_id,
                pallet_type=int(pallet_type),
                count=int(body.get("count", 0)),
                before_index=body.get("before_index")
            )
            return success(data={"line": line})
        except (ValueError, TypeError, BadRequest, DomainValidationError, InvalidStateError) as ex:
            return invalid(f"入力エラー: {str(ex)}")
        except StaleWriteError as ex:
            return stale_write(str(ex))
        except NotFoundError as ex:
            return not_found(str(ex))

    # 変更
    @bp.put("/api/v1/pallet_supply/<line_id>/pair/<int:pair_id>")
    def pallet_supply_update(line_id: str, pair_id: int):
        """パレット情報の変更（数量や型式）"""
        body = request.get_json(silent=True) or {}
        try:
            pallet_type = body.get("pallet_type")
            if pallet_type is None:
                return invalid("pallet_type が必要です。")

            line = pallet_supply_service.update_pair(
                line_id=line_id,
                pair_id=pair_id,
                pallet_type=int(pallet_type),
                count=int(body.get("count", 0))
            )
            return success(data={"line": line})
        except (ValueError, TypeError, BadRequest, DomainValidationError, InvalidStateError) as ex:
            return invalid(f"入力エラー: {str(ex)}")
        except StaleWriteError as ex:
            return stale_write(str(ex))
        except NotFoundError as ex:
            return not_found(str(ex))


    @bp.delete("/api/v1/pallet_supply/<line_id>/pair/<int:pair_id>")
    def pallet_supply_delete(line_id: str, pair_id: int):
        """パレットの削除"""
        body = request.get_json(silent=True) or {}
        try:
            line = pallet_supply_service.delete_pair(
                line_id=line_id,
                pair_id=pair_id
            )
            return success(data={"line": line})
        except (ValueError, TypeError) as ex:
            return invalid("リビジョンの形式が正しくありません。")
        except StaleWriteError as ex:
            return stale_write(str(ex))
        except NotFoundError as ex:
            return not_found(str(ex))

    @bp.post("/api/v1/pallet_supply/<line_id>/move_to_group0")
    def pallet_supply_move_to_group0(line_id: str):
        """パレットを先頭（供給準備完了）へ移動"""
        body = request.get_json(silent=True) or {}
        try:
            idx = body.get("pair_index")

            line = pallet_supply_service.move_to_group0(
                line_id=line_id,
                pair_index=int(idx)
            )
            return success(data={"line": line})
        except (ValueError, TypeError) as ex:
            return invalid("入力データの形式が正しくありません。")
        except StaleWriteError as ex:
            return stale_write(str(ex))
        except NotFoundError as ex:
            return not_found(str(ex))
    
    @bp.get("/api/v1/master/pallets")
    def get_master_pallets():
        """Returns the list of all valid pallets for the dropdown"""
        pallets = pallet_supply_service.get_master_pallet_list()
        return success(data={"pallets": pallets})
    
    @bp.post("/api/v1/pallet_supply/pattern/<int:pattern_no>/apply")
    def pallet_supply_apply_pattern(pattern_no: int):
        try:
            lines = pallet_supply_service.apply_pattern(pattern_no)
            return success(data={
                "pattern": pattern_no,
                "lines": lines
            })
        except DomainValidationError as ex:
            return invalid(str(ex))
        except InvalidStateError as ex:
            return invalid(str(ex))
        except Exception as ex:
            return invalid(f"予期しないエラー: {str(ex)}")



    return bp