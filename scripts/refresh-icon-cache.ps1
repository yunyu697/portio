<#  刷新 Explorer 图标缓存（Portio 装完新图标不生效时用）
    做法：停掉 explorer → 删掉 iconcache_*.db（48/96/256px 的缓存分片）→ 重启 explorer → 通知 shell 重新读图标。
    只动当前用户的缓存目录，不碰系统其它配置。 #>
$ErrorActionPreference = 'Stop'
$cacheDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Explorer'
$oldCache = Join-Path $env:LOCALAPPDATA 'IconCache.db'

Write-Host "停止 explorer…"
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 900

Write-Host "删除图标缓存分片…"
Get-ChildItem -LiteralPath $cacheDir -Filter 'iconcache_*.db' -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
        try { Remove-Item -LiteralPath $_.FullName -Force; Write-Host "  已删 $($_.Name)" }
        catch { Write-Host "  跳过 $($_.Name)（占用中）" }
    }
if (Test-Path -LiteralPath $oldCache) {
    try { Remove-Item -LiteralPath $oldCache -Force; Write-Host "  已删 IconCache.db" } catch {}
}

Write-Host "重启 explorer…"
Start-Process explorer.exe
Start-Sleep -Milliseconds 400

# ie4uinit -show 让 shell 重新广播图标变更，配合上面的缓存清除才算完整
$ie4 = Join-Path $env:SystemRoot 'System32\ie4uinit.exe'
if (Test-Path -LiteralPath $ie4) { & $ie4 -show }
Write-Host "图标缓存已重建。"
