# app/infrastructure/runners/run_controll.py

import threading
from app.infrastructure.repositories.iotds_repository import IOTDSRepository
from app.infrastructure.repositories.operation_repository import OperationRepository
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
from app.services.iotds_service import IoTDSService
from app.services.operation_ni_service import OperationNiService

logger = setup_log(
    cfg.LOG_FOLDER,
    cfg.RUN_CONTROLL_LOG_FILE,
    cfg.BACKUP_DAYS,
    logger_name="run_controll"
)

class ThreadManager:
    def __init__(self):
        self.threads = {}
        self.lock = threading.Lock()

    def start(self, line_id, target):
        with self.lock:
            t = self.threads.get(line_id)

            if t and t.is_alive():
                logger.debug(f"🟨 Thread for line {line_id} already running — skip start.")
                return False

            logger.info(f"🟩 Starting new worker thread for line {line_id} ...")

            # スレッドを起動して非同期に処理を実行
            th = threading.Thread(target=target, daemon=True)
            self.threads[line_id] = th
            th.start()
            return True


class RunControll:
    """
    自動搬送モードの監視＋ライン作業スレッド起動  
    OperationService(line_id, repo, op_rms) を起動する
    """

    def __init__(self, w, i):
        # w: WCSSQLQuery, i: IOTDSSQLQuery
        self._repo = OperationRepository(w, i)
        self.wcs_sql = w
        # self._service = OperationNiService()
        self._manager = ThreadManager()
        self._iotrepo = IOTDSRepository(w, i) 
        
    def run_cycle(self):

        logger.debug("✅ RunControll: run_cycle() called")
        iot = IoTDSService(self._iotrepo)
        
        mode = True  # 各個モードの状態を追跡するフラグ

        while True:
            iot.detect_and_update()

            system = self._repo.get_system_status()
            if not system:
                logger.error("❌ No system status returned")
                return

            status = system[0]
            auto_mode = status["mode"] == 1
            prepared  = status["preparation_ok"] == 1
            running   = status["auto_running"] == 1
            
            # 各個モード
            if not (auto_mode and prepared and running):
                if mode is True:
                    logger.info(
                        "⏹ 各個モード → skip OperationService "
                        "(mode=%s, prep=%s, running=%s)",
                        status["mode"],
                        status["preparation_ok"],
                        status["auto_running"],
                    )
                    mode = False
                continue
            else:
                mode = True

            lines = self._repo.get_line_status()
            if not lines:
                logger.error("❌ No line status returned")

            for row in lines:
                line_id = int(row["line_id"])
                permission = row["transport_permission"]
                carry_pattern = row.get("carry_pattern")
                request_flag = row["request_flag"]
                execution = row["execution"]

                if permission != 1:
                    continue
                if request_flag == 1:
                    if execution == 1:
                        continue
                else:
                    continue
                logger.debug(f"🔍 Line {line_id} execution")

                if carry_pattern is None:
                    logger.error(
                        "❌ Line %s has NULL carry_pattern — skip",
                        line_id,
                    )
                    continue

                if int(carry_pattern) != 0 and isinstance(carry_pattern, int):
                    carry_pattern = int(carry_pattern)
                    logger.info(f"🟦 Line {line_id} allowed (carry_pattern={carry_pattern})")
                else:
                    logger.error(f"carry pattern missing, line_id:{line_id}")
                    continue

                self._repo.update_request_execution(line_id)

                service = OperationNiService(self.wcs_sql, self._iotrepo) #TODO: added _iotrepo parameter
                started = self._manager.start(line_id, lambda: service.start_operation(line_id))
                logger.debug(f"🔍 Line {line_id} service started")
