# =====================================================================
#  Обновление образа диска CIRCUITPY прямо на компьютере — без платы.
#
#  Берёт образ диска из прошлого установочного файла (или .img), сравнивает
#  каждый файл с папкой device\ и заменяет изменившиеся. Новых файлов
#  не добавляет: если в device\ появился файл, которого нет в образе, —
#  остановится и скажет (тогда образ собирается через плату, см. make-image.ps1).
#
#  Пример (обновить образ 2.3 до текущих файлов и собрать установочный файл):
#   powershell -ExecutionPolicy Bypass -File tools\update-image.ps1 `
#       -FromUf2 PassPuck-2.3.uf2 -OutImg new.img
#   powershell -ExecutionPolicy Bypass -File tools\make-image.ps1 -FromRaw new.img -Out PassPuck-2.4.uf2
# =====================================================================
param(
    [string]$FromUf2,
    [string]$FromRaw,
    [Parameter(Mandatory = $true)][string]$OutImg,
    [string]$Device
)
$ErrorActionPreference = "Stop"
if (-not $Device) { $Device = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\device" }
$FS_ADDR = [uint32]"0x10100000"
$FS_SIZE = 1048576

# ---------- образ диска ----------
if ($FromUf2) {
    $u = [IO.File]::ReadAllBytes((Resolve-Path $FromUf2))
    $img = New-Object byte[] $FS_SIZE
    for ($o = 0; $o -lt $u.Length; $o += 512) {
        $a = [BitConverter]::ToUInt32($u, $o + 12)
        if ($a -ge $FS_ADDR -and $a -lt $FS_ADDR + $FS_SIZE) { [Array]::Copy($u, $o + 32, $img, $a - $FS_ADDR, 256) }
    }
} elseif ($FromRaw) { $img = [IO.File]::ReadAllBytes((Resolve-Path $FromRaw)) }
else { throw "Укажите -FromUf2 или -FromRaw" }

# ---------- устройство FAT12 ----------
$bps = [BitConverter]::ToUInt16($img, 11); $spc = $img[13]
$rsv = [BitConverter]::ToUInt16($img, 14); $nf = $img[16]
$rde = [BitConverter]::ToUInt16($img, 17); $spf = [BitConverter]::ToUInt16($img, 22)
$tot = [BitConverter]::ToUInt16($img, 19)
$fatStart = $rsv * $bps
$rootStart = ($rsv + $nf * $spf) * $bps
$dataStart = $rootStart + $rde * 32
$clSize = $spc * $bps
$nclus = [math]::Floor(($tot * $bps - $dataStart) / $clSize)
if ($nclus -ge 4085 -or $img[510] -ne 0x55) { throw "Это не диск FAT12" }

function Get-Fat($c) {
    $v = [BitConverter]::ToUInt16($img, $fatStart + [math]::Floor($c * 3 / 2))
    if ($c % 2) { return $v -shr 4 } else { return $v -band 0xFFF }
}
function Set-Fat($c, $val) {
    for ($f = 0; $f -lt $nf; $f++) {               # во всех копиях таблицы
        $o = $fatStart + $f * $spf * $bps + [math]::Floor($c * 3 / 2)
        $v = [BitConverter]::ToUInt16($img, $o)
        if ($c % 2) { $v = ($v -band 0x000F) -bor ($val -shl 4) } else { $v = ($v -band 0xF000) -bor $val }
        $b = [BitConverter]::GetBytes([uint16]$v); $img[$o] = $b[0]; $img[$o + 1] = $b[1]
    }
}
function Get-Chain($first) {
    $list = New-Object System.Collections.Generic.List[int]
    $c = $first
    while ($c -ge 2 -and $c -lt 0xFF8) { $list.Add($c); $c = Get-Fat $c; if ($list.Count -gt $nclus) { throw "Цепочка кластеров зациклена" } }
    return ,$list
}
function Cluster-Offset($c) { return $dataStart + ($c - 2) * $clSize }

function Read-Dir($first) {
    # Список записей папки: имя (длинное, если есть), атрибуты, кластер, размер, где лежит запись
    $offsets = New-Object System.Collections.Generic.List[int]
    if ($first -eq 0) { for ($e = 0; $e -lt $rde; $e++) { $offsets.Add($rootStart + $e * 32) } }
    else { foreach ($c in (Get-Chain $first)) { for ($e = 0; $e -lt $clSize / 32; $e++) { $offsets.Add((Cluster-Offset $c) + $e * 32) } } }
    $out = @(); $lfn = @{}
    foreach ($o in $offsets) {
        $b0 = $img[$o]
        if ($b0 -eq 0) { break }
        if ($b0 -eq 0xE5) { $lfn = @{}; continue }
        $attr = $img[$o + 11]
        if ($attr -eq 0x0F) {
            $seq = $b0 -band 0x1F; $chars = ""
            foreach ($p in @(@(1, 5), @(14, 6), @(28, 2))) {
                for ($k = 0; $k -lt $p[1]; $k++) {
                    $ch = [BitConverter]::ToUInt16($img, $o + $p[0] + $k * 2)
                    if ($ch -ne 0 -and $ch -ne 0xFFFF) { $chars += [char]$ch }
                }
            }
            $lfn[$seq] = $chars; continue
        }
        if ($attr -band 0x08) { $lfn = @{}; continue }   # метка тома
        if ($lfn.Count) { $name = (($lfn.Keys | Sort-Object) | % { $lfn[$_] }) -join "" }
        else {
            $base = [Text.Encoding]::ASCII.GetString($img, $o, 8).TrimEnd()
            $ext = [Text.Encoding]::ASCII.GetString($img, $o + 8, 3).TrimEnd()
            $name = if ($ext) { "$base.$ext" } else { $base }
        }
        $lfn = @{}
        if ($name -eq "." -or $name -eq "..") { continue }
        $out += [pscustomobject]@{ Name = $name; Dir = [bool]($attr -band 0x10)
            Cluster = [BitConverter]::ToUInt16($img, $o + 26); Size = [BitConverter]::ToUInt32($img, $o + 28); Entry = $o }
    }
    return $out
}

function Read-File($entry) {
    $data = New-Object byte[] $entry.Size; $pos = 0
    foreach ($c in (Get-Chain $entry.Cluster)) {
        $n = [math]::Min($clSize, $entry.Size - $pos); if ($n -le 0) { break }
        [Array]::Copy($img, (Cluster-Offset $c), $data, $pos, $n); $pos += $n
    }
    return ,$data
}

function Write-File($entry, [byte[]]$data) {
    # Старые кластеры освобождаем, новые берём первые свободные
    foreach ($c in (Get-Chain $entry.Cluster)) { Set-Fat $c 0 }
    $need = [math]::Ceiling($data.Length / $clSize)
    $free = New-Object System.Collections.Generic.List[int]
    for ($c = 2; $c -lt $nclus + 2 -and $free.Count -lt $need; $c++) { if ((Get-Fat $c) -eq 0) { $free.Add($c) } }
    if ($free.Count -lt $need) { throw "На диске не хватает места для $($entry.Name)" }
    for ($i = 0; $i -lt $need; $i++) {
        Set-Fat $free[$i] $(if ($i -eq $need - 1) { 0xFFF } else { $free[$i + 1] })
        $o = Cluster-Offset $free[$i]
        [Array]::Clear($img, $o, $clSize)
        [Array]::Copy($data, $i * $clSize, $img, $o, [math]::Min($clSize, $data.Length - $i * $clSize))
    }
    $first = if ($need) { $free[0] } else { 0 }
    $b = [BitConverter]::GetBytes([uint16]$first); $img[$entry.Entry + 26] = $b[0]; $img[$entry.Entry + 27] = $b[1]
    [BitConverter]::GetBytes([uint32]$data.Length).CopyTo($img, $entry.Entry + 28)
}

function Find-Entry($relPath) {
    $dir = 0; $parts = $relPath.Split("\")
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $e = Read-Dir $dir | ? { $_.Name -ieq $parts[$i] } | Select-Object -First 1
        if (-not $e) { return $null }
        if ($i -lt $parts.Count - 1) { $dir = $e.Cluster } else { return $e }
    }
}

# ---------- сравниваем и заменяем ----------
$root = (Resolve-Path $Device).Path.TrimEnd("\")
$changed = 0; $same = 0
foreach ($f in Get-ChildItem $root -Recurse -File) {
    $rel = $f.FullName.Substring($root.Length + 1)
    $e = Find-Entry $rel
    if (-not $e) { throw "В образе нет файла $rel — новый файл добавляется только через плату (make-image.ps1)" }
    $new = [IO.File]::ReadAllBytes($f.FullName)
    $old = Read-File $e
    if ([Linq.Enumerable]::SequenceEqual([byte[]]$old, [byte[]]$new)) { $same++; continue }
    Write-File $e $new
    $check = Read-File (Find-Entry $rel)
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$check, [byte[]]$new)) { throw "Проверка $rel после записи не прошла" }
    "Заменён: $rel ($($old.Length) -> $($new.Length) байт)"; $changed++
}
[IO.File]::WriteAllBytes($OutImg, $img)
"Готово: $OutImg (заменено $changed, без изменений $same)"
