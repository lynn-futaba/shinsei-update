"""
マップ構成要素定義 (Map Components)
作成者: Lynn
----------------------------------
【役割】
工場内の「物理的な構成要素（セル、AMR、コタツ、マップ全体）」をプログラム上で表現するクラス群です。
シミュレーションやリアルタイムの監視画面での描画、位置計算のベースとなります。

【各クラスの概要】
1. Cell: 床面の区画。位置やサイズ、現在何かが置かれているか（占有）を管理します。
2. AMR: 自動走行搬送ロボット。現在地、向き、割り当てられたタスクを保持します。
3. Kotatsu: 搬送対象となる架台（コタツ）。パレットの有無や、どのAMRが運んでいるかを管理します。
4. Map: 上記すべての要素を統合して管理するコンテナです。
"""
from datetime import datetime

class Cell:
    def __init__(
            self,
            cellCode: int,
            cellType: str,
            size: tuple[int, int],
            location: tuple[int, int, int],
            flag: str = "NORMAL",
            type: str = "DEFAULT",
            angle: int = 0
    ):
        self._cellCode = cellCode  # セルのID
        self._location = location  # セルの位置(x, y, z)
        self._cellType = cellType  # セルのタイプ(RMS仕様)
        self._cellFlag = flag  # セルの状態フラグ(RMS仕様)
        self._size = size  # セルの状態フラグ(RMS仕様)
        self._type = type  # セルのタイプ(アプリ仕様)=使用用途
        if angle == 0:  # コタツの向き(アプリ仕様)
            self._angle = 0
        elif angle == 90:
            self._angle = 90
        elif angle == 180:
            self._angle = 180
        elif angle == -90:
            self._angle = -90
        elif angle == -180:
            self._angle = -180
        self._angle = angle  # コタツの向き(アプリ仕様)
        self._kotatsu_id = None  # セルに配置されているパレットのID
        self._is_occupied = False  # セルが占有されているかどうかを示すフラグ
        self._carrier_flg = False  # セルに搬送が有るかを示すフラグ

    @property
    def location(self):
        """セルの位置を取得します。"""
        return self._location

    @property
    def size(self):
        """セルのサイズを取得します。"""
        return self._size

    @property
    def id(self):
        """セルのIDを取得します。"""
        return self._cellCode

    @property
    def celltype(self):
        """セルのタイプを取得します。"""
        return self._cellType

    @property
    def cellflag(self):
        """セルの使用可不"""
        return self._cellFlag

    @property
    def type(self):
        """セルのタイプを取得します。"""
        return self._type

    @property
    def angle(self):
        """セルに配置するコタツの向きを取得します。"""
        return self._angle

    @property
    def kotatsu_id(self):
        """セルに配置されているパレットのIDを取得します。"""
        return self._kotatsu_id

    @property
    def is_occupied(self):
        """セルがコタツに占有されているかどうかを取得します。"""
        return self._is_occupied

    @property
    def carrier(self):
        """セルの搬送が有るかを取得します。"""
        return self._carrier_flg

    def set_kotatsu_id(self, kotatsu_id):
        """セルに配置されているパレットのIDを設定します。"""
        self._kotatsu_id = kotatsu_id

    def set_occupant(self, kotatsu_id):
        """セルをコタツで占有します。"""
        if self._is_occupied is True:
            return False
        self._is_occupied = True
        self._kotatsu_id = kotatsu_id
        return True

    def clear_occupant(self):
        """セルの占有状態をクリアします。"""
        self._kotatsu_id = None
        self._is_occupied = False

    def set_carrier(self):
        """セルに搬送待ちを設定します。"""
        if self._carrier_flg:
            return False
        self._carrier_flg = True
        return True

    def clear_carrier(self):
        """セルに搬送待ちを設定します。"""
        self._carrier_flg = False
        
class AMR:
    def __init__(
            self,
            id: int,
            name: str,
            angle: float,
            mode: str,
            path: list,
            location: tuple[int, int, int] = None
    ):
        self._id = id
        self._name = name
        self._angle = angle
        self._location = location
        self._mode = mode
        self._path = path
        self._task_id = None
        self._status = None

    @property
    def id(self):
        """AMRのIDを取得します。"""
        return self._id

    @property
    def name(self):
        """AMRの名前を取得します。"""
        return self._name

    @property
    def location(self):
        """AMRの現在位置を取得します。"""
        return self._location
    
    @property
    def angle(self):
        """AMRの現在の向きを取得します。"""
        return self._angle

    @property
    def path(self):
        """AMRの現在位置を取得します。"""
        return self._path

    @property
    def task_id(self):
        """AMRに割り当てられたタスクIDを取得します。"""
        return self._task_id

    @property
    def mode(self):
        """AMRの現在のモードを取得します。"""
        return self._mode

    @property
    def status(self):
        """AMRの現在の状態を取得します。"""
        return self._status

    def set_location(self, z: int, x: int, y: int, angle: float):
        """AMRの位置を設定します。"""
        self._location = (z, x, y)
        self._angle = angle

    def assign_task(self, task_id: int):
        """AMRにタスクを割り当てます。"""
        self._task_id = task_id

    def clear_task(self):
        """AMRのタスクをクリアします。"""
        self._task_id = None

    def set_status(self, status: str):
        """AMRの状態を設定します。"""
        self._status = status

    def __repr__(self):
        return f"""
            AMR(
                id={self._id},
                name={self._name},
                status={self._status},
                location={self._location},
                task_id={self._task_id}
                )"""


class Kotatsu:
    def __init__(
                    self,
                    id: int,
                    status: str,
                    type: int,
                    size: tuple[int, int],
                    angle: int,
                    location: tuple[int, int, int]
                ):
        self._id = id  # コタツのID
        self._status = status  # コタツの倉庫状態(RMS仕様)
        self._cellcode = None  # コタツの(アプリ仕様)=使用用途
        self._size = size  # コタツのサイズ(RMS仕様)
        if -15 <= angle <= 15:  # コタツのサイズ(RMS仕様)
            self._angle = 0
        elif 75 <= angle <= 105:
            self._angle = 90
        elif 165 <= angle <= 195 or -190 <= angle <= -170:
            self._angle = 180
        elif 255 <= angle <= 285 or -100 <= angle <= -80:
            self._angle = -90
        self._type = type  # コタツのタイプ(アプリ仕様)=使用用途
        self._location = location  # コタツの位置(x, y, z)
        self._pallet_id = None  # コタツに配置されているパレットのID（配置されていない場合はNone）
        self._is_occupied = False  # 占有されているかどうかを示すフラグ
        self._occupant_id = None  # 占有しているAMRのID（占有されていない場合はNone）

    @property
    def id(self):
        """こたつのIDを取得します。"""
        return self._id

    @property
    def location(self):
        """こたつの現在位置を取得します。"""
        return self._location,

    @property
    def angle(self):
        """こたつの現在の向きを取得します。"""
        return self._angle

    @property
    def size(self):
        """こたつのサイズを取得します。"""
        return self._size

    @property
    def status(self):
        """こたつの状態を取得します。"""
        return self._status

    @property
    def pallet_id(self):
        """こたつに配置されているパレットのIDを取得します。"""
        return self._pallet_id

    @property
    def cellcode(self):
        """こたつの配置されているセルコードを取得します。"""
        return self._cellcode

    @property
    def occupant_id(self):
        """こたつを占有しているAMRのIDを取得します。"""
        return self._occupant_id

    @property
    def is_occupant(self):
        """こたつを占有状態を取得します。"""
        return self._is_occupied

    def set_cellcode(self, cellcode: int):
        """こたつの配置されているセルコードを設定します。"""
        self._cellcode = cellcode

    def set_location(self, z: int, x: int, y: int):
        """こたつの位置を設定します。"""
        self._location = (z, x, y)

    def set_pallet(self, pallet_id: int):
        """こたつにパレットを配置します。"""
        self._pallet_id = pallet_id

    def clear_pallet(self):
        """こたつのパレットをクリアします。"""
        self._pallet_id = None

    def set_occupant(self):
        """こたつが占有します。"""
        if self._is_occupied is True:
            return False
        self._is_occupied = True
        return True

    def clear_occupant(self):
        """占有をクリアします。"""
        self._is_occupied = False
        self._occupant_id = None

    def __repr__(self):
        return f"""
            Kotatsu(
                id={self._id},
                location={self._location},
                pallet_id={self._pallet_id}
                amr_id={self._occupant_id}
                )"""


class Map:
    def __init__(self):
        self._cells = []
        self._amrs = []
        self._kotatsus = []

    @property
    def cells(self):
        """マップ内のセルのリストを取得します。"""
        return self._cells

    @property
    def amrs(self):
        """マップ内のセルのリストを取得します。"""
        return self._amrs

    @property
    def kotatsus(self):
        """マップ内のセルのリストを取得します。"""
        return self._kotatsus

    def clear_map(self):
        """マップ内のセルをクリアします。"""
        self._cells = []
        self._amrs = []
        self._kotatsus = []

    def add_cell(self, cell: Cell):
        """マップにセルを追加します。"""
        self._cells.append(cell)

    def add_amr(self, amr: AMR):
        """マップにAMRを追加します。"""
        self._amrs.append(amr)

    def add_kotatsu(self, kotatsu: Kotatsu):
        """マップにこたつを追加します。"""
        self._kotatsus.append(kotatsu)

class Pallet:
    def __init__(
            self,
            id: int,
            type: int,
            status: str,
            # location: int = None,
            input_time: datetime = None,
            complete_time: datetime = None,
            angle: int = 0
    ):
        self._id = id
        self._type = type
        self._status = status
        # self._location = location
        self._input_time = input_time
        self._complete_time = complete_time
        if angle == 0:  # コタツの向き(アプリ仕様)
            self._angle = 0
        elif angle == 90:
            self._angle = 90
        elif angle == 180:
            self._angle = 180
        elif angle == -90:
            self._angle = -90
        elif angle == -180:
            self._angle = -180

    @property
    def id(self):
        """パレットのIDを取得します。"""
        return self._id

    @property
    def type(self):
        """パレットのタイプを取得します。"""
        return self._type

    @property
    def status(self):
        """パレットのサイズを取得します。"""
        return self._status

    # @property
    # def location(self):
    #     """パレットの現在位置を取得します。"""
    #     return self._location

    @property
    def input_time(self):
        """パレットの投入時間を取得します。"""
        return self._input_time

    @property
    def complete_time(self):
        """パレットの完成時間を取得します。"""
        return self._complete_time

    @property
    def angle(self):
        """パレットのカンバン向きを取得します。"""
        return self._angle

    def set_status(self, status: str):
        """パレットの状態を設定します。"""
        self._status = status

    # def set_location(self, location: int):
    #     """パレットの位置を設定します。"""
    #     self._location = location

    def set_input_time(self, input_time: datetime):
        """パレットの投入時間を設定します。"""
        self._input_time = input_time

    def set_complete_time(self, complete_time: datetime):
        """パレットの完成時間を設定します。"""
        self._complete_time = complete_time


class Task:
    def __init__(
            self,
            id: int,
    ):
        self._id = id
        self._robot_id = None
        self._start_cell = None
        self._dest_cell = None
        self._type = None
        self._status = None
        self._phase = None
        self._instruction = None
        self._shelf = None

    @property
    def id(self):
        """タスクのIDを取得します。"""
        return self._id

    @property
    def robot_id(self):
        """タスクに割り当てられたロボットのIDを取得します。"""
        return self._robot_id

    @property
    def start_cell(self):
        """タスクの開始セルを取得します。"""
        return self._start_cell

    @property
    def dest_cell(self):
        """タスクの目的地セルを取得します。"""
        return self._dest_cell

    @property
    def type(self):
        """タスクのタイプを取得します。"""
        return self._type

    @property
    def status(self):
        """タスクの状態を取得します。"""
        return self._status

    @property
    def phase(self):
        """タスクのフェーズを取得します。"""
        return self._phase

    @property
    def instruction(self):
        """タスクの指示内容を取得します。"""
        return self._instruction

    @property
    def shelf(self):
        """タスクの棚情報を取得します。"""
        return self._shelf

    def set_robot_id(self, robot_id: int):
        """タスクにロボットを割り当てます。"""
        self._robot_id = robot_id

    def set_start_cell(self, start_cell: int):
        """タスクの開始セルを取得します。"""
        self._start_cell = start_cell

    def set_dest_cell(self, dest_cell: int):
        """タスクの目的地セルを取得します。"""
        self._dest_cell = dest_cell

    def set_type(self, type: str):
        """タスクのタイプを設定します。"""
        self._type = type

    def set_status(self, status: str):
        """タスクの状態を設定します。"""
        self._status = status

    def set_phase(self, phase: str):
        """タスクのフェーズを設定します。"""
        self._phase = phase

    def set_instruction(self, instruction: str):
        """タスクの指示内容を設定します。"""
        self._instruction = instruction

    def set_shelf(self, shelf: str):
        """タスクの棚情報を設定します。"""
        self._shelf = shelf
