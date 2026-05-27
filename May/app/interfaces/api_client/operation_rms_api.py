import time
from app.domain.rms_domain import Cell, Kotatsu, Pallet, Task
from app.interfaces.api_client.post_rms_api import PostRmsApi
from app.interfaces.sql.wcs_sql_query import WCSSQLQuery

from app.infrastructure.setup_log import setup_log
import app.config.config as cfg



logger = setup_log(
    cfg.LOG_FOLDER, cfg.OPERATION_RMS_API_LOG_FILE, cfg.BACKUP_DAYS,
    logger_name="operation_rms_api"
)


class OperationRMS:
    """
    Clean RMS operation module:
    ✅ All SQL goes through WCSSQLQuery op_* functions
    ✅ Only RMS API + merge logic lives in here
    ✅ Supports:
        - get_operation
        - get_cells
        - get_kotatsus
        - get_pallets
        - get_empty_pallet
        - get_carry_data
        - reserve/update/clear
        - send_task
        - wait_for_task
        - persist_task_status
        - set_lift_plat
        - operation_update
    """

    def __init__(self, wcs_sql: WCSSQLQuery):
        self._sql = wcs_sql
        self.rms_api = PostRmsApi(cfg.RMS_IP, cfg.RMS_PORT)
        
    # ================================================================
    # 1) Check for operation request
    # ================================================================
    def get_operation(self, line_id):
        """作業情報を取得する処理"""
        sql = self._sql.op_get_operation()
        try:
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql, (line_id,))
                row = cur.fetchone()
                logger.info(f"[OperationRMS] op_get_operation SQL Query: {row}")
        except Exception as e:
            logger.error(f"[OperationRMS] get_operation SQL error: {e}")
            return False

        if not row:
            # 作業がない場合は、Falseを返す
            return False

        # update pallet 
        # 作業がある場合は、作業の内容をもとにセルとコタツの情報を更新する処理
        upd = self._sql.op_update_complete_pallet()
        logger.info(f"[OperationRMS] op_update_complete_pallet SQL Query: {upd}")
        with self._sql.write_cursor_ctx() as cur:
            cur.execute(upd, (row["request_time"], row["pallet_id"]))

        return True

    # ================================================================
    # 2) GET CELLS  (オペレーションに必要な関数)
    # ================================================================
    def get_cells(self, line_id):
        # ----------------------------
        # 1) LOAD DB CELLS
        # ----------------------------
        try:
            # データベースからセルの情報を取得する処理
            sql = self._sql.op_get_line_cells()
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql, (line_id,))
                db_cells = cur.fetchall() or []

                # ✅ EXTENSION: add empty cells
                try:
                    sql_empty = self._sql.op_get_empty_cells()
                    cur.execute(sql_empty, (line_id,))
                    db_cells.extend(cur.fetchall() or [])
                except Exception as e:
                    logger.warning(f"[OperationRMS] get_empty_cells skipped: {e}")

        except Exception as e:
            logger.error(f"[OperationRMS] SQL get_cells failed: {e}")
            return []

        # ------------------------------------------------------
        # 2) LOAD RMS CELLS (RMS APIからセルの情報を取得する処理)
        # ------------------------------------------------------
        try:
            with self.rms_api as rms:
                ans = rms.get_rms_info(3)
        except Exception as e:
            logger.error(f"[OperationRMS] RMS get_cells failed: {e}")
            return []

        if not ans:
            logger.error("[OperationRMS] RMS response is None")
            return []

        body = (ans.get("response") or {}).get("body")
        if not body:
            logger.error(f"[OperationRMS] RMS missing body: {ans}")
            return []

        map_data = body.get("map")
        if not map_data:
            logger.error(f"[OperationRMS] RMS missing map: {ans}")
            return []

        floors = map_data.get("floors") or []
        if not floors:
            logger.error("[OperationRMS] RMS map has no floors")
            return []

        rms_cells = floors[0].get("cells") or []
        if not rms_cells:
            logger.error("[OperationRMS] RMS floor has no cells")
            return []

        # ---------------------------------------------------------------
        # 3) MERGE (RMS APIとデータベースの情報を照合して、セル作成する処理)
        # ---------------------------------------------------------------
        merged = []

        for db_item in db_cells:
            for rms_item in rms_cells:
                if str(db_item.get("cell_code")) != rms_item.get("cellCode"):
                    continue

                cell = Cell(
                    cellCode=rms_item["cellCode"],
                    cellType=rms_item["cellType"],
                    size=(rms_item["length"], rms_item["width"]),
                    location=(
                        rms_item["location"]["x"],
                        rms_item["location"]["y"],
                        rms_item["location"]["z"],
                    ),
                    flag=rms_item["cellFlag"],
                    type=db_item.get("cell_type"),
                    angle=db_item.get("angle"),
                )
                if db_item["has_reservation"]:
                    tmpe = cell.set_carrier(db_item["has_reservation"])
                occupied = rms_item.get("occupiedShelfCode")
                
                if occupied is not None:
                    # ✅ Only care when WCS has reservation intent
                    if db_item.get("kotatsu_id") != occupied:
                        logger.error(
                            f"[OperationRMS] Reserved cell mismatch "
                            f"Cell:{db_item.get('cell_code')} "
                            f"DB:{db_item.get('kotatsu_id')} "
                            f"RMS:{occupied}"
                        )
                    # Visualization still trusts RMS
                    cell.set_occupant(occupied)


                merged.append(cell)

        return merged

    # ================================================================
    # 3) GET KOTATSUS
    # ================================================================
    def get_kotatsus(self):
    # ------------------------------------------------------------------------
    # 1) LOAD DB KOTATSU STATUS (こたつの状態を管理するテーブルから情報を取得する)
    # ------------------------------------------------------------------------
        try:
            sql = self._sql.op_get_kotatsu_status2()
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql)
                db_kt = cur.fetchall() or []
        except Exception as e:
            logger.error(f"[OperationRMS] SQL get_kotatsu failed: {e}")
            return []
        logger.info(f"{db_kt}")
        # ----------------------------------------------------------------
        # 2) LOAD RMS KOTATSU DATA (RMS APIからこたつの情報を取得する処理)
        # ----------------------------------------------------------------
        try:
            with self.rms_api as rms:
                ans = rms.get_rms_info(1)
        except Exception as e:
            logger.error(f"[OperationRMS] RMS get_kotatsu failed: {e}")
            return []

        if not ans:
            logger.error("[OperationRMS] RMS get_kotatsu returned None")
            return []

        body = (ans.get("response") or {}).get("body") or {}
        shelves = body.get("shelves") or []

        if not shelves:
            logger.warning("[OperationRMS] RMS returned no shelves")
            return []

        # ----------------------------
        # 3) MERGE DB + RMS DATA
        # ----------------------------
        out = []

        for d in db_kt:
            db_id = d.get("kotatsu_id")
            if not db_id:
                continue

            for r in shelves:
                if db_id != r.get("shelfCode"):
                    continue

                loc = r.get("location") or {}

                kot = Kotatsu(
                    id=r.get("shelfCode"),
                    status=r.get("shelfStatus"),
                    type=d.get("kotatsu_type"),
                    size=(
                        r.get("length"),
                        r.get("width"),
                    ),
                    angle=r.get("angle"),
                    location=(
                        loc.get("x"),
                        loc.get("y"),
                        loc.get("z"),
                    )
                )

                cell_code = r.get("locationCellCode")
                if cell_code is not None:
                    kot.set_cellcode(cell_code)

                pallet_id = d.get("pallet_id")
                if pallet_id:
                    kot.set_pallet(pallet_id)
                
                out.append(kot)
        # logger.info(f"data={out}")
        return out

    # ================================================================
    # 4) PALLETS (パレットの状態を管理するテーブルから情報を取得する)
    # ================================================================
    def get_pallets(self):
        try:
            
            sql = self._sql.op_get_pallet_status()
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql)
                db_pallets = cur.fetchall() or []
        except Exception as e:
            logger.error(f"[OperationRMS] SQL get_pallets failed: {e}")
            return []
        
        pallets = []

        for pallet_item in db_pallets:
            pallet_id = pallet_item.get("pallet_id")
            if not pallet_id:
                continue

            pallets.append(
                Pallet(
                    id=pallet_id,
                    type=pallet_item.get("pallet_type"),
                    status=pallet_item.get("status"),
                    input_time=pallet_item.get("input_time"),
                    complete_time=pallet_item.get("completion_time"),
                    angle=pallet_item.get("kanban_angle"),
                )
            )
            
        return pallets

    # ================================================================
    # 5) EMPTY PALLET FROM LIFT
    # ================================================================
    def get_empty_pallet(self, line_id):
        """パレットの状態を管理するテーブルから情報を取得する"""
        sql = self._sql.op_get_lift_pallet_status()
        try:
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql, (line_id,))
                r = cur.fetchone()
        except Exception as e:
            logger.error(f"[OperationRMS] SQL get_empty_pallet failed: {e}")
            return None, None

        if not r:
            return None, None

        logger.info(f"[OperationRMS] get_empty_pallet: pallet_id={r['pallet_id']} cell_code={r['cell_code']}")
        return r["pallet_id"], r["cell_code"]

    # ================================================================
    # 6-1) Combine cell + kotatsu + pallet
    # ================================================================
    def get_empty_carry_data(self, line_id):
        # セルとコタツのオブジェクトの読み出し
        cells = self.get_cells(line_id)
        kotatsus = self.get_kotatsus()
        pallets = self.get_pallets()

        # 供給するパレットIDを取得
        empty_pid, empty_cell = self.get_empty_pallet(line_id)

        cell_data = None
        kot_data = None
        pal_data = None
        
        # ✅ PRE‑DEFINE log variables
        p_cell = None
        p_kot = None
        p_pal = None

        try:
            # ------------------------------------------------------------
            # セルの情報はリスト化
            # ------------------------------------------------------------
            for c in cells:
                # 空パレット取出しセル
                if empty_cell and int(c.id) == empty_cell:
                    cell_data = c
                    p_cell = int(c.id)
                    break

            # ------------------------------------------------------------
            # コタツの情報はリスト化
            # ------------------------------------------------------------
            for k in kotatsus:
                # 供給するパレットのコタツを登録
                if empty_pid and k.pallet_id == empty_pid:
                    kot_data = k
                    p_kot = k.id
                    break

            # ------------------------------------------------------------
            # パレットの情報はリスト化
            # ------------------------------------------------------------
            pal_data = None
            for p in pallets:
                # 供給するパレットを登録
                if kot_data and p.id == kot_data.pallet_id:
                    pal_data = p
                    p_pal = p.id
                    break

            logger.info(f"[OperationRMS] get_empty_carry_data: cell={p_cell} kotatsu={p_kot} pallet={p_pal}")

        except Exception as e:
            logger.error(f"[OperationRMS] get_empty_carry_data error: {e}")
            cell_data = None

        return cell_data, kot_data, pal_data

    # ================================================================
    # 6-0) Combine cell + kotatsu + pallet
    # ================================================================
    def get_carry_data(self, line_id):
        # 戻り値の変数
        cell_data = {
            "input": None,
            "temp": None,
            "complete": None,
            "turn": None,
            "wait": None,
            "lift": None,
        }
        kot_data = {
            "complete": None,
            "wait": None,
            "empty": None,
        }
        pal_data = {
            "complete": None,
            "wait": None,
            "empty": None,
        }

        # セルとコタツのオブジェクトの読み出し
        cells = self.get_cells(line_id)
        kotatsus = self.get_kotatsus()
        pallets = self.get_pallets()
        # logger.info(f"cell={cells} kotatsu={kotatsus }")


        # ------------------------------------------------------------
        # セルの情報はリスト化
        # ------------------------------------------------------------
        for c in cells:
            # 投入間口のセル
            if c.type == "input":
                cell_data["input"] = c

            # 仮置き場のセル
            elif c.type == "temp":
                cell_data["temp"] = c

            # 回転セル
            elif c.type == "turn":
                cell_data["turn"] = c

            # 完成品置き場のセル
            elif c.type == "complete":
                # kotatsu未割当のセルを優先
                if c.kotatsu_id is None and c.carrier is False:
                    logger.debug(
                        "[CELL COMPLETE] cell=%s kotatsu_id=%s",
                        c.id, c.kotatsu_id
                    )
                    cell_data["complete"] = c

            # 空パレ置き場のセル
            if c.type == "wait":
                cell_data["wait"] = c

        # ------------------------------------------------------------
        # コタツの情報はリスト化
        # ------------------------------------------------------------
        for k in kotatsus:
            # 投入間口のコタツを登録
            # logger.debug(f"{k.id},{cell_data['input'].kotatsu_id}")
            if cell_data["input"] and cell_data["input"].kotatsu_id == k.id:
                kot_data["complete"] = k

            # 完成品置き場のコタツを登録
            if cell_data["wait"] and cell_data["wait"].kotatsu_id == k.id:
                kot_data["wait"] = k

        # ------------------------------------------------------------
        # パレットの情報はリスト化
        # ------------------------------------------------------------
        pal_data["empty"] = None
        for p in pallets:
            # 投入間口のパレットを登録
            if kot_data["complete"] and p.id == kot_data["complete"].pallet_id:
                pal_data["complete"] = p
            # 完成品置き場のパレットを登録
            if kot_data["wait"] and p.id == kot_data["wait"].pallet_id:
                pal_data["wait"] = p

        return cell_data, kot_data, pal_data

    # ================================================================
    # 7) reserve/update/clear
    # ================================================================
    def update_state(self, cell: Cell, kotatsu: Kotatsu):
        """
        セル、棚のステータスを更新
        """
        logger.info(f"update_state cells :{cell.id} {kotatsu.id}")
        """セルとコタツの状態を更新する処理"""
        cell_occupant = cell.set_occupant(kotatsu.id)
        kotatsu_occupant = kotatsu.set_occupant()
        cell_reserve = cell.set_carrier()
        
        if not cell_occupant or not kotatsu_occupant:
            if not cell_occupant:
                logger.error(f"Error: セル:{cell.id}に棚がいるため、棚搬送指示をしてください")
                if not cell_reserve:
                    logger.error(f"Error: セル:{cell.id}に棚搬送指示されているので搬送に失敗しました")
                    if kotatsu_occupant:
                        kotatsu.clear_occupant()
                        return False
            if not kotatsu_occupant:
                logger.error(f"Error: コタツ:{kotatsu.id}は搬送が設定されているため、搬送できません")
                if cell_occupant:
                    cell.clear_occupant()
                return False

        try:
            #セルの情報を更新する
            cell_code = cell.id
            if cell.cellflag == "NORMAL":
                cellFlag = True
            kotatsu_id = cell.kotatsu_id
            has_reservation = cell.is_occupied
            
            #コタツの情報を更新する
            k_id = kotatsu.id
            k_cellcode = kotatsu.cellcode
            k_pallet_id = kotatsu.pallet_id
            k_booking = kotatsu.is_occupant
            
            logger.info(f"update_state t_location :{cellFlag} {kotatsu_id} {has_reservation} {cell_code}")
            logger.info(f"update_state t_kotatsu_status :{k_cellcode} {k_pallet_id} {k_booking} {k_id}")

            with self._sql.write_cursor_ctx() as cur:
                # Release cell
                cur.execute(self._sql.op_update_cell(),
                    (cellFlag, kotatsu_id, has_reservation, cell_code) # transport_permission, kotatsu_id, has_reservation, cell_code
                )
                cur.execute(self._sql.op_update_kotatsu(), 
                    (cell_code, k_pallet_id, k_booking, k_id) # cell_code, loaded_pallet_id, booking, kotatsu_id
                )

        except Exception as e:
            logger.error(f"[OperationRMS] update_state failed: {e}")
            return False

        return True


    def clear_state(self, s_cell: Cell, d_cell: Cell, kotatsu: Kotatsu):
        
        # logger.info(f"[OperationRMS] clear_state >> cell: {s_cell} , {d_cell}")
        # logger.info(f"[OperationRMS] clear_state >> kotatsu: {kotatsu}")
        
        s_cell.clear_occupant()
        d_cell.clear_occupant()
        kotatsu.clear_occupant()
        try:
            # スタートセルの情報を更新する
            s_cell_code = s_cell.id
            if s_cell.cellflag == "NORMAL":
                s_cellFlag = True

            # ダストセルの情報を更新する
            d_cell_code = d_cell.id
            if d_cell.cellflag == "NORMAL":
                d_cellFlag = True

            #コタツの情報を更新する
            k_id = kotatsu.id
            k_pallet_id = kotatsu.pallet_id
            k_booking = False
            with self._sql.write_cursor_ctx() as cur:
                # Release cell
                cur.execute(self._sql.op_update_cell(),
                    (s_cellFlag, None, False, s_cell_code) # transport_permission, kotatsu_id, has_reservation, cell_code
                )
                cur.execute(self._sql.op_update_cell(),
                    (d_cellFlag, k_id, False, d_cell_code) # transport_permission, kotatsu_id, has_reservation, cell_code
                )
                cur.execute(self._sql.op_update_kotatsu(), 
                    (d_cell_code, k_pallet_id, k_booking, k_id) # cell_code, loaded_pallet_id, booking, kotatsu_id
                )
        except Exception as e:
            logger.error(f"[OperationRMS] clear_state failed: {e}")
        return True

    # ================================================================
    # 8‐1) Send RMS Task (GO_RETURN)
    # ================================================================
    def send_task(self, *, step, start_cell, dest_cell, kotatsu, pallet, task_number=None, is_continue=False, ratation_cell=None):

        rotation = False
        turn_angle=None
        left_spin=False
        task_id = None
        if task_number is None:
            task_number = -1

        # 搬送条件をstepで見分ける
        if step == "empty_carry":
            rotation = True
            # セルの向きとパレットの向きで条件を作る 回転方向は決め打ちで、必要なら追加する
            if dest_cell.angle == 0 and pallet.angle == 0:
                turn_angle = 0
                left_spin = False
            elif dest_cell.angle == 0 and pallet.angle == 180:
                turn_angle = 180
                left_spin = False
            elif dest_cell.angle == 90 and pallet.angle == 0:
                turn_angle = 90
                left_spin = False
            elif dest_cell.angle == 90 and pallet.angle == 180:
                turn_angle = 90
                left_spin = True
            elif dest_cell.angle == -90 and pallet.angle == 0:
                turn_angle = 90
                left_spin = True
            elif dest_cell.angle == -90 and pallet.angle == 180:
                turn_angle = 90
                left_spin = False
            elif dest_cell.angle == 180 and pallet.angle == 0:
                turn_angle = 180
                left_spin = False
            elif dest_cell.angle == 180 and pallet.angle == 180:
                turn_angle = 0
                left_spin = False
            logger.info(f"angle:{turn_angle}, spin:{'left' if left_spin else 'right'}")

        elif step == "ship_carry":
            rotation = True
            # 発進セルの向きとパレットの向きで条件を作る 回転方向は決め打ちで、必要なら追加する
            if start_cell.angle == 0 and pallet.angle == 0:
                turn_angle = 0
                left_spin = True
            elif start_cell.angle == 0 and pallet.angle == 180:
                turn_angle = 180
                left_spin = True
            elif start_cell.angle == 90 and pallet.angle == 0:
                turn_angle = 90
                left_spin = True
            elif start_cell.angle == 90 and pallet.angle == 180:
                turn_angle = 90
                left_spin = False
            elif start_cell.angle == -90 and pallet.angle == 0:
                turn_angle = 90
                left_spin = False
            elif start_cell.angle == -90 and pallet.angle == 180:
                turn_angle = 90
                left_spin = True
            elif start_cell.angle == 180 and pallet.angle == 0:
                turn_angle = 180
                left_spin = True
            elif start_cell.angle == 180 and pallet.angle == 180:
                turn_angle = 0
                left_spin = True
            logger.info(f"angle:{turn_angle}, spin:{'left' if left_spin else 'right'}")
        else:
            turn_angle = 0
            left_spin = False

        if rotation:
            try:
                with self.rms_api as rms:
                    res = rms.go_fetch(
                        dest_cell_code=ratation_cell.id,
                        shelf_code=kotatsu.id,
                        update_task_id=task_number,
                        turn_angle=turn_angle,
                        left_spin=left_spin,
                        robot_id=None,
                    )

                logger.info(f"""[OperationRMS] send_task: STEP {step} ,GO_RETURN: {res}
                            task_details[shelf:{kotatsu.id}, turn:{turn_angle}, spin:{'left' if left_spin else 'right'}, continue:{is_continue}]""")
                if task_number == -1:
                    task_id = self.rms_api.get_task_id(res)
                else:
                    task_id = task_number

                ok, _, task = self.wait_for_task(task_id, start_cell, ratation_cell.id, kotatsu.id)
                
                if not ok:
                    logger.error("[OPS] ➀-2 wait_for_task 失敗")
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"[OperationRMS] send_task error: {e}")
                return None, None

        try:
            with self.rms_api as rms:
                res = rms.go_return(
                    dest_cell_code=dest_cell.id,
                    shelf_code=kotatsu.id,
                    update_task_id=task_number,
                    turn_angle=0,
                    left_spin=False,
                    robot_id=None,
                    is_continue=is_continue
                )
                logger.info(f"""[OperationRMS] send_task: STEP {step} ,GO_RETURN: {res}
                            task_details[shelf:{kotatsu.id}, turn:{turn_angle}, spin:{'left' if left_spin else 'right'}, continue:{is_continue}]""")
                if task_number == -1:
                    task_id = self.rms_api.get_task_id(res)
                else:
                    task_id = task_number
                # 搬送の情報を受け取り
                rms_info = rms.get_rms_info(0)

        except Exception as e:
            logger.error(f"[OperationRMS] send_task error: {e}")
            return None, None

        # start_cell 抽出
        start_cell = None
        try:
            for t in rms_info["response"]["body"]["tasks"]:
                if t["taskId"] == task_id:
                    start_cell = t.get("startCellCode")
                    break
        except Exception as e:
            logger.warning("[OperationRMS] Failed to parse rms_info startCellCode: %s", e)
        return res, task_id, start_cell

    # ================================================================
    # 8‐2) Send RMS Task (GO_FETCH)
    # ================================================================
    def send_go(self, *, step, start_cell, dest_cell, kotatsu, pallet, task_number=None, is_continue=False, ratation_cell=None):

        task_id = None
        if task_number is None:
            task_number = -1

        logger.info(f"send_go, task_id = {task_number}")

        try:
            with self.rms_api as rms:
                res = rms.go_next(
                    dest_cell_code=dest_cell.id,
                    update_task_id=task_number,
                    stay_flag=False,
                    robot_id=None,
                    is_continue=is_continue
                )

            logger.info(f"""[OperationRMS] send_task: STEP {step} ,go_next: {res}""")
            if task_number == -1:
                task_id = self.rms_api.get_task_id(res)
            else:
                task_id = task_number
            
            rms_info = rms.get_rms_info(0)
            ok, _, task = self.wait_for_task(task_id, start_cell, dest_cell.id, kotatsu.id, move=False)
            if not ok:
                logger.error("[OPS] ➀-2 wait_for_task 失敗")

        except Exception as e:
            logger.error(f"[OperationRMS] send_task error: {e}")
            return None, None

        # start_cell 抽出
        start_cell = None
        try:
            for t in rms_info["response"]["body"]["tasks"]:
                if t["taskId"] == task_id:
                    start_cell = t.get("startCellCode")
                    break
        except Exception as e:
            logger.warning(
                "[OperationRMS] Failed to parse rms_info startCellCode: %s", e
            )

        return res, task_id, start_cell

    # ================================================================
    # 9)Wait for RMS task completion
    # ================================================================
    def wait_for_task(self, task_id, start_cell, dest_cell_id, kotatsu_id, move=True,*, timeout_sec=300):
        """
        搬送が完了するまで、タスクの状態を確認する処理

        - DBのタスク管理テーブルをポーリング
        - 完了 / キャンセル / タイムアウト を判定する
        """

        db = self._sql
        start_time = time.time()
        logger.info(f"[OperationRMS] wait_for_task (task_id={task_id}, dest_cell={dest_cell_id}, 棚搬送:{move})")

        time.sleep(0.5)
        
        status = None
        phase = None
        instruction = None
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                logger.error(
                    f"[OperationRMS] wait_for_task timeout "
                    f"(task_id={task_id}, elapsed={elapsed:.1f}s)"
                )
                # continue
                # return False, task_id, None

            try:
                # タスクの状態を管理するテーブルからタスクの情報を取得する処理
                with db.cursor_ctx(dictionary=True) as cur:
                    cur.execute(db.get_op_task_status(), (task_id,))
                    rows = cur.fetchall() or []
                    # logger.info(f"[OperationRMS] wait_for_task DB rows: {rows}")
            except Exception as e:
                logger.error(f"[OperationRMS] wait_for_task DB error: {e}")
                return False, task_id, None

            # RMS → DB 反映待ち（初期状態）
            if not rows:
                time.sleep(0.5)
                continue

            row = rows[0]

            # ------------------------------
            # Task domain object
            # ------------------------------
            task = Task(task_id)
            task.set_type(row.get("task_type"))
            task.set_status(row.get("status"))
            task.set_instruction(row.get("instruction"))
            task.set_phase(row.get("phase"))
            task.set_robot_id(row.get("robot_id"))
            task.set_dest_cell(row.get("dest_cell"))
            task.set_start_cell(start_cell)
            task.set_shelf(kotatsu_id)
            
            if (task.status == status and
                task.phase == phase and
                task.instruction == instruction):
                status = task.status
                phase = task.phase
                instruction = task.instruction
                logger.info(
                    "[OperationRMS] wait task=%s status=%s phase=%s instruction=%s dest=%s",
                    task_id,
                    task.status,
                    task.phase,
                    task.instruction,
                    task.dest_cell,
                )

            # ✅ Persist cancellation state
            """"""
            self.persist_task_status(task)
            
            # ------------------------------
            # Completion判定
            # -----------------------------
            # logger.info(
            #     "[OperationRMS] ju taskid=%s SHELF_ARRIVED=%s READY=%s cell:%s=%s",
            #     task_id,
            #     task.phase,
            #     task.instruction,
            #     task.dest_cell,
            #     dest_cell_id,
            # )
            if (move == True
                and task.phase == "SHELF_ARRIVED"
                and task.instruction == "READY"
                and int(task.dest_cell) == int(dest_cell_id)
            ) or (move == False
                and task.phase == "ARRIVED"
                and task.instruction == "READY"
                and int(task.dest_cell) == int(dest_cell_id)
            ) or (
                task.status == "COMPLETED"
                and int(task.dest_cell) == int(dest_cell_id)
            ):
                logger.info(
                    "[OperationRMS] Task completed "
                    "(task_id=%s, dest_cell=%s)",
                    task_id, dest_cell_id
                )
                return True, task_id, task

            # ------------------------------
            # キャンセル判定
            # ------------------------------
            if task.status == "CANCELED":
                logger.error(
                    f"[OperationRMS] Task canceled "
                    f"(task_id={task_id})"
                )
                return False, task_id, task
    
            time.sleep(1)
    
    # ================================================================
    # 10)persist_task_status
    # ================================================================        
    def persist_task_status(self, task: Task):
        """
        Insert or update task status in DB
        """
        with self._sql.cursor_ctx(dictionary=True) as cur:
            cur.execute(self._sql.op_task_exists(), (task.id,))
            exists = cur.fetchone()["cnt"] > 0

    # ✅ normalize end_cell
        end_cell = task.dest_cell
        if end_cell == "":
            end_cell = None

        params = (
            task.robot_id,
            task.status,
            end_cell,
            task.phase,
        )

        with self._sql.write_cursor_ctx() as cur:
            if exists:
                cur.execute(
                    self._sql.op_update_task(),
                    (*params, task.id)
                )
            else:
                cur.execute(
                    self._sql.op_insert_task(),
                    (task.id, *params)
                )
    
    # ================================================================
    # 11) LIFT STATION UPDATE リフトセルの状態をクリアする処理
    # ================================================================
    def set_lift_plat(self, task: Task, cell: Cell, flag):
        
        if flag:
            sql = self._sql.op_clear_lift_station()
            params = (cell.id,)
        else:
            sql = self._sql.op_set_lift_station_pallet()
            params = (task.shelf, cell.id)

        with self._sql.write_cursor_ctx() as cur:
            cur.execute(sql, params)

    # ================================================================
    # 12) Operation_start,stop → request_execution 変更, 
    # ================================================================
    def operation_update(self, line_id, condition):
        # Convert condition → request_flag / request_execution
        if condition == "COMP":
            execution = 0
            request = 0
            permition = 0
            sql = self._sql.op_request_reset()
            with self._sql.write_cursor_ctx() as cur:
                cur.execute(sql, (request, permition, execution, line_id))
        elif condition == "WORK":
            execution = 1
            sql = self._sql.op_request_receive()
            with self._sql.write_cursor_ctx() as cur:
                cur.execute(sql, (execution, line_id))
        else:
            execution = 0

    # ================================================================
    # ??) t_line_status のパレット番号更新
    # ================================================================
    def update_line_pallet(self, line_id, pallet_id):
        sql = self._sql.update_line_pallet()
        with self._sql.write_cursor_ctx() as cur:
            cur.execute(sql, (pallet_id, line_id))

    # ================================================================
    # ??) t_pallet_statusの各時間更新
    # ================================================================
    def update_pallet_time(self, pallet_id, slot):
        sql = self._sql.pallet_time_set(slot)
        with self._sql.write_cursor_ctx() as cur:
            cur.execute(sql, (pallet_id,))
    
    # ================================================================
    # t_line_status の permition 取得
    # ================================================================
    def get_permition(self, line_id: int) -> bool:
        sql = self._sql.select_permition()
        logger.info("[OperationRMS] get_permition SQL Query: %s", sql)
        with self._sql.cursor_ctx(dictionary=True) as cur:
            cur.execute(sql, (line_id,))
            row = cur.fetchone()
            logger.info("[OperationRMS] get_permition has exist: %s", row)
            
        if not row:
            logger.debug("[OperationRMS] get_permition does not exist")
            return False

        return bool(row["permition"])

    # ================================================================
    # t_locationのhas_reservationの取得
    # ================================================================
    def get_reservation(self, cell: Cell) -> bool:
        try:
            sql = self._sql.get_reservation()
            with self._sql.cursor_ctx(dictionary=True) as cur:
                cur.execute(sql, (cell.id,))
                row = cur.fetchone()
                logger.info("[OperationRMS] get_permition has exist: %s", row)
        except Exception as e:
            logger.error(f"[OperationRMS] get_reservation SQL error: {e}")
            return False
        if row == 1:
            return False
        else:
            return True
