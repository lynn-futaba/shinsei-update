# app/services/run_initialization_service.py

from app.interfaces.api_client.post_rms_api import PostRmsApi
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
import time

logger = setup_log(
    cfg.LOG_FOLDER,
    cfg.RUN_INITIALIZATION_SEV_LOG_FILE,
    cfg.BACKUP_DAYS,
    logger_name="run_initialization_svc"
)


class RunInitializationService:
    """
    RMS 初期化サービス（Flask 非依存）

    ・RMS の最新状態を取得し、WCS 側 DB の t_location / t_kotatsu_status を更新する
    ・RMS の棚占有情報を反映して、起動後の状態と倉庫の実状態を同期する
    """

    def __init__(self, ip, port, user_id, user_key, db, wcs_sql: WCSSQLQuery,
                 db_name: str = "futaba_ok2_shippment"):

        logger.info("RunInitializationService >>> ip=%s, port=%s, user=%s",
                    ip, port, user_id)

        self.ip = ip
        self.port = port
        self.user_id = user_id
        self.user_key = user_key

        # DB / SQL クライアント保持
        self._db = db
        self._db_name = db_name
        self._sql = wcs_sql

    # --------------------------------------------------------
    # RMS API を安全に取得するためのリトライ付きラッパー
    # --------------------------------------------------------
    def _fetch_with_retry(self, rms, inst_id, retries=5, delay=0.5):
        """
        RMS API の取得を安全に行う（無限ループ防止）
        inst_id:
            5 = Robot
            6 = Cell（棚位置）
            1 = Kotatsu（コタツ）
        """
        for _ in range(retries):
            data = rms.get_rms_info(inst_id)
            
            logger.info("RunInitializationService >>> Data: %s", data)

            if data:
                return data
            time.sleep(delay)

        raise Exception(f"RMS inst_id={inst_id} の応答がありません")

    # --------------------------------------------------------
    # 初期化メイン処理
    # --------------------------------------------------------
    def initialization(self):
        """
        RMS から状態を取得し、WCS DB を初期化 & 同期する。
        WCSSQLQuery の設計に合わせて、接続のみ利用し、
        トランザクションは本サービスが管理する。
        """

        # =====================================================
        # 1) RMS から現在状態を取得
        # =====================================================
        with PostRmsApi(self.ip, self.port, self.user_id, self.user_key) as rms:
            logger.info("[Init] RMS 状態取得開始")

            robot_info   = self._fetch_with_retry(rms, 5)
            cell_info    = self._fetch_with_retry(rms, 6)
            kotatsu_info = self._fetch_with_retry(rms, 1)

        robots = robot_info["response"]["body"].get("robots", [])
        logger.info("[Init] RMS robots count=%d", len(robots))
        logger.info("[Init] RMS robots raw=%s", robots)

        # =====================================================
        # 2) DB 初期化 & 同期（明示トランザクション）
        # =====================================================
        conn = self._sql.get_connection()
        cur = conn.cursor()

        def _drain_cursor(cursor):
            """WCSSQLQuery.cursor_ctx と同じ安全ドレイン"""
            try:
                if getattr(cursor, "with_rows", False):
                    try:
                        cursor.fetchall()
                    except Exception:
                        pass
                if hasattr(cursor, "nextset"):
                    while True:
                        try:
                            more = cursor.nextset()
                        except Exception:
                            break
                        if not more:
                            break
                        try:
                            if getattr(cursor, "with_rows", False):
                                cursor.fetchall()
                        except Exception:
                            pass
            except Exception:
                pass

        try:
            # ---- clear tables ----
            logger.info("[Init] DB 初期化")
            cur.execute(self._sql.clear_t_location()); _drain_cursor(cur)
            cur.execute(self._sql.clear_t_kotatsu_status()); _drain_cursor(cur)
            cur.execute(self._sql.clear_t_robot()); _drain_cursor(cur)

            # ---- UPSERT t_robot ----
            robot_updated = 0

            for r in robots:
                robot_id = r.get("robotId")
                if robot_id is None:
                    logger.error("[Init] robotId missing: %s", r)
                    continue

                cur.execute(
                    self._sql.update_t_robot_from_rms(),
                    (
                        int(robot_id),
                        int(r.get("locationCellCode", 0)),
                        r.get("robotStatus", ""),
                        0,  # kotatsu_id
                    )
                )
                _drain_cursor(cur)

                robot_updated += 1
                logger.info(
                    "[Init] UPSERT t_robot id=%s", robot_id
                )

            # ---- RMS cell → location / kotatsu ----
            cells = cell_info["response"]["body"].get("cells", [])
            updated_cells = 0
            updated_kotatsu = 0

            for rms_cell in cells:
                cell_code = int(rms_cell["cellCode"])
                shelf_code = rms_cell.get("occupiedShelfCode")
                if not shelf_code:
                    continue

                cur.execute(self._sql.update_t_location(), (shelf_code, cell_code))
                _drain_cursor(cur)

                cur.execute(self._sql.update_t_kotatsu_status(), (cell_code, shelf_code))
                _drain_cursor(cur)

                updated_cells += 1
                updated_kotatsu += 1

            conn.commit()

            # ---- t_lift_station の更新 ----
            # t_lift_station の状態取得
            cur.execute(self._sql.get_t_lift_station())
            cell_results = cur.fetchall()
            """
                [0]:plat_no
                [1]:seq_no
                [2]:cell_code
                [3]:pallet_id
                [4]:transport_status
                [5]:kotatsu_id
            """
            # t_lift_station の状態取得
            cur.execute(self._sql.get_t_kotatsu_status())
            kotatsu_results = cur.fetchall()
            """
                [0]:kotatsu_id
                [1]:loaded_pallet_id
                [2]:cell_code
            """

            logger.info(f"[Init] 状態取得: cells={cell_results}, kotatsu={kotatsu_results}")

            for rms_cell in cells:
                cell_code = int(rms_cell["cellCode"])
                for row in cell_results:
                    if cell_code == int(row[2]):  # DBとRMSの比較開始
                        logger.debug(f"[Init]: cells={rms_cell}, kotatsu={row}")
                        if rms_cell.get("occupiedShelfCode", None) is None:  # Cellが占有されていない場合
                            logger.info(f"[Init] 情報削除 プラット:{row[0]}, {row[1]}, 棚: 無し, パレット:  無し")
                            cur.execute(
                                self._sql.updata_t_lift_station_status(),
                                (None, "WAIT", row[0], row[1])
                            )
                            _drain_cursor(cur)
                            break
                        else:  # Cellの占有情報がある場合
                            for kotatsu in kotatsu_results:  # コタツ情報からパレットを取得
                                if rms_cell.get("occupiedShelfCode") == kotatsu[0]:  # DBのコタツのパレットに更新
                                    logger.info(f"[Init] 情報更新 プラット: {row[0]} {row[1]}, 棚: {kotatsu[0]}, パレット: {kotatsu[1]})")
                                    if row[4] == "WAIT":
                                        status = "READY"
                                    else:
                                        status = row[4]
                                    cur.execute(
                                        self._sql.updata_t_lift_station_status(),
                                        (kotatsu[1], status, row[0], row[1])
                                    )
                                    _drain_cursor(cur)
                                    break
                conn.commit()

            logger.info(
                "[Init] 初期化完了: robots=%d cells=%d kotatsu=%d",
                robot_updated, updated_cells, updated_kotatsu
            )

            return {
                "status": "OK",
                "updated_robots": robot_updated,
                "updated_cells": updated_cells,
                "updated_kotatsu": updated_kotatsu,
            }

        except Exception as e:
            logger.exception("[Init] 例外発生、ROLLBACK: %s", e)
            conn.rollback()
            raise

        finally:
            try:
                _drain_cursor(cur)
                cur.close()
            except Exception:
                pass
            conn.close()