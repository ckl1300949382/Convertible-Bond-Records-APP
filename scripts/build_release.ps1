# 绿色版构建脚本（阶段 5 / 文档 §11）：PyInstaller onedir + windowed。
# 产物与中间文件在 dist/、build/（已列入 .gitignore，不入 Git，见架构决策 6）。
# 用法：项目根目录执行  powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
# 注意：本文件必须保存为 UTF-8 with BOM（PowerShell 5 按 ANSI 读无 BOM 文件，中文会乱码）。
# 注意：构建冒烟会启动打包后的程序；请先关闭正在运行的应用实例（单实例限制）。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "未找到虚拟环境 $py；请先执行 .venv\Scripts\pip install -e .[build]"
    exit 1
}

& $py -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name "可转债收益记录" `
    --paths src `
    scripts\run_app.py
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller 构建失败"; exit 1 }

$appDir = Join-Path $root "dist\可转债收益记录"
$exe = Join-Path $appDir "可转债收益记录.exe"
if (-not (Test-Path $exe)) { Write-Error "未找到生成的 exe：$exe"; exit 1 }

# ---- 发布包附加内容（§11.1：版本说明 + 简短使用说明） ----
Copy-Item (Join-Path $root "docs\版本说明.txt") $appDir -Force
Copy-Item (Join-Path $root "docs\使用说明.txt") $appDir -Force

# ---- 构建冒烟（PKG-01 的本机部分）：启动 exe → 存活检查 → 正常关闭 ----
$proc = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 6
if ($proc.HasExited) {
    $msg = "冒烟失败：进程在 6 秒内退出（退出码 {0}）。若正在运行本应用的其他实例，会因单实例限制立即退出——请关闭后重试。" -f $proc.ExitCode
    Write-Error $msg
    exit 1
}
Write-Host "冒烟通过：进程存活，发送关闭请求…"
$null = $proc.CloseMainWindow()
if (-not $proc.WaitForExit(8000)) {
    Stop-Process -Id $proc.Id -Force
    Write-Warning "进程未响应关闭请求，已强制结束（不影响冒烟结论）"
}

# ---- 压缩发布包 ----
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
$zip = Join-Path $root ("dist\可转债收益记录_v{0}_win64.zip" -f $version)
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $appDir -DestinationPath $zip
Write-Host "构建完成：$zip"
