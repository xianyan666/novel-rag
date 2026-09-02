$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidPath = Join-Path $Root ".runtime\pids.json"

function Stop-TrackedProcess {
  param(
    [string]$Name,
    [object]$PidValue
  )
  if (-not $PidValue) {
    return
  }
  try {
    $proc = Get-Process -Id ([int]$PidValue) -ErrorAction Stop
    Write-Host "[RAG] Stopping $Name, PID $($proc.Id)" -ForegroundColor Cyan
    Stop-Process -Id $proc.Id -Force
  } catch {
    Write-Host "[RAG] $Name is not running or already exited" -ForegroundColor DarkGray
  }
}

if (-not (Test-Path -LiteralPath $PidPath)) {
  Write-Host "[RAG] No startup pid record found: $PidPath" -ForegroundColor Yellow
  Write-Host "[RAG] If services are still running, close processes on ports 8000, 5173/5174, and 11434 manually."
  exit 0
}

$pids = Get-Content -LiteralPath $PidPath -Encoding UTF8 | ConvertFrom-Json

Stop-TrackedProcess -Name "Vue frontend" -PidValue $pids.frontend
Stop-TrackedProcess -Name "FastAPI backend" -PidValue $pids.backend
Stop-TrackedProcess -Name "Ollama" -PidValue $pids.ollama

Remove-Item -LiteralPath $PidPath -Force
Write-Host "[RAG] Done." -ForegroundColor Green
