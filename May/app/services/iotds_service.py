"""
IoT データソースサービス（IoTDSService）
作成者: Lynn
--------------------------------------------------

【役割 / Responsibility】
PLC 信号を業務イベントへ変換するための「翻訳レイヤ」。
IoTDS DB を監視し、PLC 信号の立ち上がり（0 → 1）のみを検知して、
信号種別ごとに業務処理に必要な状態更新を行い、
後続サービス起動のトリガ情報を生成する。

本サービスは以下を厳格に守る：
・PLC 信号を直接業務テーブルへ書き込まない
・IoTDS は「状態管理」ではなく「イベント検知」に専念する
・業務ロジックは Operation 系 Service に委譲する

--------------------------------------------------
【処理概要 / Processing Flow】
1. m_signal_list から PLC 信号定義を取得
2. t_input / t_output を監視し、入力信号を取得
3. value = 1（立ち上がり）のみをイベントとして検知（エッジトリガ）
4. signal_type に基づき業務イベントへ変換（単一ループ内で分岐）
    - INPUT START
        → ライン request_flag を更新
        → パレットを FILL 状態へ更新
        → IoTDS 側の出力信号をリセット
        → パレット完了時刻を記録
    - INPUT PERMISSION
        → ライン permission を更新
5. 必要に応じて OperationService / OperationNiService が後続処理を実行

--------------------------------------------------
【重要な設計思想 / Design Principles】
・value = 0 は PLC 内部制御・リセット用途のため無視する
・同一 signal_id は立ち上がりごとに 1 度のみ業務イベントとして処理する
・業務イベントは一方向（起きたら戻らない）
・signal_type ごとに責務を明確に分離する
・DB 更新失敗は必ず ERROR ログとして可視化する

--------------------------------------------------
【チームへのメリット / Benefits】
1. 安全な業務状態管理
    PLC の瞬間的な信号変動が業務データへ直接影響しない。

2. 可読性・追跡性の高い処理構造
    単一ループ＋ signal_type ディスパッチにより、
    「どの PLC 信号が、どの業務イベントになるか」が
    Service レベルで明確に定義されている。

3. 将来拡張が容易
    新しい signal_type 追加時も、
    Repository 変更なしで Service ロジック拡張のみで対応可能。
"""
# app/services/iotds_service.py
from app.infrastructure.repositories.iotds_repository import IOTDSRepository
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
from app.services.operation_service import OperationService
from app.services.operation_ni_service import OperationNiService

# ログ使用
logger = setup_log(
    cfg.LOG_FOLDER,
    cfg.IOTDS_SEV_LOG_FILE,
    cfg.BACKUP_DAYS,
    logger_name="iotds_svc"
)

class IoTDSService:

    def __init__(self, repo: IOTDSRepository):
        self._repo = repo
        self.signal_flgs = None  # signal_id ごとの前回値を保持

    def detect_and_update(self):
        """
        Detect PLC rising-edge signals and translate them into
        business-triggering state updates.
        """
        result = {
            "signals_checked": 0,
            "input_ON_detected": 0,
            "signals_permission_detected": 0,
            "pallet_fill_detected": 0,
            "pallet_completion": 0,
            "request_execution_updated": 0,
            "output_ON_detected": 0,
            "errors": [],
        }

        # ==========================================================
        # Load signal definitions 信号定義を読み込む
        # ==========================================================
        try:
            signal_input_defs = {
                s["signal_id"]: s
                for s in self._repo.get_signal_input_definitions()
            }
        except Exception:
            logger.exception("[IOTDS][INIT] failed to load input signal definitions")
            result["errors"].append("load_input_signal_definitions")
            return result

        # ============================================================================
        # Load input signals & detect first run 入力信号を読み込み、初回実行を検出する
        # ============================================================================
        up_flag= True
        try:
            input_rows = self._repo.get_input_signals()
            if self.signal_flgs is None:
                up_flag= False
        except Exception:
            logger.exception("[IOTDS][INPUT] failed to load input signals")
            result["errors"].append("load_input_signals")
            return result

        # ==========================================================
        # PHASE 1: START / PERMISSION signal detection (edge trigger)
        # ==========================================================
        for row in input_rows:
            result["signals_checked"] += 1

            signal_id = row.get("signal_id")
            input_value = row.get("value")

            # Only rising edge
            if input_value != 1:
                continue

            sig = signal_input_defs.get(signal_id)
            if not sig:
                continue

            signal_type = sig.get("signal_type")
            if signal_type not in ("START", "PERMISSION"):
                continue

            # ==================================================
            # Rising-edge detection
            # ==================================================
            is_edge = False
            if up_flag:
                for f in self.signal_flgs:
                    if f["signal_id"] == signal_id:
                        is_edge = (f["value"] != input_value)
                        logger.info(f"[IOTDS][INPUT] updeate {signal_id} value={input_value}")
            else:
                is_edge = True

            if not is_edge:
                continue

            # =======================================================
            # Resolve pallet_id & line_id パレットIDとラインIDを解決する
            # =======================================================
            try:
                plat_no = sig.get("plat_no")
                res = self._repo.get_pallet_id_by_plat_no(plat_no)
                logger.info(
                    "[WCSDB t_line_station] (plat_no=%s)の pallet_id, line_id取得",
                    res
                )
                if not res:
                    logger.warning(
                        "[WCSDB t_line_station] no pallet mapping found (plat_no=%s)",
                        plat_no
                    )
                    continue
                pallet_id, line_id = res
            except Exception:
                logger.exception("[WCSDB] get_pallet_id_by_plat_no failed")
                result["errors"].append(f"resolve_plat_no:{plat_no}")
                continue

            # ==================================================
            # Dispatch by signal_type
            # ==================================================
            if signal_type == "START":
                result["input_ON_detected"] += 1

                # [WCS DB] update t_line_statusのrequest_flag
                try:
                    self._repo.update_request_flag(input_value, line_id)
                    result["request_execution_updated"] += 1
                    logger.info(
                        "[WCSDB t_line_status] request_flag=%s 更新 (line_id=%s)",
                        input_value,
                        line_id
                    )
                except Exception:
                    logger.exception("[WCSDB t_line_status] request_flag 更新失敗")
                    result["errors"].append(f"update_request_flag:{line_id}")
                    continue
                
                # [WCS DB] update t_pallet_statusのstatus=FILL, SET input_time
                try:
                    self._repo.update_pallet_fill(pallet_id)
                    result["pallet_fill_detected"] += 1
                    logger.info(
                        "[WCSDB t_pallet_status] FILL 更新 (pallet_id=%s)",
                        pallet_id
                    )
                except Exception:
                    logger.exception("[WCSDB t_pallet_status] FILL 更新失敗")
                    result["errors"].append(f"update_pallet_fill:{pallet_id}")
                    continue
                
                # [IoTDS DB] t_outputのvalue1 にセット
                try:
                    self._repo.update_t_output_value(signal_id)
                    result["output_ON_detected"] += 1
                    logger.info(
                        "[IoTDSDB t_output] 1 に セット (signal_id=%s)",
                        signal_id
                    )
                except Exception:
                    logger.exception("[IOTDB t_output] 1 に セット 更新失敗")
                    result["errors"].append(f"update_output_value:{signal_id}")

                # [WCS DB] t_pallet_statusのcompletion_time更新
                try:
                    self._repo.update_pallet_completion(pallet_id)
                    result["pallet_completion"] += 1
                    logger.info(
                        "[WCSDB t_pallet_status] completion_time (pallet_id=%s)",
                        pallet_id
                    )
                except Exception:
                    logger.exception("[WCSDB t_pallet_status] completion 更新失敗")
                    result["errors"].append(f"update_pallet_completion:{pallet_id}")

            elif signal_type == "PERMISSION": #TODO: PERMISSION追加
                result["signals_permission_detected"] += 1

                try:
                    self._repo.update_permition(input_value, line_id)
                    logger.info(
                        "[WCSDB t_line_status] Permission更新 input_value=%s (line_id=%s)",
                        input_value,
                        line_id
                    )
                    # logger.info(
                    #     "[TEST] Permission更新 per=%s input_value=%s line_id=%s",
                    #     per, input_value, line_id
                    # )
                except Exception as e:
                    logger.error(f"[WCSDB t_line_status] permission 更新失敗: {e}")
                    result["errors"].append(f"update_permission_flag:{line_id}")

        # ==========================================================
        # Save current signal snapshot
        # ==========================================================
        self.signal_flgs = input_rows
        return result

        


