# ChessDNA

線上棋譜 → 棋力評估（CPL / accuracy / blunder rate 等）＋棋風特徵建模，並支援「棋風模仿」的延伸方向。

## MVP (Phase 1)

- 輸入
  - PGN（單盤 / 多盤）
  - 線上抓棋譜：Lichess / Chess.com（輸入 username）
- 輸出
  - 每盤：平均 CPL、accuracy%、錯誤類型、turning points（逐步完善中）
  - 玩家總覽：棋風特徵（規劃中）

## Run (local)

> Windows 終端顯示中文若出現亂碼：建議使用 **Windows Terminal + PowerShell**，並先執行 `chcp 65001`（UTF-8），或在 VS Code 內建終端執行。

### Web

```powershell
cd D:\code\ChessDNA
pip install -e .
.\run_dev.ps1
# open http://127.0.0.1:8004
```

### CLI

```powershell
# (option A) use installed console script
# fetch PGN from lichess
chessdna fetch --platform lichess --user orange_bot --max 10 --out games.pgn

# fetch PGN from chess.com
chessdna fetch --platform chesscom --user hikaru --max 10 --out games_chesscom.pgn

# (option B) run via python -m (no console script required)
python -m chessdna pgninfo --pgn games.pgn --max-games 200

# quick validate/summarize PGN (no engine required)
chessdna pgninfo --pgn games.pgn --max-games 200

# minimal self-test (pgninfo + best-effort analyze)
# - if Stockfish path is missing, it will auto-skip analyze
chessdna selftest --pgn _sample_orange_bot.pgn

# analyze PGN with Stockfish
chessdna analyze --pgn games.pgn --engine D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe --t 0.05 --max-plies 200 --out report.json
```

## Web UX：線上抓棋譜（MVP 流程）

1) 平台選擇：Lichess / Chess.com
2) 輸入 username、fetch_max
3) 顯示最近對局清單
4) 勾選要分析的對局（可多選）
5) 按 Analyze 產出報告

## Limitations (MVP)

- Web UI 目前用 token / report_id 主要做「記憶體 mapping（in-memory）」
  - 伺服器重啟後 mapping 會清空
  - 但後端 best-effort 會把 PGN / 報告寫到系統 temp，所以下次帶著 token 仍可能在有效期內找得到（不保證）
  - temp 自動清理（startup 時 best-effort）：
    - 報告預設保留 7 天（可用 `CHESSDNA_REPORT_TMP_MAX_AGE_HOURS` 調整）
    - 線上抓取 PGN 預設保留 48 小時（可用 `CHESSDNA_FETCH_TMP_MAX_AGE_HOURS` 調整）
- 線上抓棋譜受 API / 網路影響
- fetch_max 目前限制 1~50，避免一次拉太多造成 UI 等太久或伺服器卡住

## Phase 2（發想）

- 棋風模仿
  - 輕量偏好特徵：trade / attack / complexity / risk…
  - 走混合模型：top-k 候選 + style consistency

## Dev

- Python 3.11+（目前環境 3.13 也可）
