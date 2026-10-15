# Сборка PassPuck: src/passpuck.py -> device/passpuck.mpy
#
# Запуск (PowerShell, из папки репозитория):
#     powershell -ExecutionPolicy Bypass -File tools\build.ps1
#
# Скрипт сам скачивает официальную утилиту Adafruit mpy-cross той же версии,
# что и прошивка в firmware/ (CircuitPython 10.2.1), и проверяет её контрольную сумму.
# .mpy-файлы, собранные для 10.x, не работают на CircuitPython 11 и новее.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$version = "10.2.1"
$sha256 = "CC8FF59E6A7DE7FE9156892667AF76AC3DB050E5783B6CFA733537A5A5425B1E"
$cache = Join-Path $PSScriptRoot ".cache"
$exe = Join-Path $cache "mpy-cross-$version.exe"

if (-not (Test-Path $exe)) {
    New-Item -ItemType Directory -Force $cache | Out-Null
    $url = "https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/windows/mpy-cross-windows-$version.static.exe"
    Write-Host "Скачиваю mpy-cross $version ..."
    Invoke-WebRequest -Uri $url -OutFile $exe
}
if ((Get-FileHash $exe -Algorithm SHA256).Hash -ne $sha256) {
    Remove-Item $exe
    throw "Контрольная сумма mpy-cross не совпала — файл удалён, сборка остановлена."
}

$src = Join-Path $root "src\passpuck.py"
$out = Join-Path $root "device\passpuck.mpy"
& $exe $src -o $out
if ($LASTEXITCODE -ne 0) { throw "mpy-cross завершился с ошибкой $LASTEXITCODE" }
Write-Host ("Готово: device\passpuck.mpy ({0} байт)" -f (Get-Item $out).Length)
