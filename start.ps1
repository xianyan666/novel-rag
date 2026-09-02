param(
  [string]$Project = "mystic_recovery",
  [switch]$SkipInstall,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$RuntimePath = Join-Path $Root "config\runtime.json"
$RuntimeDir = Join-Path $Root ".runtime"
$LogDir = Join-Path $Root "logs"
$PidPath = Join-Path $RuntimeDir "pids.json"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"
if (-not $env:OLLAMA_MODELS) {
  $userOllamaModels = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
  if ($userOllamaModels) {
    $env:OLLAMA_MODELS = $userOllamaModels
  }
}

function Import-DotEnv {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    return
  }
  Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      return
    }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if ($key -and -not [Environment]::GetEnvironmentVariable($key, "Process")) {
      [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
  }
}

function Get-Setting {
  param(
    [object]$Runtime,
    [string]$Property,
    [string]$EnvName,
    [string]$Default = ""
  )
  $envValue = [Environment]::GetEnvironmentVariable($EnvName, "Process")
  if ($envValue) {
    return [string]$envValue
  }
  if ($Runtime.PSObject.Properties.Name -contains $Property) {
    return [string]$Runtime.$Property
  }
  return $Default
}

function Write-Step {
  param([string]$Message)
  Write-Host "[RAG] $Message" -ForegroundColor Cyan
}

function Test-Http {
  param(
    [string]$Url,
    [int]$TimeoutSec = 2
  )
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Wait-Http {
  param(
    [string]$Url,
    [string]$Name,
    [int]$Seconds = 60
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Http -Url $Url -TimeoutSec 3) {
      Write-Step "$Name ready: $Url"
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "$Name was not ready within $Seconds seconds: $Url"
}

function Get-ProcessOnPort {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) {
    return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
  }
  return $null
}

function Get-ProcessCommandLine {
  param([int]$ProcessId)
  try {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
    return [string]$proc.CommandLine
  } catch {
    return ""
  }
}

function Test-BackendEntityApi {
  try {
    $openapi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 5
    $paths = $openapi.paths.PSObject.Properties.Name
    return ($paths -contains "/api/projects/{project_id}/entities" -and $paths -contains "/api/projects/{project_id}/history")
  } catch {
    return $false
  }
}

function Stop-StaleBackendIfSafe {
  param([System.Diagnostics.Process]$Process)
  if (-not $Process) {
    return $false
  }
  $cmd = Get-ProcessCommandLine -ProcessId $Process.Id
  if ($cmd -match "uvicorn" -and $cmd -match "app\.main:app" -and -not (Test-BackendEntityApi)) {
    Write-Step "Port 8000 has stale backend without the latest API (entities/history). Restarting PID $($Process.Id)."
    Stop-Process -Id $Process.Id -Force
    Start-Sleep -Seconds 2
    return $true
  }
  return $false
}

function Find-FreePort {
  param(
    [int]$StartPort = 5173,
    [int]$EndPort = 5199
  )
  for ($port = $StartPort; $port -le $EndPort; $port++) {
    if (-not (Get-ProcessOnPort -Port $port)) {
      return $port
    }
  }
  throw "No free frontend port found in range $StartPort-$EndPort"
}

function Test-OllamaModel {
  param([string]$Model)
  try {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
    foreach ($m in $tags.models) {
      if ($m.name -eq $Model -or $m.name.StartsWith($Model + ":")) {
        return $true
      }
    }
    return $false
  } catch {
    return $false
  }
}

function Start-HiddenProcess {
  param(
    [string]$Name,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$OutFile,
    [string]$ErrFile
  )
  Write-Step "Starting $Name"
  return Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput $OutFile `
    -RedirectStandardError $ErrFile `
    -WindowStyle Hidden `
    -PassThru
}

if (-not (Test-Path -LiteralPath $RuntimePath)) {
  throw "Missing runtime config: $RuntimePath"
}

Import-DotEnv -Path (Join-Path $Root ".env")
$apiProxy = [Environment]::GetEnvironmentVariable("RAG_API_PROXY", "Process")
if ($apiProxy) {
  $env:HTTP_PROXY = $apiProxy
  $env:HTTPS_PROXY = $apiProxy
}
$runtime = Get-Content -LiteralPath $RuntimePath -Encoding UTF8 | ConvertFrom-Json

Write-Step "Project root: $Root"
Write-Step "Project id: $Project"

$embeddingProvider = (Get-Setting -Runtime $runtime -Property "embedding_provider" -EnvName "RAG_EMBEDDING_PROVIDER" -Default "ollama").ToLower()
$llmProvider = (Get-Setting -Runtime $runtime -Property "llm_provider" -EnvName "RAG_LLM_PROVIDER" -Default "ollama").ToLower()
$embeddingModel = Get-Setting -Runtime $runtime -Property "embedding_model" -EnvName "RAG_EMBEDDING_MODEL"
$llmModel = Get-Setting -Runtime $runtime -Property "llm_model" -EnvName "RAG_LLM_MODEL"
if ([Environment]::GetEnvironmentVariable("MIMO_MODEL", "Process")) {
  $llmModel = [Environment]::GetEnvironmentVariable("MIMO_MODEL", "Process")
}
Write-Step "Model providers: embedding=$embeddingProvider($embeddingModel), llm=$llmProvider($llmModel)"

$pids = [ordered]@{}

$needsOllama = ($embeddingProvider -eq "ollama" -or $llmProvider -eq "ollama")
if ($needsOllama) {
  $ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
  if (-not $ollama) {
    throw "ollama command not found. Install Ollama and ensure it is in PATH."
  }

  if (-not (Test-Http -Url "http://127.0.0.1:11434/api/tags" -TimeoutSec 3)) {
    $ollamaProcess = Start-HiddenProcess `
      -Name "Ollama" `
      -FilePath $ollama.Source `
      -ArgumentList @("serve") `
      -WorkingDirectory $Root `
      -OutFile (Join-Path $LogDir "ollama.out.log") `
      -ErrFile (Join-Path $LogDir "ollama.err.log")
    $pids.ollama = $ollamaProcess.Id
  }

  Wait-Http -Url "http://127.0.0.1:11434/api/tags" -Name "Ollama" -Seconds 60

  if ($embeddingProvider -eq "ollama" -and -not (Test-OllamaModel -Model $embeddingModel)) {
    throw "Embedding model not found in Ollama: $embeddingModel. Run: ollama pull $embeddingModel"
  }
  if ($llmProvider -eq "ollama" -and -not (Test-OllamaModel -Model $llmModel)) {
    throw "LLM model not found in Ollama: $llmModel. Run: ollama pull $llmModel"
  }
}

if ($llmProvider -in @("mimo", "openai_compatible", "openai")) {
  $llmBaseUrl = [Environment]::GetEnvironmentVariable("RAG_LLM_API_BASE_URL", "Process")
  if (-not $llmBaseUrl) {
    $llmBaseUrl = [Environment]::GetEnvironmentVariable("MIMO_API_BASE_URL", "Process")
  }
  if (-not $llmBaseUrl -and ($runtime.PSObject.Properties.Name -contains "llm_api_base_url")) {
    $llmBaseUrl = [string]$runtime.llm_api_base_url
  }
  if (-not $llmBaseUrl) {
    throw "LLM API base URL is missing. Set RAG_LLM_API_BASE_URL or MIMO_API_BASE_URL in .env."
  }
}
Write-Step "Models ready: $embeddingModel / $llmModel"

if (-not $SkipInstall) {
  Write-Step "Installing backend dependencies"
  Push-Location $BackendDir
  try {
    python -m pip install -r requirements.txt
  } finally {
    Pop-Location
  }

  if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
    Write-Step "Installing frontend dependencies"
    Push-Location $FrontendDir
    try {
      npm install
    } finally {
      Pop-Location
    }
  } else {
    Write-Step "frontend/node_modules exists, skip npm install"
  }
}

$backendOnPort = Get-ProcessOnPort -Port 8000
if ($backendOnPort) {
  $restarted = Stop-StaleBackendIfSafe -Process $backendOnPort
  if ($restarted) {
    $backendOnPort = Get-ProcessOnPort -Port 8000
  }
}
if ($backendOnPort -and (Test-BackendEntityApi)) {
  Write-Step "Backend already ready on port 8000 with entity API: PID $($backendOnPort.Id)"
} else {
  if ($backendOnPort) {
    throw "Port 8000 is occupied by PID $($backendOnPort.Id), but it is not the expected backend with entity API."
  }
  $backendProcess = Start-HiddenProcess `
    -Name "FastAPI backend" `
    -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $BackendDir `
    -OutFile (Join-Path $LogDir "backend.out.log") `
    -ErrFile (Join-Path $LogDir "backend.err.log")
  $pids.backend = $backendProcess.Id
}
Wait-Http -Url "http://127.0.0.1:8000/api/projects" -Name "Backend API" -Seconds 60
if (-not (Test-BackendEntityApi)) {
  throw "Backend started but entity API is not available. Check logs/backend.err.log."
}

$frontendPort = 5173
$frontendUrl = "http://127.0.0.1:$frontendPort"
$frontendOnPort = Get-ProcessOnPort -Port $frontendPort
if ($frontendOnPort -and (Test-Http -Url $frontendUrl -TimeoutSec 5)) {
  Write-Step "Frontend already ready on port ${frontendPort}: PID $($frontendOnPort.Id)"
} else {
  if ($frontendOnPort) {
    Write-Step "Port $frontendPort is occupied but not responding. Selecting another port."
    $frontendPort = Find-FreePort -StartPort 5174 -EndPort 5199
    $frontendUrl = "http://127.0.0.1:$frontendPort"
  }
  $npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
  if (-not $npm) {
    $npm = Get-Command "npm" -ErrorAction Stop
  }
  $frontendProcess = Start-HiddenProcess `
    -Name "Vue frontend" `
    -FilePath $npm.Source `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort", "--strictPort") `
    -WorkingDirectory $FrontendDir `
    -OutFile (Join-Path $LogDir "frontend.out.log") `
    -ErrFile (Join-Path $LogDir "frontend.err.log")
  $pids.frontend = $frontendProcess.Id
}
Wait-Http -Url $frontendUrl -Name "Vue frontend" -Seconds 60

$pids | ConvertTo-Json | Set-Content -LiteralPath $PidPath -Encoding UTF8

Write-Step "All services are ready"
Write-Host ""
Write-Host "Frontend: $frontendUrl" -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8000/api/projects" -ForegroundColor Green
if ($needsOllama) {
  Write-Host "Ollama:   http://127.0.0.1:11434/api/tags" -ForegroundColor Green
} else {
  Write-Host "LLM API:  $llmProvider" -ForegroundColor Green
}
Write-Host "Logs:     $LogDir"
Write-Host "Stop:     powershell -ExecutionPolicy Bypass -File .\stop.ps1"
Write-Host ""

if (-not $NoBrowser) {
  Start-Process $frontendUrl
}
