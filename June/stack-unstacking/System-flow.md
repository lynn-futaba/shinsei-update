
✅ 1. Purpose (目的)
Currently, people manually take TP boxes and store them. 
So we want to create a model line to automate stacking and unstacking work currently done by humans.
リフトを活用して、段積み・段バラシ作業の無人化モデルラインを構築する。
👉 We want to reduce human work using machines (AMR + lift system).

✅ 2. Overview (概要)
The system transports items into and out of the stacking/unstacking process.
本システムは、段積み・段バラシ工程への搬入および搬出を行う。

The system moves TP boxes:
IN → to stacking/unstacking area 
OUT → after processing
👉 It is basically an automation flow system

✅ 3. Current Problem/ Issue (課題)
Currently, workers manually take TP boxes from the skid and store them on shelves.
現在、仕入先から納入されたTP箱を、作業者がスキット上から取り出し、部品棚へ手作業で収納している。
Supplier → Skit → Worker → Shelf

✅ 4. Goal (目標)
Automate stacking and unstacking of TP boxes before the exhibition.
生技展示会までに、TP箱の段積み・段バラシ作業の自動化を実現する。
Skit → Machine → Automatic stacking/unstacking

✅ 5. System Story (システムの流れ) / システムストーリー
The forklift places the skit onto the lift station, and the forklift presses the input button to start transport.
フォークリフトがスキットをコタツに載せ、フォークリフトが投入完了ボタンを押すことで、段積み・段バラシ工程へ搬送が開始される。

Forklift places skit on kotatsu → forklift presses button → system transports
(1) A forklift places a skid with TP boxes onto kotatsu of the lift station.　
フォークリフトがスキットをコタツに設置する。

(2) Forklift presses "input complete" button.　
フォークリフトが「投入完了ボタン」を押す。

(3) WCS receives signal.　
WCSが信号を受信する。

(4.1) WCS sends signal to IOTDataShare which connected with PLC to process input/output signal flow of stacking/unstacking machine.
WCSは信号をIOTDataShareに送ります。IOTDataShareはPLCに接続されていて、積み重ね/積み下ろし機の入出力信号の流れを処理します。

(4.2) WCS sends a transport command to the AMR.
WCSがAMRへ搬送指示を出す。

(5) AMR transports the skid to the stacking/unstacking area. 
AMRがスキットを段積み・段バラシエリアへ搬送する。

(6) WCS sends a command to the stacking or unstacking process. 
WCSが段積みまたは段バラシ工程設備へ処理指示を出す。

(7) The machine performs stacking or unstacking.　
段積みまたは段バラシを実行する。

(8) The system confirms completion. 
システムが処理完了を確認する。

(9) The processed items are sent to storage or output. 
処理されたTP箱は保管または搬出される。

(10)The system returns to idle state. 
システムは待機状態に戻る
   

✅ 7. System Components（構成要素）/ アクター定義

リフトマン (Forklift)
AMR / RMS 
WCS (制御システム)
段積み.段バラシ 設備 Stacking/Unstacking machine
コタツ (Kotatsu)
スキット(Skit)
TP箱

✅ 8. System States（状態定義）

IDLE（待機）→ doing nothing
WAITING_INPUT（投入待ち）→ waiting for button press
TRANSPORTING（搬送中）→ AMR moving skid
STACKING（段積み中）→ stacking process
UNSTACKING（段バラシ中）→ unstacking process
COMPLETED（完了）→ process finished
ERROR（異常）→ something went wrong

🟢 Context diagram = “map of world”
“Who interacts with the system?”
- Shows system boundary
- Shows external actors
- Does NOT show detailed functions

参加者

リフトマン ⇒ 投入ボタン押すと信号をWCSに送って iOTDSに信号入力する　RMS搬送開始してAMR移動する。（リフト画面）
　　管理者 ⇒ AMR運行操作、AMR異常情報、AMR運行状況、タスク状態、自動/各個操作コントロール（管理画面）

流れ
投入ボタン押 → WCS　→　iOTDS →　PLC
　　　　　　　 WCS  →  AMR

🟢 Use case diagram = “(menu - service level)”
“What can the system do?”
“What functions does system provide?”

actions
details of context diagram.
It includes WCS support services, RMS API connection, 

🟢 Activity Diagram (step-by-step) / アクティビティ図（最重要）

Start 開始
   ↓
Forklift places skidスキット設置（フォークリフト）
   ↓
Liftman presses button ボタン押下（リフト作業者）
   ↓
WCS receives signal (WCS信号受信)
   ↓
WCS sends command to AMR (AMR搬送開始)
   ↓
AMR transports skid  (工程へ搬送)
   ↓
Arrive at processing area 
   ↓
Stacking / Unstacking 段積み/段バラシ実行
   ↓
Completion confirmed 完了確認
   ↓
System updates status 状態更新
   ↓
End 終了

Activity Diagram

Start
 ↓
Forklift places skid
 ↓
Press input button
 ↓
WCS receives signal
 ↓
Send signal to IoT/PLC
 ↓
Send command to AMR
 ↓
AMR transports skid
 ↓
AMR arrives?

YES ↓
WCS decides process
 ↓
[Decision]
   ├─ Stacking
   │     ↓
   │   Machine executes stacking
   └─ Unstacking
         ↓
      Machine executes unstacking

 ↓
Process complete?
 ↓
YES
 ↓
WCS confirms completion
 ↓
Send AMR to output
 ↓
AMR transports to storage/output
 ↓
End → back to waiting

✅ 12. Key idea 👉 WCS (the brain)
Flow: Liftman → WCS → AMR → Machine → Output


