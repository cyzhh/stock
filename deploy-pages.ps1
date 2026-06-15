#Requires -Version 5.1
# 三通道发布：gh-pages 分支 + main/docs + main 根目录 index.html
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "index.html")) {
    Write-Error "index.html 不存在，请先运行: python generate_html.py"
}

$sha = (git rev-parse HEAD).Substring(0, 7)
$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$buildTxt = "Deployed at $stamp from main $sha"

# 1) main 根目录 + docs/（适配 Pages 选 main 或 main/docs）
New-Item -ItemType Directory -Path "docs" -Force | Out-Null
Copy-Item "index.html" "docs\index.html" -Force
"" | Set-Content ".nojekyll" -Encoding ascii -NoNewline
"" | Set-Content "docs\.nojekyll" -Encoding ascii -NoNewline
$buildTxt | Set-Content "docs\build.txt" -Encoding utf8

Write-Host ">>> 1/2 提交 main（index.html + docs/）..." -ForegroundColor Cyan
git add index.html .nojekyll docs/
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git diff --staged --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "deploy: Pages $sha"
    git push origin main
}
$ErrorActionPreference = $prevEAP

# 2) gh-pages 孤儿分支
$work = Join-Path $env:TEMP "stock-quant-ghp-$sha"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Path $work | Out-Null
Copy-Item "index.html" (Join-Path $work "index.html") -Force
"" | Set-Content (Join-Path $work ".nojekyll") -Encoding ascii -NoNewline
$buildTxt | Set-Content (Join-Path $work "build.txt") -Encoding utf8

$remote = git remote get-url origin
Write-Host ">>> 2/2 推送到 gh-pages ($sha)..." -ForegroundColor Cyan
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
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
$ErrorActionPreference = $prevEAP
if ($code -ne 0) { exit $code }

Write-Host ""
Write-Host "Done. Configure GitHub Settings -> Pages:" -ForegroundColor Yellow
Write-Host "  gh-pages / (root)  OR  main / docs  OR  GitHub Actions" -ForegroundColor Yellow
Write-Host "https://cyzhh.github.io/stock/" -ForegroundColor Green
Write-Host "Verify build.txt: https://cyzhh.github.io/stock/build.txt" -ForegroundColor Green
Write-Host "Expected stamp: $stamp" -ForegroundColor Green
