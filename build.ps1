# 本地一键构建看板（不推送 Git）
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
python build_all.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n打开看板: $PSScriptRoot\index.html" -ForegroundColor Green
}
