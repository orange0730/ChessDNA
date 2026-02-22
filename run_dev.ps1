$ErrorActionPreference = 'Stop'
if([string]::IsNullOrWhiteSpace($env:STOCKFISH_PATH)){
  $env:STOCKFISH_PATH = 'D:\code\chess_train\stockfish\stockfish-windows-x86-64-avx2.exe'
}

Write-Host "[ChessDNA] STOCKFISH_PATH=$env:STOCKFISH_PATH"
function Test-PortFree([int]$port){
  try{
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return -not $c
  } catch {
    # fallback if cmdlet not available
    return $true
  }
}

$port = 8004
while($port -lt 8015 -and -not (Test-PortFree $port)) { $port++ }

Write-Host "[ChessDNA] http://127.0.0.1:$port"

uvicorn chessdna.app:app --reload --host 127.0.0.1 --port $port
