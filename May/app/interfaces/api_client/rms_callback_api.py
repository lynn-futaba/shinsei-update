"""
RMSコールバックAPIクライアント (RMSCallbackApi)
作成者: Lynn
----------------------------------
【役割】
RMS（ロボット管理システム）からの通知を受け取った際、正しく「受け取りました」という
応答（ACK: Acknowledgment）を返すためのJSONを組み立てるクラスです。

【チームへのメリット】
1. プロトコル遵守: 
   複雑なヘッダー構造や認証コードをこのクラスに閉じ込めることで、
   他の場所で間違った形式のレスポンスを作るミスを防ぎます。
2. リクエストの紐付け: 
   受信した `requestId` を自動的に `responseId` としてセットするため、
   RMS側で「どの指示に対する返事か」が正しく認識されます。
3. 安全なデータ抽出: 
   受信データの一部が欠けていても、プログラムがクラッシュしないように
   安全なデフォルト値（"UnknownMsg"など）を割り当てます。

※ このクラスはJSONを「作る」だけで、HTTP送信自体は行いません。
   これにより、ネットワーク環境がなくてもテストが可能になっています。
"""
# app/interfaces/api_client/rms_callback_api.py
from __future__ import annotations
from typing import Dict


from app.infrastructure.setup_log import setup_log
import app.config.config as cfg

# ログ設定: 送信データのデバッグに使用します
logger = setup_log(cfg.LOG_FOLDER, cfg.RMS_CALLBACK_API_LOG_FILE, cfg.BACKUP_DAYS, logger_name="rms_callback_api")

class RMSCallbackApi:
    """
    RMS仕様に基づいたレスポンスJSONを構築する専門モジュールです。
    """

    def __init__(self, client_id: str,
                 version: str = "3.3.0",):
        """
        Args:
            client_id: クライアント識別子（例: geekCode_warehouse_001）
            version: プロトコルバージョン（ベンダー指定）
            auth_code: RMSが認証に使用する固定コード
        """
        self._client_id = client_id
        self._version = version
    
    def _create_ack_base(self, msg_type: str, response_id: str, incoming_id: str = "clientid") -> Dict:
        return {
            "id": incoming_id,
            "msgType": msg_type,
            "response": {
                "header": {
                    "responseId": response_id,
                    "code": 0,
                    "msg": "success",
                    "version": self._version
                }
            }
        }

    def build_ack_from_request(self, request_json: Dict) -> Dict:
        msg_type = str(request_json.get("msgType") or "UnknownMsg")

        incoming_id = str(request_json.get("id") or "*")

        response_id = (
            (request_json.get("request") or {})
            .get("header", {})
            .get("requestId", "")
        )

        if not response_id:
            logger.warning("ACK without requestId")

        return self._create_ack_base(msg_type, response_id, incoming_id)