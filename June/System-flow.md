
✅ 1. Purpose (目的)
リフトを活用して、段積み・段バラシ作業の無人化モデルラインを構築する。
Create a model line to automate manual stacking and unstacking work using a lift system.

Simple meaning:
Right now, people manually take TP boxes and store them.
Create a model line to automate stacking and unstacking work currently done by humans.

👉 You want to reduce human work using machines (AMR + lift system).

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

✅ 5. AMR Flow(AMRの流れ)
The forklift places the skid onto the lift station, and the operator presses the input button to start transport.
フォークリフトがスキットをコタツに載せ、作業者が投入完了ボタンを押すことで、段積み・段バラシ工程へ搬送が開始される。

Forklift places skid on kotatsu → operator presses button → system transports
(1) Forklift places skid on station (kotatsu)
(2) Operator presses "input complete" button
(3) WCS receives signal
(4) AMR moves skit
(5) Send to stacking/unstacking process

✅ 6. System Story (システムの流れ) / システムストーリー
1. フォークリフトがスキットをコタツに設置する
   A forklift places a skid with TP boxes onto kotatsu of the lift station.

2. 作業者が「投入完了ボタン」を押す。
   The operator presses the "input complete" button.

3. WCSが信号を受信する
   The WCS receives the signal.

4. WCSがAMRへ搬送指示を出す
   The WCS sends a transport command to the AMR.

5. AMRがスキットを段積み・段バラシエリアへ搬送する。
   The AMR transports the skid to the stacking/unstacking area.

6. WCSが設備へ処理指示を出す
   The WCS sends a command to the stacking or unstacking machine.

7. 段積みまたは段バラシを実行する
   The machine performs stacking or unstacking.

8. システムが処理完了を確認する。
   The system confirms completion.

9. 処理されたTP箱は保管または搬出される。
   The processed items are sent to storage or output.
   
10. システムは待機状態に戻る
   The system returns to idle state.

✅ 7. System Components（構成要素）/アクター定義 System Components (構成要素)

作業者 (Operator)
フォークリフト (Forklift)
AMR
WCS (制御システム)
段積み設備 Stacking machine
段バラシ設備 Unstacking machine
コタツ (Kotatsu)

✅ 8. System States（状態定義）
IDLE（待機）→ doing nothing
WAITING_INPUT（投入待ち）→ waiting for button press
TRANSPORTING（搬送中）→ AMR moving skid
STACKING（段積み中）→ stacking process
UNSTACKING（段バラシ中）→ unstacking process
COMPLETED（完了）→ process finished
ERROR（異常）→ something went wrong

✅ 9. Simple Explanation for Supervisor（説明用フレーズ）

This system automates the transport and stacking/unstacking of TP boxes.
The operator only needs to place the skit and press a button.
After that, WCS controls AMR and machines automatically.

本システムはTP箱の搬送および段積み・段バラシ作業を自動化するものです。
作業者はスキットを設置し、ボタンを押すだけで操作できます。
その後はWCSがAMRと設備を自動制御します。

✅ ① （理解確認）
人がやっている 段積み・段バラシ作業を自動化
AMR＋リフトでラインを作る
フォークリフト → コタツ → AMR → 工程 → 完了

👉 本質：
「TP箱の搬送と積み下ろしを自動制御するシステム」

✅ ② 図にする前の「整理」
🎯 入力・トリガー・出力

入力：
・TP箱 (スキット上)

トリガー：
・投入完了ボタン

処理：
・AMR搬送
・段積み / 段バラシ

出力：
・処理完了されたTP箱 (棚 or 搬出)

✅ 10. Activity Flow (step-by-step)
This is what you draw:
Start開始
↓
Forklift places skidスキット設置（フォークリフト）
↓
Operator presses button
↓
WCS receives signal
↓
WCS sends command to AMR
↓
AMR transports skid
↓
Arrive at processing area
↓
Stacking / Unstacking
↓
Completion confirmed
↓
System updates status
↓
End

4. アクティビティ図（最重要）

 ↓

 ↓
ボタン押下（作業者）
 ↓
WCS信号受信
 ↓
AMR搬送開始
 ↓
工程へ搬送
 ↓
段積み/段バラシ実行
 ↓
完了確認
 ↓
状態更新
 ↓
終了

✅ 12. Key idea
👉 WCS (the brain)
Flow: Operator → WCS → AMR → Machine → Output


