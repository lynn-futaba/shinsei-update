# app/interfaces/api_client/post_rms_api.py

"""
    機能名:RMS API実行の共通関数
    概要  :RMSへAPIをHTTPリクエストとして送信する。
    作成  :2024/06/11 TMC)S.Nishibe
    更新  :2025/02/11 Futaba)S.Sugiura
    追加  :2026/03/10 Lynn対応
            - セッション開始時の自動ログイン(LoginRequestMsg)追加
            - レスポンス解析の柔軟化 (フラット/入れ子両対応)
            - 認証情報 (userId/userKey) の動的設定対応
"""

from __future__ import annotations
from typing import Optional

import json
import requests
from datetime import datetime
import traceback

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定
logger = setup_log(cfg.LOG_FOLDER, cfg.POST_RMS_API_LOG_FILE, cfg.BACKUP_DAYS, logger_name="post_rms_api")

class PostRmsApi:
    """
    RMSへのAPI送信共通クラス

    :def _init_:
    :def _create_json_base: return=dict
    :def _post_json: return=[dict/None]
    :def get_task_id: return=[int/None]
    :def go_return: return=[dict/None]
    :def go_return_robots: return=[dict/None]
    :def go_fetch: return=[dict/None]
    :def go_fetch_robots: return=[dict/None]
    :def go_next: return=[dict/None]
    :def go_next_robots: return=[dict/None]
    :def go_next_cells: return=[dict/None]
    :def go_next_robots_cells: return=[dict/None]
    :def go_charge_yourself: return=[dict/None]
    :def cancel: return=[dict/None]
    :def release_robot_cell: return=[dict/None]
    :def recover_dispatching: return=[dict/None]
    :def force_move_one_cell: return=[dict/None]
    :def force_robot_turn: return=[dict/None]
    :def add_shelf: return=[dict/None]
    :def remove_shelf: return=[dict/None]
    :def update_shelf_location: return=[dict/None]
    :def update_shelf_class: return=[dict/None]
    :def change_system_mode: return=[dict/None]
    :def change_task_mode: return=[dict/None]
    :def get_rms_info: return=[dict/None]
    """

    # region ==========コンストラクタ==========
    def __init__(self, ip: str, 
                 port: Optional[int] = None, 
                 user_id: str = "geekplus",
                 user_key: str = "111111",
                 base_path: Optional[str] = "/athena/api/v3/message"):
        self.__ip = ip
        self.__port = port if (isinstance(port, int) and port > 0) else None
        
        self.__user_id = user_id
        self.__user_key = user_key

        path = (base_path or "").strip()
        if path and not path.startswith("/"):
            path = "/" + path

        if self.__port is None:
            self.__url = f"http://{self.__ip}{path}"
        else:
            self.__url = f"http://{self.__ip}:{self.__port}{path}"

        logger.info("PostRmsApi Initialized: URL=%s (User: %s)", self.__url, self.__user_id)

        self.session: Optional[requests.Session] = None
        self.session_open = False

    def open_session(self) -> bool:
        """セッションを開始し、自動的にログインを実行する"""
        if not self.session_open:
            self.session = requests.Session()
            self.session_open = True
            logger.debug("RMS session opened")
            # セッション開始直後にログインを試行
            return self.login()
        return True

    def close_session(self):
        if self.session_open and self.session:
            try:
                self.session.close()
            finally:
                self.session_open = False
                logger.debug("RMS session closed")

    def __enter__(self):
        self.open_session()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close_session()

    def __del__(self):
        try:
            if getattr(self, "session_open", False) and getattr(self, "session", None):
                self.session.close()
        except Exception:
            pass
    # endregion

    # region ==========内部処理==========
    def __create_json_base(self, msg_type: str) -> dict:
        """
        APIで用いるjsonの共通部分を作成する関数 ※クラス利用者は意識する必要無し

        :param    msg_type: jsonに設定するmsgType
        :Return: dict型のjsonデータ
        """
        dt_now = datetime.now()
        # RequestID: YYYYMMDDHHMMSSmmm (ミリ秒まで)
        request_id = dt_now.strftime("%Y%m%d%H%M%S%f")[:-3]

        return {
            "id": "clientid",
            "msgType": msg_type,
            "request": {
                "header": {
                    "clientCode": "geekplus",
                    "warehouseCode": "geekplus",
                    "userId": self.__user_id,
                    "userKey": self.__user_key,
                    "version": "3.3.0",
                    "requestId": request_id,
                },
                "body": {},
            },
        }

    def __post_json(self, json_data: dict, is_write_log: bool = True) -> dict | None:
        """
        RMSにJSONを送信。
        フラットなレスポンス（{'code': 0...}）と入れ子構造（{'response': {'header': {'code': 0...}}}）の両方に対応。
        """
        msg_type = json_data.get("msgType")
        logger.info("RMS POST EXEC: url=%s msgType=%s", self.__url, msg_type)

        try:
            http = self.session or requests
            json_dumps = json.dumps(json_data, ensure_ascii=False)
            
            resp = http.post(
                self.__url,
                data=json_dumps,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=10,
            )
        except Exception as e:
            logger.exception("RMS POST failed (network/timeout): %s", e)
            return None

        if resp.status_code != 200:
            logger.error("RMS HTTP Error: status=%s body=%s", resp.status_code, resp.text[:500])
            return None

        try:
            data = resp.json()
        except Exception:
            logger.error("RMS JSON Decode Error. body=%s", resp.text[:500])
            return None

        if is_write_log:
            logger.info("RMS Response Body: %s", data)

        # --- レスポンス構造の解析 ---
        # 1. 入れ子構造 ('response' -> 'header') を探す
        resp_obj = data.get("response") or {}
        header = resp_obj.get("header") or {}
        
        # 2. code/msgを取得 (headerになければトップレベルを探す)
        code = header.get("code") if header.get("code") is not None else data.get("code")
        msg = header.get("msg") if header.get("msg") is not None else data.get("msg")
        
        logger.info("RMS Results: code=%s msg=%s", code, msg)

        if code != 0:
            logger.warning("RMS API Warning/Error: code=%s (msg: %s) for msgType=%s", code, msg, msg_type)
        
        return data
    
    def login(self) -> bool:
        try:
            msg_name = "com.geekplus.athena.api.msg.req.LoginRequestMsg"
            json_data = self.__create_json_base(msg_name)

            # ✅ Explicit empty structure (Athena compatibility)
            json_data["request"]["body"] = {
                "userId": self.__user_id,
                "userKey": self.__user_key
            }

            res = self.__post_json(json_data)

            resp_obj = (res or {}).get("response") or {}
            header = resp_obj.get("header") or {}
            code = header.get("code")

            if code == 0:
                logger.info("RMS Login Success: user_id=%s", self.__user_id)
                return True
            else:
                logger.error("RMS Login Failed: code=%s", code)
                return False
        except Exception as e:
            logger.error("Login Exception: %s", e)
            return False

    def get_rms_info(self, instruction_id: int) -> dict | None:
        """
        RMS情報要求 (QueryInstructionRequestMsg)
        """
        try:
            json_data = self.__create_json_base("com.geekplus.athena.api.msg.req.QueryInstructionRequestMsg")
            instructions = {
                0: "TASK", 1: "SHELF", 2: "CHARGER", 3: "MAP", 
                4: "STATION", 5: "ROBOT", 6: "CELL", 7: "WAREHOUSE", 
                8: "LATTICE", 9: "BOX", 10: "TASKOFPOINT", 11: "DISTANCE"
            }
            instruction = instructions.get(instruction_id, "CELL")
            json_data["request"]["body"]["instruction"] = instruction
            json_data["request"]["body"]["queryType"] = "detail"
            
            logger.info("RMS get_rms_info", json_data)

            return self.__post_json(json_data, is_write_log=True)
        except Exception as e:
            logger.error("get_rms_info exception: %s\n%s", e, traceback.format_exc())
            return None
    # endregion

    # region ==========指示系 API (既存機能の維持)==========
    def go_next(self, dest_cell_code: str, update_task_id: int = -1, stay_flag: bool = False, robot_id: str = None, is_continue=False) -> dict | None:
        try:
            msg_type = "RobotTaskRequestMsg" if update_task_id == -1 else "RobotTaskUpdateRequestMsg"
            json_data = self.__create_json_base(msg_type)
            if update_task_id != -1: 
                json_data["request"]["body"]["taskId"] = update_task_id

            json_data["request"]["body"]["taskType"] = "GO_SOMEWHERE_TO_STAY" if stay_flag else "GO_WORK"
            json_data["request"]["body"]["instruction"] = "GO_NEXT"
            json_data["request"]["body"]["destCellCode"] = dest_cell_code
            if robot_id: json_data["request"]["body"]["robotId"] = robot_id
            json_data["request"]["body"]["isContinue"] = 1 if is_continue else 0

            return self.__post_json(json_data)
        except Exception:
            logger.error(traceback.format_exc())
            return None

    def go_fetch(self, dest_cell_code: str, shelf_code: str, update_task_id: int = -1, turn_angle: int = 0, left_spin: bool = False, robot_id: str = None) -> dict | None:
        try:
            msg_type = "RobotTaskRequestMsg" if update_task_id == -1 else "RobotTaskUpdateRequestMsg"
            json_data = self.__create_json_base(msg_type)
            if update_task_id != -1: 
                json_data["request"]["body"]["taskId"] = update_task_id

            json_data["request"]["body"]["taskType"] = "DELIVER_SHELF"
            json_data["request"]["body"]["instruction"] = "GO_FETCH"
            json_data["request"]["body"]["destCellCode"] = dest_cell_code
            json_data["request"]["body"]["shelfCode"] = shelf_code
            if turn_angle != 0:
                json_data["request"]["body"]["shelfTurnAngle"] = turn_angle
                json_data["request"]["body"]["shelfTurnDirection"] = 1 if left_spin else 0
            if robot_id: json_data["request"]["body"]["robotId"] = robot_id
            json_data["request"]["body"]["isContinue"] = 1

            return self.__post_json(json_data)
        except Exception:
            logger.error(traceback.format_exc())
            return None
    # endregion
    
     # region ==========AMR指示系API==========
    def go_return(
        self,
        dest_cell_code: str,
        shelf_code: str,
        update_task_id: int = -1,
        turn_angle: int = 0,
        left_spin: bool = False,
        robot_id: str = None,
        is_continue=False,
    ) -> dict:
        """
        棚搬送API（GO_RETURN）を実行する共通関数

        :param dest_cell_code:  行先セルコード
        :param shelf_code: 搬送棚コード
        :param update_task_id: 更新タスクID（タスク引き継ぎ時のID）。-1の場合新規タスク
        :param turn_angle: 回転角度。0、90、180、270
        :param left_spin: 左回転フラグ。左回転は[TRUE]/右回転は[FALSE]
        :param robot_id: AMR指定時のロボットID。None時は指定無し
        :param is_continue: タスク継続フラグ。継続ありは[TRUE]/継続なしは[FALSE]
        :Return: 成功時[辞書型のHTTPレスポンス]/失敗時[None]
        """
        try:
            # jsonのベースを作成
            if update_task_id == -1:
                # タスク新規発行
                json_data = self.__create_json_base("RobotTaskRequestMsg")
            else:
                # タスク引き継ぎ
                json_data = self.__create_json_base("RobotTaskUpdateRequestMsg")
                json_data["request"]["body"]["taskId"] = update_task_id

            # 固定パラメータセット
            json_data["request"]["body"]["taskType"] = "DELIVER_SHELF"
            json_data["request"]["body"]["instruction"] = "GO_RETURN"

            # 行先セルコード
            json_data["request"]["body"]["destCellCode"] = dest_cell_code

            # 搬送棚コード
            json_data["request"]["body"]["shelfCode"] = shelf_code

            # 回転角度が設定されていれば回転あり
            if turn_angle != 0:
                # 回転角度
                json_data["request"]["body"]["shelfTurnAngle"] = turn_angle

                # 回転方向
                if left_spin:
                    # 左回転
                    json_data["request"]["body"]["shelfTurnDirection"] = 1
                else:
                    # 右回転
                    json_data["request"]["body"]["shelfTurnDirection"] = 0

            # AMRの指定があるか
            if robot_id is not None:
                json_data["request"]["body"]["robotId"] = robot_id

            # タスクを継続するか
            if is_continue:
                json_data["request"]["body"]["isContinue"] = 1
            else:
                json_data["request"]["body"]["isContinue"] = 0

            # jsonの送信
            response_data = self.__post_json(json_data)
            return response_data

        except Exception as e:
            error_message = traceback.format_exc()
            logger.error(f"例外発生:{e}")
            logger.error(f"トレースバック:{error_message}")
            return None

    def go_return_robots(
        self,
        dest_cell_code: str,
        shelf_code: str,
        robot_ids: list[str],
        turn_angle: int = 0,
        left_spin: bool = False,
        is_continue=False,
    ) -> dict:
        """
        棚搬送API（GO_RETURN）を複数ロボット指定で実行する共通関数

        :param dest_cell_code:  行先セルコード
        :param shelf_code: 搬送棚コード
        :param robot_ids: ロボットIDのリスト
        :param turn_angle: 回転角度。0、90、180、270
        :param left_spin: 左回転フラグ。左回転は[TRUE]/右回転は[FALSE]
        :param is_continue: タスク継続フラグ。継続ありは[TRUE]/継続なしは[FALSE]
        :Return: 成功時[辞書型のHTTPレスポンス]/失敗時[None]
        """
        try:
            # jsonのベースを作成
            json_data = self.__create_json_base("RobotTaskRequestMsg")

            # 固定パラメータセット
            json_data["request"]["body"]["taskType"] = "DELIVER_SHELF"
            json_data["request"]["body"]["instruction"] = "GO_RETURN"

            # 行先セルコード
            json_data["request"]["body"]["destCellCode"] = dest_cell_code

            # 搬送棚コード
            json_data["request"]["body"]["shelfCode"] = shelf_code

            # 回転角度が設定されていれば回転あり
            if turn_angle != 0:
                # 回転角度
                json_data["request"]["body"]["shelfTurnAngle"] = turn_angle

                # 回転方向
                if left_spin:
                    # 左回転
                    json_data["request"]["body"]["shelfTurnDirection"] = 1
                else:
                    # 右回転
                    json_data["request"]["body"]["shelfTurnDirection"] = 0

            # AMRリストの指定
            json_data["request"]["body"]["robotIds"] = robot_ids

            # タスクを継続するか
            if is_continue:
                json_data["request"]["body"]["isContinue"] = 1
            else:
                json_data["request"]["body"]["isContinue"] = 0

            # jsonの送信
            response_data = self.__post_json(json_data)
            return response_data

        except Exception as e:
            error_message = traceback.format_exc()
            logger.error(f"例外発生:{e}")
            logger.error(f"トレースバック:{error_message}")
            return None
        
    def cancel(
            self,
            update_task_id: int,
            cancel_mode: int = 2,
            dest_cell_code: str = None,
        ) -> dict:
            """
            タスクキャンセルAPI（GO_NEXT）を実行する共通関数

            :param update_task_id: 更新タスクID
            :param cancel_mode: キャンセルモード
                                [0]棚のplacementCellCodeに棚を置く
                                [2]キャンセルされた場所に棚を置く
                                [3]指定したセルコードに棚を置く
            :param dest_cell_code: キャンセルモード3の時に棚を置くセルコード
            :Return: 成功時[辞書型のHTTPレスポンス]/失敗時[None]
            """
            try:
                # jsonのベースを作成
                # タスク引き継ぎ
                json_data = self.__create_json_base("RobotTaskUpdateRequestMsg")
                json_data["request"]["body"]["taskId"] = update_task_id

                # 固定パラメータセット
                json_data["request"]["body"]["instruction"] = "CANCEL"

                # キャンセルモード
                json_data["request"]["body"]["cancelAction"] = cancel_mode

                # キャンセルモード3なら棚を置くセルコードを指定する
                if cancel_mode == 3:
                    json_data["request"]["body"]["destCellCode"] = dest_cell_code

                # jsonの送信
                response_data = self.__post_json(json_data)
                return response_data

            except Exception as e:
                error_message = traceback.format_exc()
                logger.error(f"例外発生:{e}")
                logger.error(f"トレースバック:{error_message}")
                return None

    def remove_shelf(self, shelf_code: str) -> dict:
        """
        棚削除API（REMOVE_SHELF）を実行する共通関数

        :param shelf_code: 削除棚コード
        :Return: 成功時[辞書型のHTTPレスポンス]/失敗時[None]
        """
        try:
            # jsonのベースを作成
            json_data = self.__create_json_base("WarehouseInstructionRequestMsg")

            # 固定パラメータセット
            json_data["request"]["body"]["instruction"] = "REMOVE_SHELF"

            # 削除棚コード
            json_data["request"]["body"]["shelfCode"] = shelf_code

            # jsonの送信
            response_data = self.__post_json(json_data)
            return response_data

        except Exception as e:
            error_message = traceback.format_exc()
            logger.error(f"例外発生:{e}")
            logger.error(f"トレースバック:{error_message}")
            return None
    
    # region ==========汎用関数==========
    def get_task_id(self, response_data: dict) -> int:
        """
        タスク指示APIの応答からタスクIDを取得する

        :param    response_data: タスク指示APIの応答
        :Return: 成功時[タスクID]/失敗時[None]
        """

        if response_data is None:
            # response_dataがNoneならNoneを返す
            return None
        elif (
            "response" in response_data
            and "body" in response_data["response"]
            and "taskId" in response_data["response"]["body"]
        ):
            # response_dataにtaskIdがあればタスクIDを返す
            return response_data["response"]["body"]["taskId"]
        else:
            # response_dataにtaskIdがなければNoneを返す
            return None

    # endregion ==========汎用関数==========
 