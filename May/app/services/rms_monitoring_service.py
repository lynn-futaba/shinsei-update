"""
RMSモニタリングサービス (RMSMonitoringService)
作成者: Lynn
----------------------------------
ロボット、設備、および倉庫全体の稼働状況をリアルタイムで監視・取得するサービス。

主な役割:
1. リアルタイムデータ取得 (Pull型):
   - RMS APIを定期的に叩き、ロボット（AMR）の位置、バッテリー状態、
     棚（コタツ）の場所、セルの空き状況などを取得します。
2. データ変換とスケーリング:
   - 物理世界（メートル単位）の座標を、画面表示用（ピクセル単位）に変換（Scale 40）。
   - ブラウザの描画ライブラリ（map.js等）がそのまま解釈できる形式に整形します。
3. データの統合:
   - RMSからの設備情報と、自社DB（MySQL）の情報を照らし合わせ、
     「どのロボットがどのパレットを運んでいるか」という付加価値情報を生成します。

管理者画面の「ライブマップ」の心臓部となるコンポーネントです。
"""
# app/services/rms_monitoring_service.py

from app.interfaces.api_client.post_rms_api import PostRmsApi
from app.domain.rms_domain import Cell, AMR, Kotatsu, Map
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery
from typing import List, Dict, Any, Tuple
from app.infrastructure.setup_log import setup_log
import app.config.config as cfg
import re

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logger = setup_log(cfg.LOG_FOLDER, cfg.RMS_MONITORING_SEV_LOG_FILE,
                   cfg.BACKUP_DAYS, logger_name="rms_monitoring_svc")

# ---------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------
def _call_or_attr(obj, name: str, default=None):
    if not hasattr(obj, name):
        return default
    v = getattr(obj, name)
    try:
        return v() if callable(v) else v
    except Exception:
        return default

def _as_int(v, d=0) -> int:
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return d

def _as_float(v, d=0.0) -> float:
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).strip())
        except Exception:
            return d

_XY_RE = re.compile(
    r"X\s*:\s*([-+]?\d+(?:\.\d+)?)\s*/\s*Y\s*:\s*([-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE
)

def _parse_xy(loc) -> tuple[float, float]:
    if isinstance(loc, (tuple, list)) and len(loc) >= 2:
        return (_as_float(loc[0]), _as_float(loc[1]))

    if isinstance(loc, dict):
        # existing support
        if "x" in loc or "y" in loc:
            return (_as_float(loc.get("x")), _as_float(loc.get("y")))

        if "location_x" in loc or "location_y" in loc:
            return (
                _as_float(loc.get("location_x")),
                _as_float(loc.get("location_y")),
            )

        # ✅ ADD THIS (RMS‑REAL FORMAT)
        if "X" in loc or "Y" in loc:
            return (_as_float(loc.get("X")), _as_float(loc.get("Y")))

        if "posX" in loc or "posY" in loc:
            return (_as_float(loc.get("posX")), _as_float(loc.get("posY")))

    if isinstance(loc, str):
        m = _XY_RE.search(loc)
        if m:
            return (_as_float(m.group(1)), _as_float(m.group(2)))

    return (0.0, 0.0)

# =========================================================
# Main service class
# =========================================================
class RMSMonitoringService:

    def __init__(self, ip, port, user_id, user_key, db, wcs_sql: WCSSQLQuery,
                 db_name: str = "futaba_ok2_shippment"):
        logger.info("RMS Monitoring Service >> ip=%s, port=%s, user=%s",
                    ip, port, user_id)
        self.ip = ip
        self.port = port
        self.user_id = user_id
        self.user_key = user_key
        self._db = db
        self._db_name = db_name
        self._sql = wcs_sql
        # self.map = Map()

    # =========================================================
    # REAL-TIME DATA FETCHING (RMS API)
    # =========================================================
    def get_cell(self) -> List[Cell]:
        cells: List[Cell] = []

        try:
            with PostRmsApi(self.ip, self.port, self.user_id, self.user_key) as rms:
                ans_cell = rms.get_rms_info(6)
                body = ((ans_cell or {}).get("response") or {}).get("body") or {}
                src = body.get("cells") or []

                for item in src:
                    try:
                        code = item.get("cellCode")
                        if not code:
                            continue

                        loc_data = item.get("location") or {}
                        x = _as_float(loc_data.get("x"))
                        y = _as_float(loc_data.get("y"))

                        # RMS dimensions
                        w = _as_float(item.get("width"), 1.0)
                        h = _as_float(item.get("length"), 1.0)

                        # ✅ RMS cellStatus → Cell.flag
                        cell_flag = item.get("cellStatus", "VACANT")

                        cell = Cell(
                            cellCode=str(code),
                            cellType=item.get("cellType", "NORMAL"),
                            size=(h, w),
                            location=(x, y, 0),
                            flag=cell_flag,
                        )

                        cells.append(cell)

                    except Exception as e:
                        logger.warning("Parse error in individual cell: %s", e)

        except Exception:
            logger.exception("Error in get_cell API call")

        return cells
    
    def get_amrs(self) -> List[AMR]:
        results = []
        try:
            with PostRmsApi(self.ip, self.port, self.user_id, self.user_key) as rms:
                ans = rms.get_rms_info(5)
                body = ((ans or {}).get("response") or {}).get("body") or {}
                src = body.get("robotList") or body.get("robots") or []
                logger.info("RMS >> Get_amrs src=%s",src)

                for item in src:
                    try:
                        loc_data = item.get("location") or {}
                        x, y = _as_float(loc_data.get("x")), _as_float(loc_data.get("y"))
                        
                        a = AMR(
                            id=item.get("robotId"),
                            name=item.get("robotName", str(item.get("robotId"))),
                            angle=_as_float(item.get("angle"), 0.0),
                            mode=item.get("robotMode", "UNKNOWN"),
                            path=item.get("path", []),
                            location=(x, y, 0)
                        )
                        a.set_status(item.get("robotStatus", "OFFLINE"))
                        results.append(a)
                    except Exception as e:
                        logger.warning("Parse error in AMR item: %s", e)
        except Exception:
            logger.exception("Error in get_amrs API call")
        return results
    
    def get_kotatsus(self) -> List[Kotatsu]:
        results: List[Kotatsu] = []
        pallet_list = self._get_kotatsu_status()
        logger.info("pallet_list >> pallet_list=%s",pallet_list)
        pal_index = {p.get("id"): p for p in (pallet_list or [])}
        logger.info("Pal index pal_index=%s",pal_index)

        try:
            with PostRmsApi(self.ip, self.port, self.user_id, self.user_key) as rms:
                ans = rms.get_rms_info(1)
                body = ((ans or {}).get("response") or {}).get("body") or {}
                shelves = body.get("shelves") or []

                for item in shelves:
                    try:
                        code = item.get("shelfCode") or item.get("id") or item.get("code")
                        if not code: continue

                        x, y = _parse_xy(item.get("location")) if "location" in item else \
                               (_as_float(item.get("location_x")), _as_float(item.get("location_y")))

                        k = Kotatsu(
                            id=str(code),
                            status=item.get("shelfStatus") or "UNKNOWN",
                            type=0,
                            size=(_as_float(item.get("height"), 1.0), _as_float(item.get("width"), 1.0)),
                            angle=_as_float(item.get("angle"), 0.0),
                            location=(x, y, 0),
                        )
                        logger.info("Kotatsu k=%s",k)
                        pal = pal_index.get(code, {})
                        if pal:
                            k.set_pallet(pal.get("palletCode"), None)
                            if pal.get("occupiedRobotId"):
                                k.set_occupant(pal.get("occupiedRobotId"))
                        results.append(k)
                        logger.info("Results results=%s",results)
                    except Exception:
                        logger.exception("Parse error in shelf item")
        except Exception:
            logger.exception("Error fetching SHELF(1)")
        return results

    # =========================================================
    # DISPLAY TRANSFORMATIONS (For map.js)
    # =========================================================
    
    def get_display_cells(self):
        items = self.get_cell()
        out = []
        scale = 40 
        max_x, max_y = 0, 0

        for c in items:
            # Note: location[0] is x, location[1] is y
            x, y = c.location[0] * scale, c.location[1] * scale
            h, w = c.size[0] * scale, c.size[1] * scale
            max_x, max_y = max(max_x, x + w), max(max_y, y + h)

            out.append({
                "cellCode": c.id,
                "location_x": int(x),
                "location_y": int(y),
                "height": int(h),
                "width": int(w),
                "color": "#cccccc" if c.cellflag == "VACANT" else "#ffcc00"
            })
        return out, {"x": int(max_x + 100), "y": int(max_y + 100)}
    
    def get_display_amrs(self):
        out = []
        for a in self.get_amrs():
            loc = a.location
            out.append({
                "id": a.id,
                "robotId": a.id,
                "location_x": _as_float(loc[0]) * 40, # Applying same scale
                "location_y": _as_float(loc[1]) * 40,
                "angle": a.angle,
                "path": a.path,
                "status": a.status,
                "color": "green" if a.status == "NORMAL" else "red",
            })
        return out
    
    def get_display_kotatsus(self):
        out = []

        for k in self.get_kotatsus():
            loc = k.location or ()
            sz  = k.size or ()

            # ✅ FIX: normalize RMS nested location ((x,y,z),)
            if (
                isinstance(loc, (list, tuple)) and
                len(loc) == 1 and
                isinstance(loc[0], (list, tuple))
            ):
                loc = loc[0]

            # ---- now validate ----
            if not isinstance(loc, (list, tuple)) or len(loc) < 2:
                logger.warning(
                    "Skipping kotatsu %s due to invalid location: %r",
                    k.id, loc
                )
                continue

            x = _as_float(loc[0])
            y = _as_float(loc[1])

            # ---- Size validation ----
            h = _as_float(sz[0]) if isinstance(sz, (list, tuple)) and len(sz) > 0 else 1.0
            w = _as_float(sz[1]) if isinstance(sz, (list, tuple)) and len(sz) > 1 else 1.0

            out.append({
                "id": k.id,
                "shelfCode": k.id,
                "location_x": x * 40,
                "location_y": y * 40,
                "height": h * 40,
                "width":  w * 40,
                "angle": k.angle,
                "color": "blue" if str(k.status).lower() == "fill" else "gray",
            })

        return out
    
    def get_display_data(self):
        cells, cell_size = self.get_display_cells()
        amrs = self.get_display_amrs()
        kotatsus = self.get_display_kotatsus()

        # ---- Start with cell-based size ----
        max_x = cell_size.get("x", 1200)
        max_y = cell_size.get("y", 800)

        # ---- Expand size to include AMRs ----
        for a in amrs:
            max_x = max(max_x, _as_float(a.get("location_x", 0)) + 100)
            max_y = max(max_y, _as_float(a.get("location_y", 0)) + 100)

        # ---- Expand size to include Kotatsus ----
        for k in kotatsus:
            max_x = max(
                max_x,
                _as_float(k.get("location_x", 0)) + _as_float(k.get("width", 0))
            )
            max_y = max(
                max_y,
                _as_float(k.get("location_y", 0)) + _as_float(k.get("height", 0))
            )

        siza = {
            "x": int(max_x),
            "y": int(max_y),
        }

        return {
            "siza": siza,
            "cells": cells,
            "amrs": amrs,
            "kotatsus": kotatsus,
        }

    # ---------------------------------------------------------
    # WAREHOUSE STATUS
    # ---------------------------------------------------------
    def get_warehouse_status(self) -> dict:
        try:
            with PostRmsApi(self.ip, self.port, self.user_id, self.user_key) as rms:
                ans = rms.get_rms_info(7)

                logger.info(f"RMS >> get_warehouse_status '{ans}'")

                response = ans.get("response", {})
                body = response.get("body", {})
                wh = body.get("warehouseStatus", {})

                system_status = wh.get("SYSTEM_STATUS") or wh.get("systemStatus")
                job_status = wh.get("JOB_STATUS") or wh.get("jobStatus")

                return {
                    "system_status": str(system_status).upper() if system_status else "OFFLINE",
                    "job_status": str(job_status).upper() if job_status else "STOPPED",
                }

        except Exception:
            logger.exception("WAREHOUSE status error")
            return {
                "system_status": "ERROR",
                "job_status": "ERROR"
            }

    def _get_kotatsu_status(self) -> List[Dict]:
        try:
            if not self._sql:
                return []

            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(self._sql.op_get_kotatsu_status2())
                return cur.fetchall() or []

        except Exception:
            logger.exception("DB kotatsu status error")
            return []