param(
    [ValidateSet("aggregate", "synthetic_demo")]
    [string]$Scope = "aggregate"
)

$ErrorActionPreference = "Stop"
function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Invoke-Step "STEP 9 static preflight" { python scripts/check_step9_agent.py }

try {
    $null = Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 5
} catch {
    throw "Host Ollama is not reachable. Run .\scripts\setup_step9_ollama.ps1 first."
}

$env:AGENT_DEFAULT_SCOPE = $Scope
Invoke-Step "Build and start API + dashboard agent profile" {
    docker compose --profile agent up -d --build --force-recreate api dashboard
}

Write-Host "`nWaiting for PeoplePulse API..." -ForegroundColor Cyan
for ($i = 0; $i -lt 30; $i++) {
    try {
        $health = Invoke-RestMethod http://localhost:8000/api/v1/agent/health -TimeoutSec 3
        if ($health.status -eq "ok") { break }
    } catch {}
    Start-Sleep -Seconds 2
}

$health = Invoke-RestMethod http://localhost:8000/api/v1/agent/health -TimeoutSec 5
$health | ConvertTo-Json -Depth 5
if ($health.status -ne "ok") {
    throw "PeoplePulse API cannot see configured Ollama model. Check AGENT_OLLAMA_MODEL and Docker host connectivity."
}

Write-Host "`n[OK] STEP 9 Analyst Agent is ready" -ForegroundColor Green
Write-Host "Dashboard: http://localhost:3000/#analyst"
Write-Host "Agent API: http://localhost:8000/api/v1/agent/health"
