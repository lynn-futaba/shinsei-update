

# 岡崎2号棟 出荷 AMR 統合管理システム (WCS)

## 概要 / Project Overview
本システムは、岡崎2号棟におけるAMR（自律走行搬送ロボット）とリフト間口の動作を統合管理するWCS（Warehouse Control System）です。
(This system is a WCS that integrates and manages AMR and Lift Entrance operations.)

### ハイライト (Technical Highlights)
1. **リアルタイム・デジタルツイン**: 
   - 工場レイアウトをSVGで動的可視化。ロボットの現在地と経路をリアルタイム監視。
2. **堅牢なデータ整合性 (Concurrency Control)**:
   - 楽観的ロック（Revision管理）を実装し、複数作業者による同時操作エラーを完全に防止。
3. **拡張性の高いアーキテクチャ**:
   - Repository PatternとDIコンテナを採用。本番環境(MySQL/RMS)とテスト環境(Fake)を1スイッチで切替可能。
4. **高可用性ロギング**:
   - 障害発生時の原因特定を容易にするため、RMSとの通信全履歴をDBおよびログファイルに保存。

開発環境設置
> Flask (Python 3.11.9、request==2.32.3、flask==2.3.2、pillow==9.5.0) + VSCode仮想環境の移管方法 + MySQL based AMR operation support:
> - 管理画面 (Admin): 機能名 → マップ情報、エラー表示、自動/各個モード、各個モード(各個操作)、ライン状態表示、リフト間口操作画面、ステータス表示
> - 作業者画面 (Worker): リフト間口操作画面、空パレット供給スケジュール 
> - リフト間口画面 (Liftman): 間口１～７、ライン、アクション
> - 空パレット供給スケジュール画面 (Empty Pallet Scheduling): 機能名 → 読出、削除、変更、追加
> - RMS API 連携: マップモニタリング取得、コールバックAPI受信とDB保存（将来、他PJがDBを利用）

---

## 目次
- [アーキテクチャ概要](#アーキテクチャ概要)
- [ディレクトリ構成](#ディレクトリ構成)
- [設置【セットアップ】](#セットアップ)
- [設定 (config.py)](#設定-config.py)
- [起動方法](#起動方法)
- [フェイク(FAKE)/本物(REAL) 切替](#fakereal-切替)
- [主要エンドポイント](#主要エンドポイント)
- [RMS コールバック仕様](#rms-コールバック仕様)
- [DB スキーマ](#db-スキーマ)
- [ログ](#ログ)
- [運用/トラブルシュート](#運用トラブルシュート)

---

## アーキテクチャ概要

- **アプリ**: Flask アプリ (`app_factory.py`)  
- **DI コンテナ**: `services_container.py` で フェイク(FAKE)/本物(REAL) の切り替えと依存解決  
- **ドメイン**: `domain/` に値オブジェクト・エンティティ・API返却整形  
- **インフラ**: `interfaces/sql/` (DB アクセス), `interfaces/api_client/` (RMS API)  
- **サービス**: 業務ロジックは `services/` に集約  
- **コントローラ**: ルート管理 `controllers/`に 管理コントローラルート、作業コントローラルート、 
- **プレゼンテーション**: `templates/` + `static/`  
- **RMS 連携**:
  - モニタ: `rms_monitoring_service.py`（管理画面でSVGレンダリング）
  - コールバック: `rms_callback_service.py`（DBへ保存 + ACK返却）

---

## ディレクトリ構成
- app/
  - common/
    - config.py
    - config.example.py
    - setup_log.py
  - controllers/
    - admin_controller.py
    - worker_controller.py
  - domain/
    - api_response_format.py
    - entities.py
    - exception.py
    - rms_domain.py
    - value_objects.py
  - infrastructure/
    - factory/
      - db_factory.py
      - domain_factory.py
    - repositories/
      - manage_repository.py
      - worker_repository.py
      - fake/
        - fake_manage_repository.py
        - fake_worker_repository.py
  - interfaces/
    - api_client/
      - post_rms_api.py
      - rms_callback_api.py
      - rms_monitor.py
    - fake/
      - fake_wcs_sql_query.py
    - sql/
      - wcs_sql_query.py
      - eip_sql_query.py
      - iotds_sql_query.py
  - logs/
    - admin_controller.log
    - manage_service.log
  - services/
    - manage_service.py
    - rms_monitoring_service.py
    - rms_callback_service.py
    - rms_manual_service.py
    - lift_entrance_service.py
    - pallet_supply_service.py
    - services_container.py
  - static/
  - css/
  - images/
  - js/
    - admin.js
    - lift-entrance.js
    - pallet-supply.js
  - templates/
    - admin/
      - dashboard.html
    - worker/
      - lift-entrance.html
      - pallet-supply.html  
- app_factory.py
- README.md

---

## セットアップ

> 前提: Python 3.11.9,  (推奨)

```bash
# 1) 仮想環境
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2) 依存ライブラリ
pip install -U pip
pip install -r requirements.txt   # ない場合は後で作成

# 3) 設定ファイル
cp app/common/config.example.py app/common/config.py
# → 接続情報、USE_FAKE、RMS_* を編集
```
---

## 設定 (config.py)
app/common/config.py の主な項目（例）:
```bash
# 実行モード
USE_FAKE = True  # True: DB/API をフェイク, False: 実DB/実RMS

# MySQL (WCS/EIP/IOTDS)
MYSQL_WCS_DB = {"host":"127.0.0.1","port":3306,"user":"user","password":"pass","database":"futaba_ok2_shippment"}
MYSQL_EIP_DB = {"host":"127.0.0.1","port":3306,"user":"user","password":"pass","database":"eip_db"}
MYSQL_IOTDS_DB = {"host":"127.0.0.1","port":3306,"user":"user","password":"pass","database":"iotds_db"}

# RMS 接続
RMS_IP = "192.168.x.y"
RMS_PORT = 8080

# RMS Callback ACK 構築用
RMS_CALLBACK_CLIENT_ID = "clientid"
RMS_VERSION = "3.3.0"
RMS_AUTH_CODE = "ca5ebc4251374e35a5f6afb2a52fd6dd"

# ログ
LOG_FOLDER = "app/logs"
LOG_FILE = "app.log"
ADMIN_CTRL_LOG_FILE = "admin_controller.log"
BACKUP_DAYS = 7
```

# 起動方法
```bash
export FLASK_ENV=development
python app_factory.py
# → http://localhost:5000/manage/admin/dashboard (例)
```

## FAKE/REAL 切替

- FAKE: USE_FAKE=True
  - DB ラッパはフェイク接続
  - マップやコールバックはフェイクサービスも利用可能

- REAL: USE_FAKE=False
  - 実 DB 接続 (ping/簡易クエリで疎通チェック)
  - RMSMonitoringService, RMSCallbackService を DI

## 主要エンドポイント
管理画面 (例)
- GET /manage/admin/dashboard
  - マップ監視など（テンプレート: templates/admin/dashboard.html）

マップモニタ API
- GET /manage/api/v1/rms_map_monitor

  - 返却:
  ```bash
  {  
    "status":"success",  
    "data": {
        "size": [1200, 800],
        "cells": [...],
        "kotatsus": [...],
        "amrs": [...]  
    }
  }
  ```
  - フロントは static/js/map.js で SVG を描画

- RMS コールバック (UI不要)

  - POST /manage/api/v1/rms/callback
    - 入力: RMS からの RobotTaskCallbackMsg (vendor spec)
    - 処理: RMSCallbackService.handle_robot_task_callback()
      - t_task_events に イベント全文JSON を保存（冪等）
      - t_task_status に 最新状態 を upsert
    - 出力: ベンダー仕様の ACK JSON を返却（ラップ無し）

## RMS コールバック仕様
- サンプル入力 (実データ例)
```bash
{
  "id":"clientid",
  "msgType":"RobotTaskCallbackMsg",
  "request":{
    "header":{"warehouseCode":"*","requestId":"07b1aa66-...","version":"3.3.0"},
    "body":{
      "taskId":3707928,
      "robotId":3441913,
      "taskStatus":"EXECUTING",
      "taskPhase":"GO_FETCHING",
      "taskType":"DELIVER_SHELF",
      "instruction":"GO_FETCH",
      "destCellCode":"40550019",
      "shelfCode":"44066",
      "destLocation":{"x":55.79,"y":19.25,"z":1}
    }
  }
}
```
ACK 出力 (例)
```bash
  {
  "id": "clientid",
  "msgType": "RobotTaskCallbackMsg",
  "request": {
    "header": {
      "responseId": "07b1aa66-...",
      "code": "ca5ebc4251374e35a5f6afb2a52fd6dd",
      "msg": "3.3.0"
    },
    "body": {}
  }
}
```

## DB スキーマ
- DB
---

## ログ
- app/logs/
  - admin_controller.log, manage_service.log ほか
- app/common/setup_log.py でローテーション/フォーマット設定

## 運用/トラブルシュート

- マップが白い:

  - Network タブで /manage/api/v1/rms_map_monitor のレスポンス確認
  - resp.data アンラップ済みか (map.js)
  - jQuery が map.js より前に読み込まれているか


- コールバックが 5xx:

  - DB スキーマと権限
  - 例外ログ ([callback] status upsert failed ...)
  - ACK を success ラップしていないか（純ACKを返すこと）