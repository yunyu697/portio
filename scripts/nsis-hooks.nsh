; Portio NSIS 安装钩子：装完刷新一次 Windows 图标缓存。
; 不刷新的后果：桌面/开始菜单仍显示上一版图标（资源管理器按路径+时间缓存 48px、96px 等多份分片）。
; 这里调用随安装包一起装进 $INSTDIR\scripts\ 的 refresh-icon-cache.ps1，与手工救急走同一条代码路径；
; 它只动当前用户的缓存目录，不碰系统级配置，explorer 会被重启一次（约 1 秒）。
; 用绝对路径调 powershell，避免静默安装时 PATH 里找不到。
!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "刷新 Windows 图标缓存…"
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\scripts\refresh-icon-cache.ps1"'
!macroend
