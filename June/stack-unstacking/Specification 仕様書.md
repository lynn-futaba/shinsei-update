Specification 仕様書
ウォーターフォールとは、工程が上から下へ順番に流れる開発手法です。
一つの工程が完了したら、次の工程に進みます。

仕様検討（Spec）
→ モデリング（Modeling）
→ 要件定義（Requirements）
→ 基本設計（Basic Design）
→ 詳細設計（Detail Design）
→ 実装（Coding）
→ テスト（Test）

職務分担　(Division of tasks)
Think → Confirm → Design → Confirm → Build


Overview 概要

🟢 STEP 1: Read specification like a story

Ask:
Who starts the process?
What triggers stacking?
What is input?
What is output?
What can go wrong?

👉 Write in simple English or broken Japanese.

🟢 STEP 2: Extract 5 key things

From spec, identify:

1. Actors (Liftman リフトマン, 管理者), 
System ( PLC[stacking/unstacking Robot], IOTDataShare, WCS, RMS, AMR )

2. Inputs
signal ON
command request

3. Outputs
stack complete
error signal

4. States
idle
running
error

5. Flow
step by step process

🟢 STEP 3: Convert into diagrams

Then you draw.

🧠 4. Simple mental model (VERY IMPORTANT)

Think like this:

🟢 Context diagram = “map of world”
who exists around system

🟢 Use case diagram = “what users do(menu)”
actions

🟢 State transition diagram = “mood of system”
system condition changes

🟢 Activity diagram = “recipe”
step-by-step cooking process

✅ Simple Explanation （説明用フレーズ）

This system automates the transport and stacking/unstacking of TP boxes.
The liftman only needs to place the skit and press a button.
After that, WCS controls AMR and machines automatically.

本システムはTP箱の搬送および段積み・段バラシ作業を自動化するものです。
リフト作業者はスキットを設置し、ボタンを押すだけで操作できます。
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




