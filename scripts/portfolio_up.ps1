param(
    [ValidateSet("synthetic_demo", "aggregate")]
    [string]$Scope = "synthetic_demo",
    [string]$Model = "qwen3:8b",
    [switch]$SkipBuild,
    [switch]$SkipSeed,
    [switch]$RunEvaluation
)

$ErrorActionPreference = "Stop"

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Write-Host "PeoplePulse AI — one-command portfolio demo" -ForegroundColor Green
Write-Host "scope=$Scope model=$Model"

Invoke-Step "STEP 10 static preflight" { python scripts/check_step10_portfolio.py }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker CLI not found" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama CLI not found. Install Ollama first." }

try {
    $null = Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 5
} catch {
    throw "Ollama API is not reachable at http://localhost:11434. Start Ollama first."
}

$modelInstalled = ollama list | Select-String -SimpleMatch $Model
if (-not $modelInstalled) {
    Invoke-Step "Pull local LLM $Model" { ollama pull $Model }
}

$env:AGENT_OLLAMA_MODEL = $Model
$env:AGENT_DEFAULT_SCOPE = $Scope
$env:MLOPS_MONITORING_SCOPE = $Scope
if ($Scope -eq "synthetic_demo") {
    $env:APP_ENV = "development"
    $env:ACTIVITY_PRIVACY_MODE = "synthetic_demo"
} else {
    $env:ACTIVITY_PRIVACY_MODE = "aggregate"
}

Invoke-Step "Start PostgreSQL and Redis" { docker compose up -d postgres redis }
Invoke-Step "Apply idempotent schema migrations" { python scripts/apply_all_migrations.py }

if ($Scope -eq "synthetic_demo" -and -not $SkipSeed) {
    Invoke-Step "Seed synthetic portfolio data" { python scripts/seed_step10_demo.py }
}

if ($SkipBuild) {
    Invoke-Step "Start portfolio services" {
        docker compose --profile portfolio up -d api dashboard mlflow prometheus grafana
    }
} else {
    Invoke-Step "Build and start portfolio services" {
        docker compose --profile portfolio up -d --build api dashboard mlflow prometheus grafana
    }
}

Write-Host "`nWaiting for service health..." -ForegroundColor Cyan
$healthUrls = @(
    "http://localhost:8000/health",
    "http://localhost:5000/health",
    "http://localhost:9090/-/healthy",
    "http://localhost:3000"
)
foreach ($url in $healthUrls) {
    $ok = $false
    for ($i = 0; $i -lt 45; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 4
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $ok = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ok) { throw "Service did not become reachable: $url" }
    Write-Host "[OK] $url"
}

Invoke-Step "Verify Analyst Agent sees Ollama" {
    $health = Invoke-RestMethod http://localhost:8000/api/v1/agent/health -TimeoutSec 8
    $health | ConvertTo-Json -Depth 6
    if ($health.status -ne "ok") { throw "Configured Ollama model is not visible to the API" }
}

if ($Scope -eq "synthetic_demo") {
    Invoke-Step "Import experiment history into MLflow" {
        docker compose --profile portfolio run --rm -e MLOPS_MONITORING_SCOPE=$Scope monitoring-worker `
            python scripts/log_step8_history_to_mlflow.py
    }
    Invoke-Step "Generate initial Evidently monitoring snapshot" {
        docker compose --profile portfolio run --rm -e MLOPS_MONITORING_SCOPE=$Scope monitoring-worker `
            python scripts/run_step8_drift.py --scope $Scope
    }
}

Invoke-Step "Start monitoring worker" {
    docker compose --profile portfolio up -d monitoring-worker
}

if ($RunEvaluation) {
    Invoke-Step "Run live STEP 10 Agent evaluation" {
        python scripts/run_step10_evaluation.py --publish
    }
}

Write-Host "`n[OK] PeoplePulse portfolio demo is ready" -ForegroundColor Green
Write-Host "Dashboard:   http://localhost:3000"
Write-Host "API Docs:    http://localhost:8000/docs"
Write-Host "MLflow:      http://localhost:5000"
Write-Host "Prometheus:  http://localhost:9090"
Write-Host "Grafana:     http://localhost:3001"
Write-Host "Ollama:      http://localhost:11434"
Write-Host "Agent:       http://localhost:3000/#analyst"
