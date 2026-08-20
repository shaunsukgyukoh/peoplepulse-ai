$ErrorActionPreference = "Stop"
docker compose --profile portfolio down
if ($LASTEXITCODE -ne 0) { throw "Portfolio shutdown failed with exit code $LASTEXITCODE" }
Write-Host "[OK] PeoplePulse portfolio containers stopped. Persistent volumes were kept." -ForegroundColor Green
