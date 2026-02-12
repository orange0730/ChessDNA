# ChessDNA

用棋譜做棋力評估（CPL / accuracy / blunder rate 等）、棋風特徵建模，並朝「棋風模仿」前進。

## MVP (Phase 1)
- 輸入：
  - PGN（單盤 / 多盤）
  - 或線上抓棋譜：Lichess / Chess.com（輸入帳號）
- 輸出：
  - 每盤：平均 CPL、accuracy%、錯誤分類、turning points（逐步完善中）
  - 玩家總覽：風格特徵（規劃中）

## Run (local)
### Web
```powershell
cd D:\code\ChessDNA
pip install -e .
.\run_dev.ps1
# open http://127.0.0.1:8004
```

### CLI
```powershell
# fetch PGN from lichess
chessdna fetch --user orange_bot --max 10 --out games.pgn

# quick validate/summarize PGN (no engine required)
chessdna pgninfo --pgn games.pgn --max-games 200

# minimal self-test (pgninfo + best-effort analyze)
# - if Stockfish path is missing, it will auto-skip analyze
chessdna selftest --pgn _sample_orange_bot.pgn

# analyze PGN with Stockfish
chessdna analyze --pgn games.pgn --engine D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe --t 0.05 --max-plies 200 --out report.json
```

## Web UX：線上抓棋譜（MVP）
流程：
1) 平台選擇：Lichess 或 Chess.com
2) 輸入 username、fetch_max
3) 列出最近對局清單
4) 勾選要分析的對局（可多選）
5) 點 Analyze 進行分析

## Limitations (MVP)
- Web UI 的「預覽 token / report_id」主要是記憶體 mapping（in-memory）。
  - 伺服器重啟後 mapping 會清空。
  - 但會 best-effort 把抓到的 PGN / 產出的報告寫到系統 temp，讓下載或預覽 token 有機會在重啟後仍可用（不保證）。
- 線上抓棋譜受 API 限流 / 網路影響。
- fetch_max 會被限制在 1~50，避免一次抓太多導致 UI 等太久或伺服器卡住。

## Phase 2 (方向)
- 棋風模仿：
  - 輕量的偏好向量（例如 trade / attack / complexity / risk）
  - 走法選擇模型（top-k 命中率 + style consistency）

## Dev
- Python 3.11+（目前環境 3.13 也可）
