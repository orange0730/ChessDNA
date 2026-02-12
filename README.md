# ChessDNA

線上抓棋譜 + 棋局評估（CPL / accuracy / blunder rate 等）＋棋風特徵建模。

## MVP (Phase 1)

- 輸入
  - PGN（單盤 / 多盤）
  - 線上抓棋譜：Lichess / Chess.com（輸入 username）
- 輸出
  - 每盤：平均 CPL、accuracy%、錯誤類型、turning points（逐步完善中）
  - 玩家總覽：棋風特徵（規劃中）

## Run (local)

> 若 Windows 終端顯示中文亂碼，建議用 **Windows Terminal + PowerShell**，並先執行 `chcp 65001`（UTF-8），或使用 VS Code 內建終端。

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

# fetch PGN (auto tries Lichess first, then Chess.com)
chessdna fetch --platform auto --user orange_bot --max 10 --out games.pgn

# fetch PGN from lichess
chessdna fetch --platform lichess --user orange_bot --max 10 --out games_lichess.pgn

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

1) 選平台：Lichess / Chess.com（或 Auto）
2) 輸入 username、fetch_max
3) 顯示最近對局清單（preview）
4) 勾選要分析的對局（可多選）
5) Analyze 產出報告

## Limitations (MVP)

- Web UI 使用 token / report_id 做「報告 mapping（in-memory）」
  - 伺服器重啟後 mapping 會消失
  - 但會 best-effort 把 PGN / 報告寫到系統 temp，所以在保留時間內，即使重啟仍可能下載成功（不保證）
- temp 檔案清理（startup / lifespan best-effort）
  - 報告預設保留 7 天，可用 `CHESSDNA_REPORT_TMP_MAX_AGE_HOURS` 調整（單位：hours）
  - 線上抓到的 PGN 預設保留 48 小時，可用 `CHESSDNA_FETCH_TMP_MAX_AGE_HOURS` 調整（單位：hours）
- 線上抓棋譜受 API / 網路影響（可能遇到 429 / 5xx）
- fetch_max 限制 1~50，避免一次抓太多導致 UI 等太久或伺服器卡住
- time_per_move 會 clamp 到 0.01~1.00 秒（太大會非常慢）
- max_plies 會 clamp 到 10~800（太大會跑很久）

### Notes

- 「線上棋譜預覽」模式下，Analyze 需要先勾選至少 1 盤；避免不小心把全部抓到的對局都丟去分析。

## Phase 2（發想）

- 棋風模仿
  - 輕量偏好特徵：trade / attack / complexity / risk …
  - 走混合模型：top-k 候選 + style consistency

## Dev

- Python 3.11+（目前環境 3.13 也可）
