"""
RMSコールバックサービス (RMSCallbackService)
作成者: Lynn
----------------------------------
ロボット管理システム (RMS) から通知される実行ステータスを受信・処理するサービス。

主な役割:
1. 受信バリデーション: 送信されてきたJSONの構造（taskId, taskStatus等）を検証し、
   システムが定義しているステータス（NEW, EXECUTING, COMPLETED等）に合致するか確認します。
2. イベントログの保存: 受信した生のJSONメッセージをそのままDB（イベントログ）に保存し、
   後からの調査（監査ログ）を可能にします。
3. 最新状態の更新 (Snapshot Upsert): 各タスクの最新ステータスをDBに反映します。
4. 応答生成 (ACK): RMSに対し、正常に受信したことを示す応答パケットを生成して返します。

ロボットの「今」の状態をシステムに同期させるための、リアルタイム性が求められる
極めて重要なコンポーネントです。
"""
# app/services/rms_callback_service.py
from __future__ import annotations
from typing import Dict, Any
import time

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定 (名前を付ける)
logger = setup_log(cfg.LOG_FOLDER, cfg.RMS_CALLBACK_SEV_LOG_FILE, cfg.BACKUP_DAYS, logger_name="rms_callback_svc")

ALLOWED_STATUSES = {"NEW", "ASSIGNED", "EXECUTING", "COMPLETED", "CANCELED"}

# Optional soft-allow lists (log unknowns; do not fail)
ALLOWED_TASK_TYPES = {
    "GO_SOMEWHERE_TO_STAY","DELIVER_SHELF_TO_STATION","DELIVER_SHELF","DELIVER_NEW_SHELF",
    "GO_WORK","CARRY_PACKAGE","DELIVER_PALLET","DELIVER_BOX","GO_WORK_ORDER_TO_PERSON",
    "MOVE_SHELF","GO_MAINTAIN_TO_STAY","GO_CHARGE_YOURSELF","GO_CIRCLE","GO_TO_INSPECTION"
}

ALLOWED_INSTRUCTIONS = {
    "NONE","GO_FETCH","GO_TURN","GO_RETURN","CANCEL","CANCEL_INSTRUCTION","GO_NEXT","PRIORITY_SET",
    "CLEAR_WAITPOINT","GO_RECEIVE","GO_DROP","ALLOW_ENTER_ELEVATOR","ALLOW_LEAVE_ELEVATOR",
    "UPDATE_PARCEL","UPDATE_BOX","FINISHED"
}

ALLOWED_PHASES = {
    "GO_FETCHING","SHELF_FETCHED","GO_DELIVERING","QUEUING","SHELF_ARRIVED","GO_RETURN","SHELF_TURNING",
    "MOVING","CHARGING","ARRIVED_RECEIVE","ARRIVED_DROP","ARRIVED_WAIT_POINT","LEAVING_WAIT_POINT",
    "RECEIVE_FINISH","DROP_FINISH","BOX_FETCHED","BOX_ARRIVED","ARRIVED_ELEVATOR_ENTRY","ENTERED_ELEVATOR",
    "LEAVED_ELEVATOR","ARRIVED","FETCHED"
}

class RMSCallbackService:
    """
    Validates RMS callback payloads, persists event + current status,
    and builds the ACK JSON to return to RMS.
    """

    def __init__(self, wcs_sql, callback_api, db_name: str = "futaba_ok2_shippment"):
        self._sql = wcs_sql
        self._db_name = db_name
        self._callback_api = callback_api

    
    def process_callback_and_build_ack(self, msg: Dict[str, Any]) -> Dict:
        try:
            self.handle_robot_task_callback(msg)
        except Exception:
            # ❗ Never stop ACK
            logger.exception("[callback] processing failed, but ACK returned")
        return self._callback_api.build_ack_from_request(msg)

    def handle_robot_task_callback(self, msg: Dict[str, Any]) -> None:
        
        msg_type = str(msg.get("msgType") or "")
        if "RobotTask" not in msg_type:
            logger.warning("[callback] Unknown msgType: %s", msg_type)
            return  # ✅ still ACK

        req = msg.get("request") or {}
        header = req.get("header") or {}
        body = req.get("body") or {}

        request_id  = str(header.get("requestId") or "")
        task_id     = str(body.get("taskId") or "")
        robot_id    = str(body.get("robotId") or "")
        task_status = str(body.get("taskStatus") or "").upper()
        task_phase  = str(body.get("taskPhase") or "")
        # dest_cell   = str(body.get("destCellCode") or "")
        
        _raw_dest = body.get("destCellCode")
        dest_cell = None if _raw_dest in (None, "") else int(_raw_dest)

        task_type   = str(body.get("taskType") or "")
        instruction = str(body.get("instruction") or "")
        ts          = int(time.time())

        if not task_id or not task_status:
            logger.warning(
                "[callback] Incomplete payload (ignored but ACKed): taskId=%s status=%s",
                task_id, task_status
            )
            return

        # Soft validations (unchanged)
        if ALLOWED_STATUSES and task_status not in ALLOWED_STATUSES:
            logger.warning("[callback] Unknown taskStatus: %s", task_status)
        if task_type and task_type not in ALLOWED_TASK_TYPES:
            logger.warning("[callback] Unknown taskType: %s", task_type)
        if instruction and instruction not in ALLOWED_INSTRUCTIONS:
            logger.warning("[callback] Unknown instruction: %s", instruction)
        if task_phase and task_phase not in ALLOWED_PHASES:
            logger.warning("[callback] Unknown taskPhase: %s", task_phase)

        # 3) Event log: store FULL inbound JSON (not only body)
        try:
            if hasattr(self._sql, "insert_task_event_json"):
                self._sql.insert_task_event_json(
                    task_id=task_id,
                    request_id=request_id,
                    event_json=msg,   # full message
                    ts=ts
                )
            else:
                logger.warning("[callback] No insert_task_event[_json] on repository")
        except Exception:
            logger.exception("[callback] event insert failed for task_id=%s", task_id)

        # 4) Snapshot upsert (must succeed or raise to force RMS retry)
        try:
            
            if dest_cell == "":
                dest_cell = None

            if hasattr(self._sql, "upsert_task_status"):
                self._sql.upsert_task_status(
                    task_id=task_id,
                    status=task_status,
                    phase=task_phase,
                    robot_id=robot_id,
                    dest_cell=dest_cell,
                    ts=ts,
                    task_type=task_type,
                    instruction=instruction
                )
            elif hasattr(self._sql, "update_task_status"):
                self._sql.update_task_status(task_id, task_status)
            else:
                logger.warning("[callback] No upsert/update method on WCSSQLQuery")
        except Exception:
            logger.exception("[callback] status upsert failed for task_id=%s", task_id)
            raise

        logger.info(
            "[callback] task=%s robot=%s status=%s phase=%s dest=%s type=%s instr=%s",
            task_id, robot_id, task_status, task_phase, dest_cell, task_type, instruction
        )
