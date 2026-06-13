#Requires -Version 5.1
param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

Write-Host ">>> 1/2 build..." -ForegroundColor Cyan
python build_all.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">>> 2/2 git push..." -ForegroundColor Cyan
git remote set-url origin ssh://git@github.com/cyzhh/stock.git
git add -A
$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "No changes to push." -ForegroundColor Yellow
    exit 0
}

if (-not $Message) {
    $Message = "Update dashboard $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git commit -m $Message
git push origin main

Write-Host "Done. Pages: https://cyzhh.github.io/stock/" -ForegroundColor Green
