import time
import threading
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

logger = setup_log(
    cfg.LOG_FOLDER, cfg.OPERATION_SEV_LOG_FILE, cfg.BACKUP_DAYS,
    logger_name="operation_svc"
)

class ResultThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._result = (None, False)
        self._exception = None

    def run(self):
        try:
            if self._target:
                self._result = self._target(*self._args, **self._kwargs)
        except Exception as e:
            self._exception = e
            logger.error(f"Thread Exception: {e}")

    def get_result(self):
        if self._exception:
            raise self._exception
        return self._result

# =====================================================================
# OPERATION SERVICE（並列実行型）
# =====================================================================
class OperationService:
    """
    ライン単位の搬送作業を実行するサービス
    ・完成品搬送
    ・空パレット搬送
    ・セル/コタツの更新
    """
    def __init__(self, repo, op_rms):
        self._repo = repo
        self.op_rms = op_rms

    # =================================================================
    # 空パレットが使用可能になるまで待機
    # =================================================================
    def _wait_for_empty_resources(self, line_id, timeout=60):
        """Wait for empty pallet with a safety timeout."""
        start_wait = time.time()
        while (time.time() - start_wait) < timeout:
            cells, kot, pal = self.op_rms.get_carry_data(line_id, "empty_carry")
            if kot.get("empty") and pal.get("empty"):
                return cells, kot, pal
            time.sleep(2)
        raise TimeoutError("Timeout waiting for empty pallet resources")

    # =================================================================
    # ➀-1 完成品,【CELL】INPUT → TEMP (temp_carry_step)
    # =================================================================
    def temp_carry_step(self, cells, kot, pal):
        logger.info("➀-1 完成品,【CELL】INPUT → TEMP 開始")

        # 完成品を投入間口から一時置き場に搬送のスレット登録
        res, task_id = self.op_rms.send_task(
            step="temp_carry",
            start_cell=cells["input"],
            dest_cell=cells["temp"],
            kotatsu=kot["complete"],
            pallet=pal["complete"],
            task_number=None,
            is_continue=True
        )

        if not res:
            logger.error("[OPS] ➀-1 send_task 失敗")
            return None, False

        ok, task_id, _ = self.op_rms.wait_for_task(
            task_id,
            dest_cell_id=cells["temp"].id,
            kotatsu_id=kot["complete"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-1 wait_for_task 失敗")
            return None, False

        return task_id, True
    
    # =================================================================
    # ➀-2【CELL】WAIT → INPUT 投入口 (input_carry_step)
    # =================================================================
    def input_carry_step(self, cells, kot, pal, task_id):
        logger.info("➀-2【CELL】WAIT → 投入口 開始")
        
        if kot.get("wait") is None: 
                logger.error("WAIT パレット取得エラー")
                return None, False

        # 待機パレットを投入間口に搬送するスレット登録
        res, task_id = self.op_rms.send_task(
            step="input_carry",
            start_cell=cells["wait"],
            dest_cell=cells["input"],
            kotatsu=kot["wait"],
            pallet=pal["wait"],
            task_number=task_id,
            is_continue=True
        )

        if not res:
            logger.error("[OPS] ➀-2 send_task 失敗")
            return None, False

        ok, task_id, _ = self.op_rms.wait_for_task(
            task_id,
            dest_cell_id=cells["input"].id,
            kotatsu_id=kot["wait"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-2 wait_for_task 失敗")
            return None, False

        return task_id, True

    # =================================================================
    # ➀-3【CELL】TEMP → 空パレット (ship_carry_step)
    # =================================================================
    def ship_carry_step(self, cells, kot, pal, task_id):
        logger.info("➀-3【CELL】TEMP → 空パレット 開始")

        # 完成品を一時置き場からリフト間口に搬送するスレット登録
        res, task_id = self.op_rms.send_task(
            step="ship_carry",
            start_cell=cells["temp"],
            dest_cell=cells["complete"],
            kotatsu=kot["complete"],
            pallet=pal["complete"],
            task_number=task_id,
            is_continue=True
        )

        if not res:
            logger.error("[OPS] ➀-3 send_task 失敗")
            return None, False

        ok, task_id, _ = self.op_rms.wait_for_task(
            task_id,
            dest_cell_id=cells["complete"].id,
            kotatsu_id=kot["complete"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-3 wait_for_task 失敗")
            return None, False

        return task_id, True
    
    # =================================================================
    # ➀-4【CELL】空パレット → WAIT (empty_carry_step)
    # =================================================================
    def empty_carry_step(self, line_id):
        logger.info("➀-4【CELL】空パレット → WAIT 開始")

        cells, kot, pal = self._wait_for_empty_resources(line_id) # 空パレット取得
    
        res, task_id = self.op_rms.send_task(
            step="empty_carry",
            start_cell=cells["lift"],
            dest_cell=cells["wait"],
            kotatsu=kot["empty"],
            pallet=pal["empty"],
            task_number=None,
            is_continue=False
        )

        if not res:
            logger.error("[OPS] ➀-4 send_task 失敗")
            return None, False

        ok, task_id, _ = self.op_rms.wait_for_task(
            task_id,
            dest_cell_id=cells["wait"].id,
            kotatsu_id=kot["empty"].id,
        )

        if not ok:
            logger.error("[OPS] ➀-4 wait_for_task 失敗")
            return None, False

        return task_id, True

    # =============================================================================================
        # Operation開始（並列実行）Parallel、AMR 2台
        # 実行順
    # =============================================================================================
    def start_operation(self, line_id: int, signal_id, pallet_id):
        """
            メイン処理
            実行順: ➀-1 ⇒（➀-2 / ➀-3 並列）⇒ ➀-4
        """
        ###################################
        # 空パレットの搬送を分ける必要がある
        # 空パレットがリフト間口に待機できてない時に完成品搬送が出来なくなる為
        # 空パレット搬送を単独で行えるようにする必要がある
        ##################################
        """作業を開始します。"""
        # 作業がある場合は、セルとコタツの情報を取得する処理
        
        logger.info(f"🚀 Parallel Operation START: Line {line_id}")

        if not self.op_rms.get_operation(line_id):
            logger.info("Operation requestなし → 終了")
            return

        # --------------------------------------------------
        # STEP 1: [WCS DB] update request_execution = 1
        # --------------------------------------------------
        try:
            self._repo.update_request_execution(line_id)
            logger.info(
                "[OP][WCSDB t_line_status] request_execution updated to 1 "
                "(line_id=%s)",
                line_id
            )
        except Exception:
            logger.exception(
                "[OP][WCSDB t_line_status] update_request_execution failed "
                "(line_id=%s)",
                line_id
            )
            return


        # --------------------------------------------------
        # STEP 2: Get carry data (cell / kotatsu / pallet)
        # --------------------------------------------------
        try:
            cells, kot, pal = self.op_rms.get_carry_data(
                line_id,
                "complete_carry"
            )
        except Exception:
            logger.exception(
                "[OP][RMS] get_carry_data failed "
                "(line_id=%s, step=complete_carry)",
                line_id
            )
            return

        logger.info(
            """
            [OP] 作業開始
            セル: input=%s, temp=%s, complete=%s, wait=%s
            コタツ: complete=%s, wait=%s
            パレット: complete=%s, wait=%s
            """,
            getattr(cells["input"], "id", None), getattr(cells["temp"], "id", None),
            getattr(cells["complete"], "id", None), getattr(cells["wait"], "id", None),
            getattr(kot["complete"], "id", None), getattr(kot["wait"], "id", None),
            getattr(pal["complete"], "id", None), getattr(pal["wait"], "id", None),
        )

        # --------------------------------------------------
        # STEP 3: [IoTDS DB] reset t_output signal value
        # --------------------------------------------------
        try:
            self._repo.update_output_value(signal_id)
            logger.info(
                "[OP][IOTDB t_output] set value = 1 updated "
                "(signal_id=%s)",
                signal_id
            )
        except Exception:
            logger.exception(
                "[OP][IOTDB t_output] update_output_value failed "
                "(signal_id=%s)",
                signal_id
            )
            return

        # --------------------------------------------------------
        # STEP 4: [WCS DB] update t_pallet_status completion_time
        # --------------------------------------------------------
        try:
            self._repo.update_pallet_completion(pallet_id)
            logger.info(
                "[OP][WCSDB t_pallet_status] completion_time updated "
                "(pallet_id=%s)",
                pallet_id
            )
        except Exception:
            logger.exception(
                "[OP][WCSDB t_pallet_status] update_completion_time failed "
                "(pallet_id=%s)",
                pallet_id
            )
            return

        # -----------------------
        # STEP 5: Operation実行順
        # -----------------------
        # ➀-1 完成品, 【CELL】INPUT → TEMP (temp_carry_thread)
        #----------------------
        # セルとコタツの状態を更新 (temp condition)
        if not self.op_rms.update_state(cells["temp"], kot["complete"]):
            logger.error("[OPS] ➀-1 update_state 失敗")
            return None, False

        # 完成品を投入間口から一時置き場に搬送のスレット登録
        temp_carry_thread = ResultThread(target=self.temp_carry_step, args=(cells, kot, pal))
        
        temp_carry_thread.start()
        temp_carry_thread.join()
        
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cells["temp"], kot["complete"])
        
        temp_task_id, ok_temp = temp_carry_thread.get_result() # 搬送の結果を取得する処理
        if not ok_temp: # 搬送に失敗した場合のエラー処理
            logger.error(f"Error: 完成品の搬送に失敗しました。タスクID: {temp_task_id}")
            while True:
                # エラーの確認用
                time.sleep(1)
        
        #----------------------
        # ➀-2 WAIT → INPUT        
        #----------------------
        # 次パレットを置くタスクは、次パレットの移動と同時のがいい
        # リフト間口から空パレットを待機置き場に移動させる処理
        empty_carry_thread = ResultThread(target=self.empty_carry_step, args=(line_id,))
        
        # セルとコタツの状態を更新
        if not self.op_rms.update_state(cells["input"], kot["wait"]):
            logger.error("[OPS] ➀-4 input_carry_step update_state 失敗")
            return None, False
        
        input_carry_thread = ResultThread(target=self.input_carry_step, args=(cells, kot, pal, temp_task_id))
        input_carry_thread.start() #TODO: Start here
        input_carry_thread.join()
        
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cells["input"], kot["wait"])
        
        input_task_id, ok_input = input_carry_thread.get_result()
        if not ok_input: # 搬送に失敗した場合のエラー処理
            logger.error(f"Error: 完成品の搬送に失敗しました。タスクID: {input_task_id}")
            while True:
                # エラーの確認用
                time.sleep(1)
                pass
        
        # セルとコタツの状態を更新
        # 完成品を一時置き場からリフト間口に移動させる処理 (ship condition)
        if not self.op_rms.update_state(cells["complete"], kot["complete"]):
            logger.error("[OPS] ➀-3 update_state 失敗")
            return None, False
        
        ship_carry_thread = ResultThread(target=self.ship_carry_step, args=(cells, kot, pal, input_task_id))
        ship_carry_thread.start()
        ship_carry_thread.join()
        ship_task_id, ok_ship = ship_carry_thread.get_result()
        # セルとコタツの状態を占有をクリアする処理
        self.op_rms.clear_state(cells["complete"], kot["complete"])
        # 搬送完了でリフトプラットをWORKにする処理
        self.op_rms.set_lift_plat(ship_task_id, cells["complete"], False) 
        # 搬送要求をリセット
        self.op_rms.operation_update(line_id, "COMP")
        logger.info(f"✅ ライン {line_id} Fully Completed 完了")
        
        empty_carry_thread.start() # 空パレット搬送スレッドを実行
        empty_carry_thread.join() # 搬送完了後の処理
        
        empty_task_id, ok_empty = empty_carry_thread.get_result() # 搬送の結果を取得する処理
    
        self.op_rms.clear_state(cells["wait"], kot["empty"]) # セルとコタツの状態を占有をクリアする処理
        self.op_rms.set_lift_plat(empty_task_id, cells["lift"], True) # 搬送完了でリフトプラットフォームを空にする処理
                        
