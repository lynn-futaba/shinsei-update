"""
管理者用コントローラー (AdminController)
作成者: Lynn
----------------------------------
管理画面（ダッシュボード）のバックエンド機能を統括する中心的なコンポーネント。

主な役割:
1. システムモード制御: 自動走行モードの開始・準備、および各個（手動）操作モードへの
   切り替えを管理します。
2. リアルタイム監視データの集約: ロボットの位置、バッテリー、棚の状態、エラー履歴、
   現在のタスク進捗状況などを一括してフロントエンドへ提供します。
3. 手動介入コマンドの仲介: 管理者が画面上から特定のロボットに対して移動やキャンセル、
   棚の持ち上げなどを指示した際、そのリクエストをRMSManualServiceへ伝達します。
4. コールバックの受領: RMS（ロボット管理システム）からの完了報告（Callback）を
   受け取るエンドポイントを提供し、システム内の状態更新をトリガーします。
5. 診断（Diagnostic）機能: 開発・保守用に、RMS APIの生の応答状況を確認する
   デバッグ用エンドポイントを提供します。

工場全体の稼働状況を可視化し、有事の際の制御を行うための「司令塔」です。
"""
# app/controllers/admin_controller.py
from __future__ import annotations
from flask import Blueprint, jsonify, render_template, request, Response
from typing import Any, Dict, List


import json
import time


# Pull in the standard API format helpers
from app.domain.api_response_format import (
    success, bad_request, not_found, invalid, internal_error
)

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
from app.interfaces.api_client.post_rms_api import PostRmsApi

# ログ設定 (名前を付ける)
logger = setup_log(cfg.LOG_FOLDER, cfg.ADMIN_CTRL_LOG_FILE, cfg.BACKUP_DAYS, logger_name="admin_ctrl")

def create_admin_blueprint(container):
    bp = Blueprint("admin_controller", __name__)
    
    # Pull services from container
    manage_service = container.manage_service
    rms_monitoring_service = container.rms_monitoring_service
    rms_manual_service = container.rms_manual_service
    run_initialization_service = container.run_initialization_service
    lift_entrance_service = container.lift_entrance_service
    
    # ------------------------------------------
    # 管理画面について UI/API
    # ------------------------------------------
    @bp.get("/")
    def dashboard():
        # Home/admin dashboard (HTML)
        return render_template("admin/dashboard.html", title="管理画面")
    
    # ---------------------------------------
    # RMS ランタイム状態 (WAREHOUSE) - statuses only
    # ---------------------------------------
    @bp.get("/api/v1/rms_status")
    def rms_status():
        try:
            if not rms_monitoring_service:
                return internal_error(details="RMS Monitoring Service not initialized")
            data = rms_monitoring_service.get_warehouse_status()
            return success(data=data)
        except Exception as ex:
            return internal_error(details=str(ex))

    # -----------------------------
    # RMS モード: 現在値を取得
    # -----------------------------
    @bp.get("/api/v1/get_rms_current_mode")
    def get_rms_current_mode():
        try:
            items = manage_service.get_rms_current_mode()
            payload = [
                {
                    "system_id": e.system_id,
                    "system_name": e.system_name,
                    "mode": 1 if e.mode else 0,           # 1=自動, 0=各個
                    "preparation_ok": 1 if e.preparation_ok else 0,
                    "auto_running": 1 if e.auto_running else 0,
                }
                for e in items
            ]
            return success(data=payload)
        except Exception as ex:
            return internal_error(details=str(ex))

    # -----------------------------
    # RMS モード: 設定（1=自動 / 0=各個）
    # -----------------------------
    @bp.put("/api/v1/rms_set_mode")
    def rms_set_mode_put():
        body = request.get_json(silent=True) or {}
        raw = body.get("mode")
        if raw is None:
            return bad_request("mode is required (0 or 1)")

        try:
            mode = 1 if int(raw) == 1 else 0
        except Exception:
            return invalid("mode must be 0 or 1")

        try:
            new_mode = manage_service.rms_set_mode(mode)
            return success(data={"mode": 1 if new_mode else 0})
        except KeyError:
            return not_found(f"mode not found: {mode}")
        except ValueError as ve:
            return invalid(str(ve))
        except Exception as ex:
            return internal_error(details=str(ex))

    # ---- (Optional fallback) GET /api/v1/rms_set_mode?mode=0|1 ----
    @bp.get("/api/v1/rms_set_mode")
    def rms_set_mode_get():
        mode = request.args.get("mode", type=int)
        if mode is None:
            return bad_request("mode query param is required (0 or 1)")
        try:
            new_mode = manage_service.rms_set_mode(1 if mode == 1 else 0)
            return success(data={"mode": 1 if new_mode else 0})
        except KeyError:
            return not_found(f"mode not found: {mode}")
        except ValueError as ve:
            return invalid(str(ve))
        except Exception as ex:
            return internal_error(details=str(ex))

    # --- Auto mode steps 自動モード、起動準備ボタン ---
    @bp.post("/api/v1/rms_auto_prepare")
    def rms_auto_prepare():
        try:
            init_service = run_initialization_service
            init_result = init_service.initialization()  # ← これが正しい呼び方 (Flaskルートは呼ばない)
            
            # --- 従来の auto_prepare ---
            item = manage_service.rms_auto_prepare()
            return success(data={
                "initialization": init_result,
                "step": "prepare",  
                "system_id": item.system_id,
                "system_name": item.system_name,
                "mode": 1 if item.mode else 0,
                "preparation_ok": 1 if item.preparation_ok else 0,
                "auto_running": 1 if item.auto_running else 0,
            })
        except Exception as ex:
            return internal_error(details=str(ex))

    # --- 自動モード、起動ボタン ---
    @bp.post("/api/v1/rms_auto_start")
    def rms_auto_start():
        try:
            item = manage_service.rms_auto_start()
            return success(data={
                "step": "start",  
                "system_id": item.system_id,
                "system_name": item.system_name,
                "mode": 1 if item.mode else 0,
                "preparation_ok": 1 if item.preparation_ok else 0,
                "auto_running": 1 if item.auto_running else 0,
            })
        except Exception as ex:
            return internal_error(details=str(ex))

    @bp.post("/api/v1/rms_auto_run")
    def rms_auto_run():
        try:            
            item = manage_service.rms_auto_run()
            return success(data={
                "step": "running",  
                "system_id": item.system_id,
                "system_name": item.system_name,
                "mode": 1 if item.mode else 0,
                "preparation_ok": 1 if item.preparation_ok else 0,
                "auto_running": 1 if item.auto_running else 0,
            })
        except Exception as ex:
            return internal_error(details=str(ex))
    
    # -----------------------------
    # 各個操作モード
    # -----------------------------
    @bp.post("/api/v1/rms_manual_move")
    def rms_manual_move():
        try:
            data = request.get_json(silent=True) or {}
            if "cell_code" not in data and "cellcode" in data:
                data["cell_code"] = data["cellcode"]

            missing = [k for k in ("robot_id", "cell_code") if k not in data]
            if missing:
                return bad_request(message="Bad Request", details=f"不足: {', '.join(missing)}")

            rms_manual_service.move(robot_id=str(data["robot_id"]), cell_code=str(data["cell_code"]))
            return success(data={"condition": "success"}, message="OK")
        except Exception as e:
            logger.error(f"Manual Move Error: {e}")
            return internal_error(details=str(e))

    @bp.post("/api/v1/rms_manual_cancel")
    def rms_manual_cancel():
        try:
            data = request.get_json(silent=True) or {}
            if "cell_code" not in data and "cellcode" in data:
                data["cell_code"] = data["cellcode"]

            missing = [k for k in ("robot_id", "cell_code") if k not in data]
            if missing:
                return bad_request(message="Bad Request", details=f"不足: {', '.join(missing)}")

            rms_manual_service.cancel(robot_id=str(data["robot_id"]), cell_code=str(data["cell_code"]))
            return success(data={"condition": "success"}, message="OK")
        except Exception as e:
            logger.error(f"Cancel Error: {e}")
            return internal_error(details=str(e))

    @bp.post("/api/v1/rms_manual_load")
    def rms_manual_load():
        try:
            data = request.get_json(silent=True) or {}
            missing = [k for k in ("robot_id", "shelf_id", "cell_code") if k not in data]
            if missing:
                return bad_request(message="Bad Request", details=f"不足: {', '.join(missing)}")

            rms_manual_service.load(
                robot_id=str(data["robot_id"]),
                shelf_code=str(data["shelf_id"]),
                cell_code=str(data["cell_code"]),
                angle=int(data.get("angle", 0))
            )
            return success(data={"condition": "success"}, message="OK")
        except Exception as e:
            return internal_error(details=str(e))

    @bp.post("/api/v1/rms_manual_shelf")
    def rms_manual_shelf():
        try:
            data = request.get_json(silent=True) or {}
            if "shelf_id" not in data:
                return bad_request(details="shelf_id is required")
            rms_manual_service.remove_shelf(shelf_code=str(data["shelf_id"]))
            return success(data={"condition": "success"}, message="OK")
        except Exception as e:
            return internal_error(details=str(e))
    
    @bp.get("/api/v1/rms_map_monitor")
    def rms_map_monitor():
        if rms_monitoring_service is None:
            return internal_error(details="Monitoring service unavailable")

        try:
            raw = rms_monitoring_service.get_display_data() or {}

            # ---- HARD normalize siza / size (no tuple leaks allowed) ----
            w, h = 1200, 800  # safe defaults

            siza_raw = raw.get("siza")

            if isinstance(siza_raw, dict):
                w = int(siza_raw.get("x", w))
                h = int(siza_raw.get("y", h))

            elif isinstance(siza_raw, (list, tuple)):
                if len(siza_raw) >= 2:
                    w = int(siza_raw[0])
                    h = int(siza_raw[1])

            # force final shape
            w = int(w) if w > 0 else 1200
            h = int(h) if h > 0 else 800

            payload = {
                "size": [w, h],                 # always list[2]
                "siza": {"x": w, "y": h},       # always dict
                "cells": list(raw.get("cells") or []),
                "kotatsus": list(raw.get("kotatsus") or []),
                "amrs": list(raw.get("amrs") or []),
            }

            return success(data=payload)

        except Exception as ex:
            logger.exception("Controller: rms_map_monitor failed")
            return internal_error(details=str(ex))


    @bp.get("/api/v1/get_map")
    def get_map():
        try:
            payload = rms_monitoring_service.get_map()
            return success(data=payload)
        except Exception as ex:
            return internal_error(details=str(ex))

    @bp.get("/api/v1/get_line_state_list")
    def get_line_state_list():
        try:
            items = manage_service.get_line_state_list()
            lines_map = {}

            for e in items:
                line_name = e.line_name

                # Initialize per line (once)
                if line_name not in lines_map:
                    lines_map[line_name] = {
                        "line_id": e.line_id,
                        "line_name": line_name,
                        "transport_permission": bool(e.transport_permission),
                        # index 0 => 間口1 (input), index 1 => 間口2 (wait)
                        "pallets": ["None", "None"]
                    }

                # Place pallet into correct maguchi slot
                if e.maguchi_no in (1, 2):
                    lines_map[line_name]["pallets"][e.maguchi_no - 1] = (
                        e.pallet_name if e.pallet_name else "None"
                    )

            # Convert dict → list for JSON response
            return success(data=list(lines_map.values()))

        except Exception as ex:
            return internal_error(details=str(ex))
    
    @bp.get("/api/v1/get_error_list")
    def get_error_list():
        try:
            # 1. Sync
            boot_ts = request.args.get("boot_ts", "2024-01-01 00:00:00")
            manage_service.sync_rms_errors(rms_boot_ts=boot_ts)

            # 2. Fetch the data (This is now a DICT: {"local": [...], "athena": [...]})
            data_dict = manage_service.get_error_list()
            
            def format_item(e):
                return {
                    "error_num": e.error_num,
                    "error_code": e.error_code,
                    "error_summary": e.error_summary,
                    "error_datetime": e.error_datetime.strftime("%Y/%m/%d %H:%M:%S") if e.error_datetime else "-",
                    "error_level": e.error_level,
                    "error_category": e.error_category,
                    "error_description": e.error_description,
                    "error_operation": e.error_operation,
                    "is_completed": e.is_completed,
                }

            # 3. Combine and sort or process directly from the dict
            # We extract the lists from the dictionary directly
            local_raw = data_dict.get("local", [])
            athena_raw = data_dict.get("athena", [])

            payload = {
                "local": [format_item(e) for e in local_raw],
                "athena": [format_item(e) for e in athena_raw]
            }
            
            return success(data=payload)

        except Exception as ex:
            # This will now stop throwing the 'str' attribute error
            return internal_error(details=str(ex))
    
    @bp.post("/api/v1/error/reset")
    def reset_error():
        payload = request.get_json(force=True, silent=False)

        try:
            source = payload.get("source")
            error_num = payload.get("error_num")

            if not source or error_num is None:
                return bad_request("source and error_num are required")

            # ✅ normalize here (important)
            error_num = int(error_num)

            manage_service.reset_error(source, error_num)
            return success(message="Error reset completed")

        except ValueError as ve:
            # input / not-found errors
            return bad_request(str(ve))

        except Exception as ex:
            # ✅ log the REAL reason
            logger.exception("reset_error failed")
            return internal_error(details=str(ex))
    
    def get_int_arg(name, default):
        raw = request.args.get(name, "")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @bp.get("/api/v1/get_task_status")
    def get_task_status():
        try:
            minutes = get_int_arg("minutes", 1)
            limit   = get_int_arg("limit",  100)
            page    = get_int_arg("page",   1)

            items = manage_service.get_task_status(
                minutes=minutes,
                limit=limit,
                page=page
            )

            payload = [{
                "task_id": e.task_id,
                "robot_id": e.robot_id,
                "status": e.status,
                "task_type": e.task_type,
                "destination": e.dest_cell,
                "instruction": e.instruction,
                "updated_date": e.updated_date
            } for e in items]

            return success(data=payload)

        except Exception as ex:
            logger.exception("Failed to fetch task status")
            return internal_error(details=str(ex))
    
    @bp.route("/api/v1/rms/callback", methods=["POST", "OPTIONS"])
    def robot_task_callback():

        logger.warning(
            "[RMS CALLBACK ENTER] method=%s path=%s origin=%s remote=%s",
            request.method,
            request.path,
            request.headers.get("Origin"),
            request.remote_addr
        )

        # ✅ Preflight (CORS) 
        # RMSとWCSのURL IP_Addressが違いましたら問題があるのでCORSの許可をrequestに追加
        if request.method == "OPTIONS":
            logger.warning("[RMS CALLBACK OPTIONS] Preflight received ✔")

            return Response(
                status=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
            )

        # ✅ Service availability
        svc = getattr(container, "rms_callback_service", None)
        if svc is None:
            logger.error("[RMS CALLBACK ERROR] rms_callback_service unavailable ❌")

            return Response(
                '{"error":"rms_callback_service unavailable"}',
                status=500,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # ✅ Raw body logging
        raw_body = request.get_data(as_text=True)
        logger.warning("[RMS CALLBACK RAW BODY] %s", raw_body)

        # ✅ JSON parsing
        try:
            payload = json.loads(raw_body)
            logger.warning("[RMS CALLBACK JSON PARSED] msgType=%s id=%s",
                        payload.get("msgType"),
                        payload.get("id"))
        except Exception:
            logger.exception("[RMS CALLBACK ERROR] JSON parse failed ❌")
            payload = {}

        # ✅ Processing + ACK
        try:
            logger.warning("[RMS CALLBACK PROCESS] Calling service…")
            ack = svc.process_callback_and_build_ack(payload)
            logger.warning("[RMS CALLBACK PROCESS] Service completed ✔")
        except Exception:
            logger.exception("[RMS CALLBACK ERROR] Service failed, fallback ACK ⚠")
            ack = svc._callback_api.build_ack_from_request(payload)

        # ✅ ACK serialization
        ack_json = json.dumps(ack, ensure_ascii=False, separators=(",", ":"))
        logger.warning("[RMS CALLBACK ACK OUT] %s", ack_json)

        return Response(
            response=ack_json,
            status=200,
            content_type="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
    
    # @bp.get("/api/v1/get_lift_entrance")
    # def get_lift_entrance():
    #     try:
    #         # 1. Fetch from Service
    #         payloads = manage_service.get_lift_entrance()

    #         # 2. Map to Dictionary (DEFENSIVE)
    #         data = []
    #         for e in payloads:
    #             # ✅ pallet_id can be "", None, or numeric
    #             raw_pallet_id = getattr(e, "pallet_id", None)

    #             try:
    #                 pallet_id = int(raw_pallet_id) if raw_pallet_id not in (None, "", "null") else None
    #             except (TypeError, ValueError):
    #                 pallet_id = None

    #             data.append({
    #                 "maguchi_name": e.maguchi_name,      # 例: "間口1"
    #                 "line_name": e.line_name,            # 例: "T65"
    #                 "pallet_name": e.pallet_name,        # 例: "300インナー" | "完成品搬入待ち"
    #                 "pallet_id": pallet_id,              # ✅ ALWAYS safe
    #                 "transport_status": e.transport_status  # READY | WAIT | COMPLETE | WORK
    #             })

    #         # 3. Return Success
    #         return success(data=data)

    #     except Exception as ex:
    #         logger.exception("Failed to fetch lift entrance")
    #         return internal_error(details=str(ex))
    
    @bp.get("/api/v1/get_lift_entrance")
    def get_lift_entrance():
        try:
            # ✅ DIRECTLY call service (no manage_service)
            payloads = lift_entrance_service.list()

            data = []
            for e in payloads:
                raw_pallet_id = e.get("pallet_id")

                try:
                    pallet_id = int(raw_pallet_id) if raw_pallet_id not in (None, "", "null") else None
                except (TypeError, ValueError):
                    pallet_id = None

                data.append({
                    "maguchi_name": e.get("maguchi_name"),
                    "line_name": e.get("line_name"),
                    "pallet_name": e.get("pallet_name"),
                    "pallet_id": pallet_id,
                    "transport_status": e.get("transport_status"),
                })

            return success(data=data)

        except Exception as ex:
            logger.exception("Failed to fetch lift entrance")
            return internal_error(details=str(ex))
        

    # ライン状態　（有効・無効）
    @bp.post("/api/v1/line_state/permission")
    def line_state_permission():
        """
        Request:  { "line_id": <int or string> }  # accepts numeric ID or name/code
        Response: success({ line_id, transport_permission })
        """
        payload = request.get_json(silent=True) or {}
        logger.info("[line_state/permission] payload=%r", payload)

        raw = payload.get("line_id")
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            return bad_request("line_id is required")

        # Normalize: int if numeric, else keep as string
        s = str(raw).strip()
        line_id_or_name = int(s) if s.isdigit() else s

        try:
            # Primary attempt: whatever your service currently expects (id or name)
            new_allowed = manage_service.toggle_transport_permission(line_id_or_name)
            return success(data={"line_id": s, "transport_permission": bool(new_allowed)})

        except KeyError:
            # Fallback: resolve via list, then call service with the “right” key
            try:
                items = manage_service.get_line_state_list()
            except Exception:
                items = []

            # Find row by either numeric id or by name/code
            row = next((
                e for e in items
                if str(e.line_id) == s or str(e.line_name) == s
            ), None)

            if not row:
                logger.warning("[line_state/permission] unknown line_id=%s (not in current list)", s)
                return not_found(f"line_id not found: {s}")

            # Try again with the *id* first, then with the *name*
            for key in (row.line_id, row.line_name):
                try:
                    new_allowed = manage_service.toggle_transport_permission(key)
                    return success(data={"line_id": s, "transport_permission": bool(new_allowed)})
                except KeyError:
                    continue

            logger.warning("[line_state/permission] could not toggle using id=%r or name=%r", row.line_id, row.line_name)
            return not_found(f"line_id not found: {s}")
        
    @bp.post("/api/v1/rms_manual_fetch")
    def rms_manual_fetch():
        """棚持ち移動指示"""
        try:
            data = request.get_json(silent=True) or {}

            # Validation
            missing = [k for k in ("robot_id", "shelf_id", "cell_code") if k not in data]
            if missing:
                return bad_request(
                    message="Bad Request",
                    details=f"必須パラメータが不足しています: {', '.join(missing)}"
                )

            # Normalize
            robot_id = str(data["robot_id"])
            shelf_code = str(data["shelf_id"])
            cell_code = str(data["cell_code"])
            try:
                angle = int(data.get("angle", 0))
            except Exception:
                return bad_request(message="Bad Request", details="angle は整数で指定してください")

            # Service call
            rms_manual_service.fetch(
                robot_id=robot_id,
                shelf_code=shelf_code,
                cell_code=cell_code,
                angle=angle,
            )

            return success(data={"condition": "success"}, message="OK")

        except Exception as e:
            logger.error(f"操作エラー: {e}")
            return internal_error(message="Internal Error", details=f"操作エラー: {e}")
    
    # ---------------------------------------
    # Combined Error List (WCS + Athena RMS)
    # ---------------------------------------
    @bp.get("/api/v1/get_all_errors")
    def get_all_errors():
        """
        Fetches combined errors. 
        Note: You can pass the RMS restart time as a query param or 
        let the service handle the logic.
        """
        try:
            # Get the boot time from query params, or default to a safe past date
            boot_ts = request.args.get("boot_ts", "2024-01-01 00:00:00")
            
            # Call the service method we discussed
            combined_data = manage_service.sync_and_get_all_errors(rms_boot_ts=boot_ts)
            
            return success(data=combined_data)
        except Exception as ex:
            logger.exception("Failed to fetch combined errors")
            return internal_error(details=str(ex))
    
    # TODO: どこから呼びますか？
    @bp.post("/api/v1/rms_initialize")
    def rms_initialize():
        try:
            svc = run_initialization_service
            result = svc.initialization()
            return success(data=result)
        except Exception as ex:
            logger.exception("Initialization failed")
            return internal_error(details=str(ex))
        
    return bp