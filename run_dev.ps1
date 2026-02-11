$ErrorActionPreference = 'Stop'
$env:STOCKFISH_PATH = $env:STOCKFISH_PATH
if([string]::IsNullOrWhiteSpace($env:STOCKFISH_PATH)){
  $env:STOCKFISH_PATH = 'D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe'
}

Write-Host "[ChessDNA] STOCKFISH_PATH=$env:STOCKFISH_PATH"
Write-Host "[ChessDNA] http://127.0.0.1:8000"

uvicorn chessdna.app:app --reload --host 127.0.0.1 --port 8000
