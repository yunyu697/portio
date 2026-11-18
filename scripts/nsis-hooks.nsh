; Portio NSIS 安装钩子：装完刷新一次 Windows 图标缓存。
; 不刷新的后果：桌面/开始菜单仍显示上一版图标（资源管理器按路径+时间缓存 48px、96px 等多份分片）。
; 这里只动当前用户的缓存目录，不碰系统级配置；explorer 会被重启一次（约 1 秒）。
!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "刷新 Windows 图标缓存…"
  nsExec::ExecToLog 'cmd /c taskkill /f /im explorer.exe'
  Sleep 700
  Delete "$LOCALAPPDATA\Microsoft\Windows\Explorer\iconcache_*.db"
  Delete "$LOCALAPPDATA\IconCache.db"
  nsExec::ExecToLog 'cmd /c start "" explorer.exe'
  nsExec::ExecToLog 'cmd /c ie4uinit.exe -show'
!macroend
