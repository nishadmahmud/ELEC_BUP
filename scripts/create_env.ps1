# Creates .env from example and opens it for you to paste OPENAI_API_KEY.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\create_env.ps1

$root = Split-Path -Parent $PSScriptRoot
$example = Join-Path $root ".env.example"
$target = Join-Path $root ".env"

if (-not (Test-Path $target)) {
    Copy-Item $example $target
    Write-Host "Created $target"
} else {
    Write-Host ".env already exists at $target"
}

Write-Host ""
Write-Host "Paste your OpenAI API key into OPENAI_API_KEY=..."
Write-Host "Then save and close the editor."
Write-Host ""
notepad $target
