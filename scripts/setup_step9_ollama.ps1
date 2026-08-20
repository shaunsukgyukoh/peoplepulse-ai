$ErrorActionPreference = "Stop"

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$model = if ($env:AGENT_OLLAMA_MODEL) { $env:AGENT_OLLAMA_MODEL } else { "qwen3:8b" }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama command not found. Install Ollama for Windows first, then reopen PowerShell."
}

Invoke-Step "Show Ollama version" { ollama --version }
Invoke-Step "Pull local analyst model: $model" { ollama pull $model }
Invoke-Step "List Ollama models" { ollama list }

try {
    $health = Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 5
    Write-Host "`n[OK] Ollama API is reachable at http://localhost:11434" -ForegroundColor Green
    Write-Host "Configured model: $model"
} catch {
    throw "Ollama API is not reachable at http://localhost:11434. Start Ollama and retry. $($_.Exception.Message)"
}
