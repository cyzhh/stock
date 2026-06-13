#Requires -Version 5.1
# 将 index.html 直接推送到 gh-pages 分支
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "index.html")) {
    Write-Error "index.html 不存在，请先运行 python generate_html.py"
}

$sha = (git rev-parse HEAD).Substring(0, 7)
$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$work = Join-Path $env:TEMP "stock-quant-ghp-$sha"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Path $work | Out-Null

Copy-Item "index.html" (Join-Path $work "index.html")
New-Item -ItemType File -Path (Join-Path $work ".nojekyll") -Force | Out-Null
"Deployed at $stamp from main $sha" | Set-Content (Join-Path $work "build.txt") -Encoding utf8

$remote = git remote get-url origin
Write-Host ">>> 推送到 gh-pages ($sha)..." -ForegroundColor Cyan
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
Push-Location $work
git init -q
git checkout -b gh-pages 2>&1 | Out-Null
git add -A
git commit -q -m "deploy: $sha"
git remote add origin $remote 2>&1 | Out-Null
git push -f origin gh-pages
$code = $LASTEXITCODE
Pop-Location
$ErrorActionPreference = $prevEAP
if ($code -ne 0) { exit $code }
Remove-Item -Recurse -Force $work
Write-Host "Pages 已更新: https://cyzhh.github.io/stock/" -ForegroundColor Green
