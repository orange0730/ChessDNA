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

## Limitations (MVP)
- Web UI 的下載連結目前是「暫存檔 + 記憶體 mapping」：伺服器重啟後，report_id 的 in-memory mapping 會消失；但若暫存檔仍在，下載端點會嘗試從 temp 目錄找回（仍可能被系統清理）。
- 線上抓棋譜（Lichess/Chess.com）已支援「平台選擇→列對局→勾選→分析」的 MVP UX；目前預覽資料主要是 in-memory 暫存，但會 best-effort 把抓到的原始 PGN 落到 temp（因此伺服器重啟後 *有時* 仍可用同一個 preview_token 續跑；仍可能被系統清理）。同時也受 API 限流/網路狀態影響。
- fetch_max 目前會被限制在 1~50，避免一次抓太多導致等待過久。

## Phase 2
- 棋風模仿：
  - 輕量版：開局與偏好加權（trade/attack/complexity）
  - 進階版：走子預測模型（top-k 命中率 + style consistency）

## Dev
Python 3.11+ (目前環境 3.13 ok)

