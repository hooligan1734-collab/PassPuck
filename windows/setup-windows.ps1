# =====================================================================
#  PassPuck: настройка Windows (один раз на каждом компьютере)
#
#  Что делает:
#   1. Проверяет, что в Windows есть английский и русский языки ввода
#      (если русского нет — предлагает добавить).
#   2. Назначает сочетания: английский — Ctrl+Shift+1, русский — Ctrl+Shift+2.
#      Через них PassPuck переключает раскладку, когда вводит пароль.
#   3. По желанию копирует эти настройки на экран входа в Windows
#      (нужно, чтобы входить в Windows паролем с русскими буквами).
#      Для этого Windows попросит права администратора.
#
#  Запуск: двойной щелчок по «Настроить Windows.cmd».
#  Пробный запуск без изменений: setup-windows.ps1 -DryRun
# =====================================================================
param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$HotKeysPath = "HKCU:\Control Panel\Input Method\Hot Keys"
$Modifiers = [byte[]](0x06, 0xC0, 0x00, 0x00)   # Ctrl + Shift (левые и правые)
$Taken = @{}                                     # номера записей, уже выбранные в этом запуске

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }

function Get-Hkl($tip) {
    # «0409:00000409» → 0x04090409 (язык + раскладка, как их хранит Windows)
    $parts = $tip.Split(":")
    $lang = [Convert]::ToUInt32($parts[0], 16)
    $layout = [Convert]::ToUInt32($parts[1], 16)
    if (($layout -band 0xFFFF0000) -eq 0) { return [uint32](($layout -shl 16) -bor $lang) }
    return [uint32](($lang -shl 16) -bor $lang)
}

function Find-Language($list, $prefix) {
    foreach ($l in $list) {
        if ($l.LanguageTag -like "$prefix*" -and $l.InputMethodTips.Count -gt 0) { return $l }
    }
    return $null
}

function Set-LanguageHotKey($name, $hkl, $digit) {
    $hklBytes = [BitConverter]::GetBytes([uint32]$hkl)
    $vk = [byte[]]((0x30 + $digit), 0, 0, 0)
    # Если для этого языка сочетание уже есть — меняем его, иначе берём свободный номер
    $slot = $null
    $used = @{}
    if (Test-Path $HotKeysPath) {
        foreach ($k in Get-ChildItem $HotKeysPath) {
            $used[$k.PSChildName] = $true
            if ($Taken.ContainsKey($k.PSChildName)) { continue }
            $target = (Get-ItemProperty $k.PSPath)."Target IME"
            if ($target -is [byte[]] -and [BitConverter]::ToUInt32($target, 0) -eq $hkl) { $slot = $k.PSChildName }
        }
    }
    if (-not $slot) {
        for ($i = 0x100; $i -le 0x11F; $i++) {
            $n = "{0:X8}" -f $i
            if (-not $used.ContainsKey($n) -and -not $Taken.ContainsKey($n)) { $slot = $n; break }
        }
    }
    $Taken[$slot] = $true
    Say ("  {0}: Ctrl+Shift+{1}  (раскладка {2:X8}, запись {3})" -f $name, $digit, $hkl, $slot)
    if ($DryRun) { return }
    $path = Join-Path $HotKeysPath $slot
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name "Key Modifiers" -Value $Modifiers -Type Binary
    Set-ItemProperty -Path $path -Name "Target IME" -Value $hklBytes -Type Binary
    Set-ItemProperty -Path $path -Name "Virtual Key" -Value $vk -Type Binary
    # Сообщаем Windows о новом сочетании сразу (если не получится — заработает после перезахода)
    try {
        [ImmHotKey]::ImmSetHotKey([uint32]("0x" + $slot), 0xC006, [uint32](0x30 + $digit), [IntPtr][int64]$hkl) | Out-Null
    } catch { }
}

Add-Type -Namespace "" -Name ImmHotKey -MemberDefinition @'
[DllImport("imm32.dll")] public static extern bool ImmSetHotKey(uint id, uint modifiers, uint vkey, IntPtr hkl);
'@ -ErrorAction SilentlyContinue

Say ""
Say "PassPuck: настройка Windows" "Cyan"
if ($DryRun) { Say "(пробный запуск: ничего не меняется)" "Yellow" }
Say ""

# ---------- 1. Языки ----------
$list = Get-WinUserLanguageList
$en = Find-Language $list "en"
$ru = Find-Language $list "ru"
if (-not $en) {
    Say "В Windows нет английского языка ввода. Добавьте его: Параметры -> Время и язык -> Язык." "Red"
    Read-Host "Нажмите Enter, чтобы закрыть"; exit 1
}
if (-not $ru) {
    $answer = Read-Host "Русского языка ввода нет. Добавить его? (д/н)"
    if ($answer -match "^[дДyY]") {
        if (-not $DryRun) {
            $list.Add("ru-RU")
            Set-WinUserLanguageList $list -Force
            $list = Get-WinUserLanguageList
        }
        $ru = Find-Language $list "ru"
        Say "Русский язык добавлен." "Green"
    }
    if (-not $ru) { Say "Без русского языка пароли с русскими буквами вводиться не будут." "Yellow" }
}

# ---------- 2. Сочетания клавиш ----------
Say "Сочетания клавиш для языков:"
Set-LanguageHotKey "английский" (Get-Hkl $en.InputMethodTips[0]) 1
if ($ru) { Set-LanguageHotKey "русский   " (Get-Hkl $ru.InputMethodTips[0]) 2 }
Say ""

# ---------- 3. Экран входа ----------
Say "Чтобы входить в Windows паролем с русскими буквами, эти настройки нужно"
Say "скопировать на экран входа. Windows спросит разрешение администратора."
$answer = Read-Host "Скопировать на экран входа? (д/н)"
if ($answer -match "^[дДyY]") {
    if ($DryRun) {
        Say "  (пробный запуск: копирование пропущено)"
    } elseif (Get-Command Copy-UserInternationalSettingsToSystem -ErrorAction SilentlyContinue) {
        try {
            Start-Process powershell -Verb RunAs -Wait -ArgumentList @(
                "-NoProfile", "-Command",
                "Copy-UserInternationalSettingsToSystem -WelcomeScreen `$true -NewUser `$true")
            Say "Готово: настройки скопированы на экран входа." "Green"
        } catch {
            Say "Не получилось (нет разрешения администратора)." "Yellow"
        }
    } else {
        # Старая Windows 10 без нужной команды — открываем окно, где это делается одной кнопкой
        Say "Откроется окно «Регион». Вкладка «Дополнительно» -> «Копировать параметры» ->" "Yellow"
        Say "отметьте «Экран приветствия и системные учётные записи» -> OK." "Yellow"
        Start-Process "intl.cpl"
    }
}

Say ""
Say "Готово. Если Ctrl+Shift+1/2 не переключают язык сразу — выйдите из Windows" "Green"
Say "и войдите снова (или перезагрузите компьютер)." "Green"
Read-Host "Нажмите Enter, чтобы закрыть"
