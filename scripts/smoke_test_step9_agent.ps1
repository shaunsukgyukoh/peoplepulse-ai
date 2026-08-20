$ErrorActionPreference = "Stop"

$thread = "smoke-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"

$payload = @{
    message = "현재 PeoplePulse 상태와 최근 Slack 파생 신호를 요약해줘. 데이터가 없으면 없다고 말해줘."
    scope = "aggregate"
    thread_id = $thread
}

# Windows PowerShell 5.1 may not send non-ASCII JSON as UTF-8 unless the
# charset/body encoding is explicit. FastAPI expects application/json as UTF-8.
$json = $payload | ConvertTo-Json -Depth 10 -Compress
$body = [System.Text.Encoding]::UTF8.GetBytes($json)

Write-Host "STEP 9 agent smoke test" -ForegroundColor Cyan
Write-Host "thread_id=$thread"
Write-Host "request_encoding=utf-8"

try {
    $response = Invoke-RestMethod `
        -Method POST `
        -Uri "http://localhost:8000/api/v1/agent/chat" `
        -ContentType "application/json; charset=utf-8" `
        -Headers @{ Accept = "application/json" } `
        -Body $body `
        -TimeoutSec 120
}
catch {
    Write-Host "`n[ERROR] STEP 9 agent request failed." -ForegroundColor Red

    if ($_.Exception.Response) {
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
                $errorBody = $reader.ReadToEnd()
                if ($errorBody) {
                    Write-Host "Response body: $errorBody" -ForegroundColor Yellow
                }
            }
        }
        catch {
            # Preserve the original exception below if the response body cannot be read.
        }
    }

    throw
}

$response | ConvertTo-Json -Depth 10

if (-not $response.answer) {
    throw "Agent returned an empty answer"
}

Write-Host "`n[OK] STEP 9 agent smoke test" -ForegroundColor Green
