"""
RMS各個操作サービス (RMSManualService)
作成者: Lynn
----------------------------------
ロボット（AMR）や設備に対して、直接的な指示（コマンド）を送信するサービス。

主な役割:
1. 手動指示の実行: 
   - 「移動 (Move)」「棚持ち上げ (Fetch)」「棚降ろし (Load)」「タスク中止 (Cancel)」
     といった具体的なアクションをRMS API経由でロボットに命令します。
2. タスクIDの自動追跡: 
   - コマンド送信前に最新のロボット状態を確認し、現在実行中の `taskId` を
     自動で取得して命令に付加します。これにより、命令の不整合を防ぎます。
3. エラーハンドリングとロギング: 
   - RMSからのレスポンスを厳格にチェックし、応答がない場合やエラー時には
     例外をスローしてログに記録します。

管理者画面の「手動操作パネル」から呼び出される、システムの実行部です。
"""
# app/services/rms_manual_service.py
from app.interfaces.api_client.post_rms_api import PostRmsApi
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.domain.rms_domain import Map
from typing import List, Dict, Any, Optional
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定 (名前を付ける)
logger = setup_log(cfg.LOG_FOLDER, cfg.RMS_MANUAL_SEV_LOG_FILE, cfg.BACKUP_DAYS, logger_name="rms_manual_service")

class RMSManualService:
    """RMS 各個操作サービス（Flask非依存）"""

    def __init__(self, ip: str, port: int, db, wcs_sql: WCSSQLQuery, db_name: str = "futaba_ok2_shippment"):
        self.ip = ip
        self.port = port
        self._db = db  # DbFactory（.get_connection(name) を持つ）
        self._db_name = db_name
        self._sql = wcs_sql
        self.map = Map()

    # ---------- public commands ----------

    def move(self, robot_id: str, cell_code: str) -> None:
        """単体移動: go_next"""
        with PostRmsApi(self.ip, self.port) as rms:
            robots = self._get_robots(rms)
            task_id = self._find_task_id(robots, robot_id, default=-1)
            ans = rms.go_next(cell_code, task_id, False, robot_id, False)
            self._ensure_response(ans, f"move: robot_id={robot_id}, cell_code={cell_code}")
            logger.info(f"[RMS] move: robot_id={robot_id} -> cell_code={cell_code}")

    def cancel(self, robot_id: str, cell_code: str) -> None:
        """タスクキャンセル: cancel"""
        with PostRmsApi(self.ip, self.port) as rms:
            robots = self._get_robots(rms)
            task_id = self._find_task_id(robots, robot_id, default=None)
            ans = rms.cancel(task_id, 3, cell_code)
            self._ensure_response(ans, f"cancel: robot_id={robot_id}, cell_code={cell_code}")
            logger.info(f"[RMS] cancel: robot_id={robot_id}")

    def load(self, robot_id: str, shelf_code: str, cell_code: str, angle: int = 0) -> None:
        """棚移動: go_return"""
        with PostRmsApi(self.ip, self.port) as rms:
            robots = self._get_robots(rms)
            if not robots:
                raise RuntimeError("操作エラー:ロボットがいません")
            task_id = self._find_task_id(robots, robot_id, default=-1)
            ans = rms.go_return(cell_code, shelf_code, task_id, angle, False, robot_id)
            self._ensure_response(ans, f"load: robot_id={robot_id}, shelf_code={shelf_code}, cell_code={cell_code}")
            logger.info(f"[RMS] load: robot_id={robot_id}, shelf_code={shelf_code} -> cell_code={cell_code}")

    def fetch(self, robot_id: str, shelf_code: str, cell_code: str, angle: int = 0) -> None:
        """棚持ち移動: go_fetch"""
        with PostRmsApi(self.ip, self.port) as rms:
            robots = self._get_robots(rms)
            if not robots:
                raise RuntimeError("操作エラー:ロボットがいません")
            task_id = self._find_task_id(robots, robot_id, default=-1)
            ans = rms.go_fetch(cell_code, shelf_code, task_id, angle, False, robot_id)
            self._ensure_response(ans, f"fetch: robot_id={robot_id}, shelf_code={shelf_code}, cell_code={cell_code}")
            logger.info(f"[RMS] fetch: robot_id={robot_id}, shelf_code={shelf_code} -> cell_code={cell_code}")

    def remove_shelf(self, shelf_code: str) -> None:
        """棚削除: remove_shelf"""
        with PostRmsApi(self.ip, self.port) as rms:
            ans = rms.remove_shelf(shelf_code)
            self._ensure_response(ans, f"remove_shelf: shelf_code={shelf_code}")
            logger.info(f"[RMS] remove_shelf: shelf_code={shelf_code}")

    # ---------- helpers ----------

    def _get_robots(self, rms) -> List[Dict[str, Any]]:
        try:
            ans = rms.get_rms_info(5)
            if ans is None:
                return []
            return ans.get("response", {}).get("body", {}).get("robots", []) or []
        except Exception as e:
            logger.error(f"Error fetching robots from RMS API: {e}")
            return []

    def _find_task_id(self, robots: List[Dict[str, Any]], robot_id: str, default: Optional[int]) -> Optional[int]:
        for r in robots:
            rid = r.get("robotId")
            if str(rid) == str(robot_id):
                return r.get("taskId", default)
        return default

    def _ensure_response(self, ans: Optional[Dict[str, Any]], context: str) -> None:
        if ans is None:
            logger.error(f"RMSが応答しませんでした: {context}")
            raise RuntimeError("RMSが応答しませんでした")