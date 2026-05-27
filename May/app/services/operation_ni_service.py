"""
自動搬送運用サービス（OperationNiService）
作成者: Lynn
---------------------------------------------
単一台のAMRを使用した、順次実行型の搬送制御サービス。

本サービスはすべての搬送工程を「直列（順番どおり）」に実行し、
前工程の完了を確認してから次工程へ進む運用を行う。

【実行シーケンス（固定順）】
順次 ➀-1 ⇒ ➀-2 ⇒ ➀-4 ⇒ ➀-3

  ➀-1 完成品 → TEMP
  ➀-2 空パレット → WAIT
  ➀-4 TEMP → 完成品出口
  ➀-3 WAIT → 投入口

主な役割:
1. 搬送手順の順序制御:
   - 並列処理を行わず、1つずつ確実に工程を進める。
2. 搬送状態の管理:
   - セル・コタツ・パレットの予約と解放を適切に制御。
3. 安全性重視の設計:
   - 各工程で異常が発生した場合は、即時処理を中断。
4. 疎結合設計:
   - RMS操作は OperationRMS に委譲し、本クラスは搬送手順の制御に専念する。

本クラスは、搬送をシンプルかつ確実に行う運用モードで使用される。
"""
# app/services/operation_ni_service.py

import time
import threading
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
from app.interfaces.api_client.operation_rms_api import OperationRMS

logger = setup_log(
    cfg.LOG_FOLDER, cfg.OPERATION_NI_SEV_LOG_FILE, cfg.BACKUP_DAYS,
    logger_name="operation_ni_svc"
)

# =====================================================================
#  FULL OPERATION NI SERVICE 完全運用サービス
# =====================================================================
class OperationNiService:
    """
    ライン単位の搬送作業を実行するサービス
    ・完成品搬送
    ・空パレット搬送
    ・セル/コタツの更新
    """

    def __init__(self, wcs_sql, iot_repo):
        self.op_rms = OperationRMS(wcs_sql)
        self.iot_repo = iot_repo

    # =====================================================================
    # 空パレットが使用可能になるまで待機
    # =====================================================================
    def _get_empty_resources(self, line_id):
        return self.op_rms.get_empty_carry_data(line_id)
    
    
    def _wait_permission(self, line_id: int, permission_signal_id: int, interval=1):
        logger.info(
            "⏳ Waiting for permission_flag ON (line_id=%s, signal_id=%s)",
            line_id, permission_signal_id
        )

        permission_acked = False

        while True:
            try:
                # 1️⃣ Wait for【WCS t_line_statusのpermition==1 】
                if self.op_rms.get_permition(line_id):

                    # 2️⃣ ACK PLC (SET t_output = 1) — only once
                    if not permission_acked:
                        self.iot_repo.update_t_output_value(permission_signal_id)
                        permission_acked = True
                        logger.info(
                            "✅ permission_flag ON → t_output ACK sent (signal_id=%s)",
                            permission_signal_id
                        )

                    return True

            except Exception:
                logger.exception("[OPS] permission wait failed")

            time.sleep(interval)

    # =================================================================
    # ➀-1 完成品,【CELL】INPUT → TEMP (complete_carry_step)
    # =================================================================
    def complete_carry_step(self, cells, kot, pal):
        logger.info("➀-1 完成品,【CELL】INPUT → TEMP 開始")
        
        # ✅ 2) State update
        # セルとコタツの状態を更新
        if not self.op_rms.update_state(cells["temp"], kot["complete"]):
            logger.error("[OPS] ➀-1 update_state 失敗")
            return None, False

        # ✅ 3) Task execution
        # 完成品を投入間口から一時置き場に搬送のスレット登録
        res, task_id, start_cell = self.op_rms.send_task(
            step="temp_carry",
            start_cell=cells["input"],
            dest_cell=cells["temp"],
            kotatsu=kot["complete"],
            pallet=pal["complete"],
            task_number=None,
            is_continue=True
        )
        dest_cell = cells["temp"].id

        if not res:
            logger.error("[OPS] ➀-1 send_task 失敗")
            return None, False

        logger.info(f"[OPS] ➀-1 send_task 成功, task_id={task_id}, dest_cell={dest_cell}")

        # ✅ 3) Wait for completion
        ok, task_id, task = self.op_rms.wait_for_task(
            task_id,
            start_cell,
            dest_cell_id=cells["temp"].id,
            kotatsu_id=kot["complete"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-1 wait_for_task 失敗")
            return None, False

        # ✅ 5) Clear update
        # セルとコタツの状態を占有をクリアする処理
        logger.info(f"[OPS] ➀-1 搬送成功, task_id={task_id}, dest_cell={dest_cell}")
        self.op_rms.clear_state(cells["input"], cells["temp"], kot["complete"])
        return task_id, True
    
    # =================================================================
    # ➀-2【CELL】WAIT → INPUT 投入口 (input_carry_step)
    # =================================================================
    def input_carry_step(self, cells, kot, pal, task_id, line_id):
        logger.info("➀-2【CELL】WAIT → 投入口 開始")

        # ✅ 2) State update
        # セルとコタツの状態を更新
        if not self.op_rms.update_state(cells["input"], kot["wait"]):
            logger.error("[OPS] ➀-2 update_state 失敗")
            return None, False

        # ✅ 3) Task execution
        # 待機パレットを投入間口に搬送するスレット登録
        res, new_task_id, start_cell = self.op_rms.send_task(
            step="input_carry",
            start_cell=cells["wait"],
            dest_cell=cells["input"],
            kotatsu=kot["wait"],
            pallet=pal["wait"],
            task_number=task_id,
            is_continue=True
        )
        dest_cell = cells["input"].id

        if not res:
            logger.error("[OPS] ➀-2 send_task 失敗")
            return None, False

        logger.info(f"[OPS] ➀-2 send_task 成功, task_id={new_task_id}, dest_cell={dest_cell}")

        # ✅ 4) Wait for completion
        ok, _, task = self.op_rms.wait_for_task(
            new_task_id,
            start_cell,
            dest_cell_id=cells["input"].id,
            kotatsu_id=kot["wait"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-2 wait_for_task 失敗")
            return None, False

        # ✅ 5) Clear state
        logger.info(f"[OPS] ➀-2 搬送成功, task_id={task_id}, dest_cell={dest_cell}")
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cells["wait"], cells["input"], kot["wait"])
        # ラインの状態更新
        self.op_rms.update_line_pallet(line_id, pal["wait"].id)
        # パレットの時間登録
        self.op_rms.update_pallet_time(pal["wait"].id, "input_time")
        return new_task_id, True
    
    # =================================================================
    # ➀-3【CELL】TEMP → 空パレット (ship_carry_step)
    # =================================================================
    def ship_carry_step(self, cells, kot, pal, task_id, line_id):
        logger.info("➀-3【CELL】TEMP → 空パレット 開始")
        # ✅ 1) State update
        # 完成品を一時置き場からリフト間口に移動させる処理
        # if not self.op_rms.update_state(cells["complete"], kot["complete"]):
        #     logger.error("[OPS] ➀-3 update_state 失敗")
        #     # return None, False
        # logger.info(f"id:{cells['complete'].id}, kotatsu{cells['complete'].kotatsu_id}, 占有:{cells['complete'].is_occupied}, 搬送:{cells['complete'].carrier}")
        
        # ✅ 2) Task execution
        # 完成品を一時置き場から回転セルに搬送するスレット登録
        res, task_id, start_cell = self.op_rms.send_go(
            step="auxiliary",
            start_cell=cells["temp"],
            dest_cell=cells["temp"],
            kotatsu=kot["complete"],
            pallet=pal["complete"],
            task_number=task_id,
            is_continue=True,
        )

        # リフト間口を検出するまでループ処理
        while True:
            t_cells, t_kot, t_pal = self.op_rms.get_carry_data(line_id)
            if t_cells["complete"] is not None:
                cells["complete"] = t_cells["complete"]
                break

        # 完成品を一時置き場からリフト間口に移動させる処理
        if not self.op_rms.update_state(cells["complete"], kot["complete"]):
            logger.error("[OPS] ➀-3 update_state 失敗")
            # return None, False
        logger.info(f"id:{cells['complete'].id}, kotatsu{cells['complete'].kotatsu_id}, 占有:{cells['complete'].is_occupied}, 搬送:{cells['complete'].carrier}")

        # ✅ 3) Task execution
        # 完成品を回転セルからリフト間口に搬送するスレット登録
        res, task_id, start_cell = self.op_rms.send_task(
            step="ship_carry",
            start_cell=cells["temp"],
            dest_cell=cells["complete"],
            kotatsu=kot["complete"],
            pallet=pal["complete"],
            task_number=task_id,
            is_continue=True,
            ratation_cell=cells["turn"]
        )

        if not res:
            logger.error("[OPS] ➀-3 send_task 失敗")
            # return None, False

        # ✅ 4) Wait for completion
        ok, task_id, task = self.op_rms.wait_for_task(
            task_id,
            start_cell,
            dest_cell_id=cells["complete"].id,
            kotatsu_id=kot["complete"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-3 wait_for_task 失敗")
            return None, False

        # ✅ 5) Clear state
        logger.info(f"[OPS] ➀-3 搬送成功, task_id={task_id}, dest_cell={cells['complete'].id}")
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cells["temp"], cells["complete"], kot["complete"])
        return task, True, task_id

    # =================================================================
    # ➀-4【CELL】空パレット → WAIT (empty_carry_step)
    # =================================================================
    def empty_carry_step(self, line_id, task_id, cells):
        logger.info("➀-4【CELL】空パレット → WAIT 開始")

        while True:
            cell, kot, pal = self._get_empty_resources(line_id)  # 空パレット取得
            if cell is not None:
                logger.info(f"搬送するコタツ: {kot}")
                break
            time.sleep(1)

        # ✅ 2) State update
        # セルとコタツの状態を更新
        if not self.op_rms.update_state(cells["wait"], kot):
            logger.error("[OPS] ➀-4 update_state 失敗")
            return None, False

        # ✅ 3) send_task now returns start_cell
        res, task_id, start_cell = self.op_rms.send_task(
            step="empty_carry",
            start_cell=cell,
            dest_cell=cells["wait"],
            kotatsu=kot,
            pallet=pal,
            task_number=task_id,
            is_continue=False,
            ratation_cell=cells["turn"]
        )

        if not res:
            logger.error("[OPS] ➀-4 send_task 失敗")
            return None, False

        # ✅ 4) Wait for completion
        ok, _, task = self.op_rms.wait_for_task(
            task_id,
            start_cell,
            dest_cell_id=cells["wait"].id,
            kotatsu_id=kot.id,
        )

        if not ok:
            logger.error("[OPS] ➀-4 wait_for_task 失敗")
            return None, False

        # ✅ 5) Clear state
        logger.info(f"[OPS] ➀-4 搬送成功, task_id={task_id}, dest_cell={cells['wait'].id}")
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cell, cells["wait"], kot)
        self.op_rms.set_lift_plat(task_id, cell, True)
        # パレットの時間登録
        self.op_rms.update_pallet_time(pal.id, "supply_time")
        return task_id, True
    
    # =============================================================================================
    # Operation開始（順次実行）Sequence、AMR 1台(タスク継続で、AMR1台を拘束)
    # =============================================================================================
    def start_operation(self, line_id: int):
        logger.info(f"🚀 OperationNiService START line {line_id}")

        # --------------------------------------------------
        # STEP 1: Get Line Operation　搬送要求を確認
        # --------------------------------------------------
        if not self.op_rms.get_operation(line_id):
            logger.info("Operation requestなし")

        # --------------------------------------------------
        # STEP 2: Get carry data (cell / kotatsu / pallet)　
        # --------------------------------------------------
        try:
            cells, kot, pal = self.op_rms.get_carry_data(line_id)
        except Exception:
            logger.exception(
                "[OP][RMS] get_carry_data failed "
                "(line_id=%s, step=complete_carry)",
                line_id
            )

        logger.info(
            """
            [OP get_carry_data] 作業開始
            セル: input=%s, temp=%s, complete=%s, wait=%s
            コタツ: complete=%s, wait=%s
            パレット: complete=%s, wait=%s
            """,
            getattr(cells["input"], "id", None), getattr(cells["temp"], "id", None), getattr(cells["complete"], "id", None), getattr(cells["wait"], "id", None),
            getattr(kot["complete"], "id", None), getattr(kot["wait"], "id", None),
            getattr(pal["complete"], "id", None), getattr(pal["wait"], "id", None),
        )

        # ----------------------------------------------------------------------
        # STEP 3: Operation実行順
        # ----------------------------------------------------------------------
        # ➀-1 完成品, 【CELL】INPUT → TEMP (complete_carry_step)
        temp_task, ok1 = self.complete_carry_step(cells, kot, pal)
        if not ok1:
            logger.error("[OP2] ➀-1 完成品 → TEMP complete_carry_step: 失敗")
            return

        # ➀-2【CELL】WAIT → INPUT 投入口 (input_carry_step)
        input_task, ok2 = self.input_carry_step(cells, kot, pal, temp_task, line_id)
        if not ok2:
            logger.error("[OP2] ➀-2 WAIT → INPUT 投入口 input_carry_step: 失敗")
            return
        
        
        # ==================================================
        # ✅ WAIT FOR PERMISSION
        # ==================================================
        #搬送許可信号を取得
        permission_signal_id = cfg.PERMISSION_SIGNAL_BY_LINE.get(line_id)
        logger.info("✅config設定から signal_id: %s", permission_signal_id)
        if not permission_signal_id:
            logger.error("❌ No PERMISSION signal mapping for line_id=%s", line_id)
            # return

        # 搬送許可の信号を待機
        self._wait_permission(line_id, permission_signal_id)
        # ==================================================

        # ➀-3【CELL】TEMP → 空パレット (ship_carry_step)
        ship_task, ok3, ship_task_id = self.ship_carry_step(cells, kot, pal, input_task, line_id)
        logger.info(f"[OP2] ➀-3 TEMP → 空パレット ship_carry_step: {ship_task}")
        if not ok3:
            logger.error("[OP2] ➀-3 TEMP → 空パレット ship_carry_step: 失敗")
            return

        # 搬送完了でリフトプラットをWORKにする処理
        if ship_task is not None:
            self.op_rms.set_lift_plat(ship_task, cells["complete"], False)
            logger.info("✅ OperationNiService ライン COMP完了")
        else:
            logger.info("⏭ Step ➀‑3 skipped — lift plat not updated, retry next scan")
            return

        # ➀-4【CELL】空パレット → WAIT (empty_carry_step)
        empty_task, ok4 = self.empty_carry_step(line_id, ship_task_id, cells)
        if not ok4:
            logger.error("[OP2] ➀-4 空パレット → WAIT empty_carry_step: 失敗")

        # 搬送完了でリフトプラットフォームを空にする処理
        if ok4 and empty_task:
            # t_line_statusのrequest_flag, permition,request_executionを0にする
            self.op_rms.operation_update(line_id, "COMP")
            # t_outputのvalueを0にする
            self.iot_repo.reset_t_output_value(permission_signal_id)
            logger.info("🔄 t_output RESET after ship complete (signal_id=%s)",permission_signal_id)
            logger.info("[WCSDB t_line_status] request_execution 0 更新 (OK)""(line_id=%s)", line_id)
           
