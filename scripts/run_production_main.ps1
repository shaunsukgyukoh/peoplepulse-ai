$ErrorActionPreference = "Stop"

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Start PostgreSQL and Redis" {
    docker compose up -d postgres redis
}

Invoke-Step "Apply production employee directory migration" {
    python scripts/apply_production_main_migration.py
}

Invoke-Step "Build and start API + HR dashboard" {
    docker compose --profile dashboard up -d --build --force-recreate api dashboard
}

Write-Host "`n[OK] PeoplePulse production main is ready." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:3000"
Write-Host "API docs : http://localhost:8000/docs"
Write-Host ""
Write-Host "Before first use, load a real employee directory locally:" -ForegroundColor Yellow
Write-Host "  Copy data/templates/employee_directory.csv.example to data/employee_directory.csv"
Write-Host "  Fill it with your authorized employee directory data"
Write-Host "  python scripts/load_employee_directory.py data/employee_directory.csv"
Write-Host ""
Write-Host "Do not commit the real employee directory CSV. .gitignore blocks it by default."
