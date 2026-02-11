# ChessDNA

棋譜精準度分析（CPL/accuracy/blunder 分類）＋棋風建模（可解釋特徵）＋棋風模仿（偏好/走子模型）。

## MVP (Phase 1)
- 輸入：PGN（單盤/多盤）或從 Lichess API 抓取指定帳號最近 N 盤
- 輸出：
  - 每盤報告：每步 CPL、accuracy%、錯誤分類（turning points 施工中）
  - 玩家總覽：風格特徵向量 + 自然語言摘要（施工中）

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

# analyze PGN with Stockfish
chessdna analyze --pgn games.pgn --engine D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe --t 0.05 --max-plies 200 --out report.json
```

## Phase 2
- 棋風模仿：
  - 輕量版：開局與偏好加權（trade/attack/complexity）
  - 進階版：走子預測模型（top-k 命中率 + style consistency）

## Dev
Python 3.11+ (目前環境 3.13 ok)

