# 打包单文件 EXE（内置 WebView2 窗口 + 离线镜像）
$ErrorActionPreference = "Stop"
cd $PSScriptRoot

python -m PyInstaller --noconfirm --clean `
  --onefile --windowed `
  --name "Helldivers2WikiCN" `
  --add-data "output_zh/site;site" `
  --hidden-import "webview.platforms.edgechromium" `
  --hidden-import "webview.platforms.winforms" `
  --collect-all clr_loader `
  --collect-all pythonnet `
  app.py

Write-Host "打包完成: dist/Helldivers2WikiCN.exe"
