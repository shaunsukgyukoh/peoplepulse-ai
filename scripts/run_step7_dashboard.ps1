$ErrorActionPreference = "Stop"

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "`n==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Write-Host "PeoplePulse STEP 7 dashboard"

Invoke-NativeStep -Name "Build and start PostgreSQL, API, and Next.js dashboard" -Command {
    docker compose --profile dashboard up -d --build --force-recreate postgres api dashboard
}

Invoke-NativeStep -Name "Show dashboard services" -Command {
    docker compose --profile dashboard ps
}

Write-Host "`n[OK] Dashboard: http://localhost:3000"
Write-Host "[OK] API health: http://localhost:8000/health"
Write-Host "[INFO] For live Slack signals, keep the local CUDA NLP worker running and start the Slack listener profile."
