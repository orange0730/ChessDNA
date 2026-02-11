# ChessDNA

棋譜精準度分析（CPL/accuracy/blunder 分類）＋棋風建模（可解釋特徵）＋棋風模仿（偏好/走子模型）。

## MVP (Phase 1)
- 輸入：PGN（單盤/多盤）或從 Lichess API 抓取指定帳號最近 N 盤
- 輸出：
  - 每盤報告：每步 CPL、accuracy%、錯誤分類、turning points
  - 玩家總覽：風格特徵向量 + 自然語言摘要

## Phase 2
- 棋風模仿：
  - 輕量版：開局與偏好加權（trade/attack/complexity）
  - 進階版：走子預測模型（top-k 命中率 + style consistency）

## Dev
Python 3.11+ (目前環境 3.13 ok)

