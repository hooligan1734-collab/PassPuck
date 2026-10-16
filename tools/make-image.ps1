# =====================================================================
#  Сборка полного образа PassPuck для установки одним файлом.
#
#  Образ = прошивка CircuitPython + готовый диск CIRCUITPY со всеми файлами.
#  Пользователь зажимает BOOT, подключает плату и перетаскивает один .uf2.
#
#  Как собрать:
#   1. Плата с ЧИСТЫМИ файлами PassPuck (пустой passwords.py!) в режиме
#      редактирования — диск CIRCUITPY виден, например D:.
#   2. powershell -ExecutionPolicy Bypass -File tools\make-image.ps1 -Drive D: -Out PassPuck-2.2.uf2
#
#  Другие режимы:
#   -SaveRaw файл.img    только сохранить диск платы побайтно (резервная копия)
#   -FromRaw файл.img    взять диск из сохранённого файла вместо платы
#   -NoFirmware          в .uf2 только диск, без прошивки (восстановление копии)
#
#  Где что лежит во флеш-памяти RP2040-Zero (2 МБ) у CircuitPython 10:
#   0x10000000 — прошивка; 0x100FF000 — память настроек (NVM, в образ не входит);
#   0x10100000 — диск CIRCUITPY, 1 МБ.
# =====================================================================
param(
    [string]$Drive,
    [string]$FromRaw,
    [string]$SaveRaw,
    [string]$Out,
    [string]$Firmware = (Join-Path $PSScriptRoot "..\firmware\adafruit-circuitpython-waveshare_rp2040_zero-ru-10.2.1.uf2"),
    [switch]$NoFirmware
)
$ErrorActionPreference = "Stop"
$FS_ADDR = [uint32]"0x10100000"
$FS_SIZE = 1048576
$FAMILY_RP2040 = [uint32]"0xE48BFF56"

Add-Type -TypeDefinition @'
using System; using System.IO; using System.Runtime.InteropServices; using Microsoft.Win32.SafeHandles;
public static class PassPuckRawVolume {
  [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  static extern SafeFileHandle CreateFile(string n, uint a, uint s, IntPtr sa, uint c, uint f, IntPtr t);
  public static byte[] Read(string path, int count) {
    var h = CreateFile(path, 0x80000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
    if (h.IsInvalid) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
    using (var fs = new FileStream(h, FileAccess.Read)) {
      var b = new byte[count]; int n = 0;
      while (n < count) { int r = fs.Read(b, n, Math.Min(65536, count - n)); if (r <= 0) break; n += r; }
      Array.Resize(ref b, n); return b;
    }
  }
}
'@

function Read-Drive($drive) {
    $letter = $drive.TrimEnd(":", "\")
    $a = [PassPuckRawVolume]::Read("\\.\${letter}:", $FS_SIZE)
    $b = [PassPuckRawVolume]::Read("\\.\${letter}:", $FS_SIZE)
    if ($a.Length -ne $FS_SIZE) { throw "Диск ${letter}: прочитан не целиком ($($a.Length) байт)" }
    if (-not [Linq.Enumerable]::SequenceEqual($a, $b)) { throw "Два чтения диска не совпали — повторите, ничего не записывая на диск" }
    if ($a[510] -ne 0x55 -or $a[511] -ne 0xAA) { throw "На диске ${letter}: нет файловой системы FAT" }
    return ,$a              # запятая: иначе PowerShell превратит массив байтов в массив объектов
}

function New-Uf2Block($addr, $payload, $blockNo, $numBlocks) {
    $blk = New-Object byte[] 512
    [BitConverter]::GetBytes([uint32]"0x0A324655").CopyTo($blk, 0)
    [BitConverter]::GetBytes([uint32]"0x9E5D5157").CopyTo($blk, 4)
    [BitConverter]::GetBytes([uint32]"0x00002000").CopyTo($blk, 8)      # есть номер семейства
    [BitConverter]::GetBytes([uint32]$addr).CopyTo($blk, 12)
    [BitConverter]::GetBytes([uint32]256).CopyTo($blk, 16)
    [BitConverter]::GetBytes([uint32]$blockNo).CopyTo($blk, 20)
    [BitConverter]::GetBytes([uint32]$numBlocks).CopyTo($blk, 24)
    [BitConverter]::GetBytes([uint32]$FAMILY_RP2040).CopyTo($blk, 28)
    [Array]::Copy($payload, 0, $blk, 32, 256)
    [BitConverter]::GetBytes([uint32]"0x0AB16F30").CopyTo($blk, 508)
    return $blk
}

function Clear-FreeSpace($img) {
    # Затираем всё, что не принадлежит файлам: свободные кластеры и записи удалённых
    # файлов в корневой папке. Иначе в образ попадут остатки старых файлов платы
    # (журнал, старые пароли), даже если сами файлы уже удалены.
    $bps = [BitConverter]::ToUInt16($img, 11); $spc = $img[13]
    $rsv = [BitConverter]::ToUInt16($img, 14); $nf = $img[16]
    $rde = [BitConverter]::ToUInt16($img, 17); $spf = [BitConverter]::ToUInt16($img, 22)
    $tot = [BitConverter]::ToUInt16($img, 19)
    $fat = $rsv * $bps
    $root = ($rsv + $nf * $spf) * $bps
    $data = $root + $rde * 32
    $nclus = [math]::Floor(($tot * $bps - $data) / ($spc * $bps))
    if ($nclus -ge 4085) { throw "Ожидалась FAT12, а кластеров $nclus" }
    $cleared = 0
    for ($c = 2; $c -lt $nclus + 2; $c++) {
        $v = [BitConverter]::ToUInt16($img, $fat + [math]::Floor($c * 3 / 2))
        if ($c % 2) { $v = $v -shr 4 } else { $v = $v -band 0xFFF }
        if ($v -eq 0) {
            [Array]::Clear($img, $data + ($c - 2) * $spc * $bps, $spc * $bps)
            $cleared++
        }
    }
    $deleted = 0
    for ($e = 0; $e -lt $rde; $e++) {
        if ($img[$root + $e * 32] -eq 0xE5) { [Array]::Clear($img, $root + $e * 32, 32); $deleted++ }
    }
    "Затёрто: свободных кластеров $cleared, удалённых записей $deleted"
}

# ---------- диск ----------
if ($Drive) { $fs = [byte[]](Read-Drive $Drive) }
elseif ($FromRaw) { $fs = [IO.File]::ReadAllBytes($FromRaw) }
else { throw "Укажите -Drive D: или -FromRaw файл.img" }
if ($fs.Length -ne $FS_SIZE) { throw "Размер диска должен быть $FS_SIZE байт" }

if ($SaveRaw) {
    # Резервная копия — как есть, ничего не затираем
    [IO.File]::WriteAllBytes($SaveRaw, $fs)
    "Сохранено: $SaveRaw (sha256 " + (Get-FileHash $SaveRaw).Hash.Substring(0, 16) + ")"
}
if (-not $Out) { return }
# Образ для других людей — без остатков старых файлов. Копию для восстановления (-NoFirmware) не трогаем.
if (-not $NoFirmware) { Clear-FreeSpace $fs }

# ---------- блоки: прошивка + диск ----------
# Сначала диск, потом прошивка: загрузчик RP2040 в обратном порядке теряет вторую часть
# (проверено: прошивка записывается, а диск — нет).
$pages = New-Object System.Collections.Generic.List[object]
for ($o = 0; $o -lt $FS_SIZE; $o += 256) {
    $payload = New-Object byte[] 256
    [Array]::Copy($fs, $o, $payload, 0, 256)
    $pages.Add(@([uint32]($FS_ADDR + $o), $payload))
}
if (-not $NoFirmware) {
    $fw = [IO.File]::ReadAllBytes((Resolve-Path $Firmware))
    for ($o = 0; $o -lt $fw.Length; $o += 512) {
        $addr = [BitConverter]::ToUInt32($fw, $o + 12)
        if ($addr -ge [uint32]"0x100FF000") { throw "Прошивка заходит в область настроек/диска — другая версия?" }
        $payload = New-Object byte[] 256
        [Array]::Copy($fw, $o + 32, $payload, 0, 256)
        $pages.Add(@($addr, $payload))
    }
}


$outStream = [IO.File]::Create($Out)
try {
    for ($i = 0; $i -lt $pages.Count; $i++) {
        $blk = New-Uf2Block $pages[$i][0] $pages[$i][1] $i $pages.Count
        $outStream.Write($blk, 0, 512)
    }
} finally { $outStream.Close() }
"Готово: $Out ($($pages.Count) блоков, $((Get-Item $Out).Length) байт)"
