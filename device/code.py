# =====================================================================
#  PassPuck — карманный менеджер паролей на RP2040-Zero (CircuitPython)
#  Версия 2.0
#
#  Файл разбит на разделы:
#    1. НАСТРОЙКИ          — то, что можно спокойно менять под себя
#    2. Журнал (log.txt)   — запись событий и ошибок
#    3. Пароли             — чтение и безопасное сохранение passwords.py
#    4. Память настроек    — Enter / Ctrl first / Jiggle (не пропадают без питания)
#    5. Светодиод, экран, кнопки, клавиатура
#    6. Действия           — набор пароля, генерация, показ, Jiggle
#    7. Главный цикл       — обработка нажатий
#    8. Запуск и аварийный экран
#
#  Сами пароли лежат в отдельном файле passwords.py.
# =====================================================================

import time
import math
import os
import random
import board
import busio
import digitalio
import microcontroller
import storage
import supervisor
import traceback
import usb_hid
import neopixel
import displayio
import terminalio
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_display_text import label
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.triangle import Triangle
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.roundrect import RoundRect


# =====================================================================
#  1. НАСТРОЙКИ — можно менять
# =====================================================================

VERSION = "2.0"

# Тип экрана. Оставьте раскомментированной ОДНУ строку:
OLED_TYPE = "SH1106"      # экран 1.3"
#OLED_TYPE = "SSD1306"    # экран 0.96"

# Названия профилей по умолчанию. Свои названия задаются в passwords.py
# (через PassPuck Editor.html) — тогда эти не используются.
PROFILE_NAMES = {
    1: "Work gen",
    2: "Work Laptop",
    3: "Crypto Vault",
    4: "Work fix",
    5: "Admin Access",
    6: "Extra Fix",
}

# Генератор паролей (Gen Pass, профили 1-3).
# Алфавит выбирается для каждого профиля в его меню: «Gen: EN» — символы из CHARS,
# «Gen: RU» — русские буквы и цифры.
PASSWORD_LENGTH = 12      # длина нового пароля
CHARS ="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-="

# Сон экрана. Выбирается прямо на устройстве: пункт SETTINGS на главном экране.
SLEEP_PRESETS = (15, 30, 60, 120, 300, 0)   # варианты «Sleep», секунды. 0 = никогда
                                            # (экран горит всегда — OLED со временем может выгорать)
SLEEP_DEFAULT_PRESET = 1                    # по умолчанию 30 с (номер в списке выше, считая с нуля)
SLEEP_STYLES = ("Off", "Stars", "Bounce", "Rain")  # Off — экран выключается, остальное — анимации
ANIMATION_FRAME_TIME = 0.05                 # скорость анимации: пауза между кадрами, сек

# Яркость экрана и светодиода. Выбирается на устройстве: SETTINGS → Screen / LED.
# Каждый вариант: (название на экране, яркость от 0.0 до 1.0)
SCREEN_BRIGHTNESS = (("Low", 0.05), ("Mid", 0.4), ("High", 1.0))
LED_BRIGHTNESS = (("Off", 0.0), ("Low", 0.2), ("High", 1.0))
BRIGHTNESS_DEFAULT = 2                      # по умолчанию High (номер в списках выше, с нуля)

# Заставка при включении: сколько секунд показывать «PassPuck» и версию (0 — не показывать)
SPLASH_TIME = 1.0

# Шрифт с русскими буквами для средней строки экрана (названия, пароли, меню).
# Если файла нет — всё работает, но русские буквы на экране будут показаны как «?».
FONT_FILE = "/fonts/passpuck-cyr.bdf"

# Время (в секундах)
TYPING_DELAY = 0.05       # пауза между символами при наборе пароля
TYPING_START_DELAY = 0.4  # пауза перед набором: экран блокировки Windows успевает «проснуться»
LONG_PRESS_TIME = 1.0     # сколько держать «Ввод», чтобы открыть меню
NAV_LOCK_HOLD_TIME = 1.0  # сколько держать «Назад»+«Вперёд» для блокировки ПК (Win+L)

# Jiggle: как часто шевелить мышь. Выбирается на устройстве: JIGGLE → долгий «Ввод» → Every.
# Windows обычно засыпает после 5-10 минут бездействия, поэтому интервал должен быть меньше.
JIGGLE_PRESETS = (30, 60, 120, 300, 600)   # секунды: 30s, 1m, 2m, 5m, 10m
JIGGLE_DEFAULT_PRESET = 1                  # по умолчанию 1 минута (номер в списке выше, с нуля)

# Пароли с русскими буквами.
# Устройство само переключает раскладку Windows этими сочетаниями клавиш.
# Их нужно ОДИН РАЗ назначить в Windows: Параметры → Время и язык → Ввод →
# Дополнительные параметры клавиатуры → Сочетания клавиш для языков ввода:
#   английский — Ctrl+Shift+1,  русский — Ctrl+Shift+2
# На Mac, Linux или компьютере без этих сочетаний выберите на устройстве
# SETTINGS → Layout: Off — тогда раскладку нужно включать самому перед набором.
LANG_EN_HOTKEY = (Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.ONE)
LANG_RU_HOTKEY = (Keycode.LEFT_CONTROL, Keycode.SHIFT, Keycode.TWO)
LANG_SWITCH_DELAY = 0.3   # пауза после переключения раскладки, сек

# Журнал: когда log.txt вырастет больше этого размера, он станет log_old.txt
LOG_MAX_SIZE = 16 * 1024  # байт

# Подключение (менять, только если перепаяли на другие контакты)
PIN_SDA = board.GP4
PIN_SCL = board.GP5
PIN_BACK = board.GP6      # если поменять, поменяйте и в boot.py
PIN_ENTER = board.GP7
PIN_FWD = board.GP8
OLED_ADDRESS = 0x3C
# Если на конкретном устройстве кнопки припаяны к другим контактам — не меняйте этот файл,
# а положите рядом hardware_pins.py, например:
#     import board
#     PIN_ENTER = board.GP8
#     PIN_FWD = board.GP7
# Значения из него заменят указанные выше (только для этого устройства).
HARDWARE_PINS_USED = False
try:
    import hardware_pins as _hw
    PIN_BACK = getattr(_hw, "PIN_BACK", PIN_BACK)
    PIN_ENTER = getattr(_hw, "PIN_ENTER", PIN_ENTER)
    PIN_FWD = getattr(_hw, "PIN_FWD", PIN_FWD)
    HARDWARE_PINS_USED = True
except ImportError:
    pass
I2C_FREQUENCY = 400000    # скорость связи с экраном. Если экран сбоит — поставьте 100000
BUTTON_DEBOUNCE = 0.03    # защита от дребезга кнопок, сек

# --- ниже этой линии менять без необходимости не стоит ---

TOTAL_PROFILES = 6
JIGGLE_ITEM = TOTAL_PROFILES           # 7-й пункт главного экрана — JIGGLE
SETTINGS_ITEM = TOTAL_PROFILES + 1     # 8-й пункт — SETTINGS
MAIN_MENU_ITEMS = TOTAL_PROFILES + 2


# =====================================================================
#  2. ЖУРНАЛ (log.txt)
#  Пишем только важные события: включение, проблемы с паролями,
#  сохранение Gen Pass, смену настроек и ошибки.
#  Сами пароли и обычные нажатия кнопок НЕ пишутся никогда.
# =====================================================================

LOG_FILE = "/log.txt"
LOG_OLD_FILE = "/log_old.txt"

# Может ли устройство писать на флешку.
# Обычный режим — да (это разрешает boot.py).
# Режим редактирования (подключили с зажатой «Назад») — нет, флешкой владеет компьютер.
FS_WRITABLE = not storage.getmount("/").readonly

boot_number = 0   # номер включения, заполняется при запуске


def log(message):
    """Пишет сообщение в консоль и в log.txt. Каждая строка помечается
    номером включения и секундами с момента включения."""
    prefix = "[#{} {}s] ".format(boot_number, int(time.monotonic()))
    text = "".join(prefix + row + "\n" for row in str(message).split("\n"))
    print(text, end="")
    if not FS_WRITABLE:
        return
    try:
        try:
            if os.stat(LOG_FILE)[6] > LOG_MAX_SIZE:
                try:
                    os.remove(LOG_OLD_FILE)
                except OSError:
                    pass
                os.rename(LOG_FILE, LOG_OLD_FILE)
        except OSError:
            pass  # журнала ещё нет — создастся ниже
        with open(LOG_FILE, "a") as f:
            f.write(text)
        os.sync()
    except Exception as e:
        print("Не удалось записать журнал:", repr(e))


def log_exception(where, e):
    """Пишет в журнал ошибку вместе с подробностями (где именно в коде она случилась)."""
    try:
        details = "".join(traceback.format_exception(e)).rstrip()
    except Exception:
        details = repr(e)
    log("ОШИБКА ({}): {}\n{}".format(where, repr(e), details))


# =====================================================================
#  3. ПАРОЛИ
#  Основной файл — passwords.py. При каждом сохранении:
#    1) новый вариант пишется в passwords.tmp и проверяется;
#    2) старый passwords.py становится passwords.bak (резервная копия);
#    3) passwords.tmp становится passwords.py.
#  Если питание пропадёт посередине, хотя бы один целый файл останется.
#  При запуске файлы пробуются по порядку: passwords.py → .bak → .tmp
# =====================================================================

PASSWORDS_FILE = "/passwords.py"
PASSWORDS_BACKUP = "/passwords.bak"
PASSWORDS_TEMP = "/passwords.tmp"

passwords = {}            # {номер профиля: пароль}
profile_names = dict(PROFILE_NAMES)   # названия профилей (берутся из passwords.py, если там есть)
passwords_source = None   # из какого файла загружены; None — не загрузились


def read_passwords_file(path):
    """Читает файл паролей. Возвращает ({1: пароль, ...}, {1: название, ...}).
    Если файл сломан — выбрасывает ошибку."""
    with open(path, "r") as f:
        text = f.read()
    data = {}
    exec(text, data)
    result = {}
    for n in (1, 2, 3):
        result[n] = str(data["AUTO_PASSWORDS"].get(n, ""))
    for n in (4, 5, 6):
        result[n] = str(data["MANUAL_PASSWORDS"].get(n, ""))
    # Названия профилей в passwords.py необязательны (в старых файлах их нет)
    file_names = data.get("PROFILE_NAMES", {})
    names = {}
    for n in range(1, TOTAL_PROFILES + 1):
        names[n] = str(file_names.get(n, PROFILE_NAMES.get(n, "Profile {}".format(n))))
    return result, names


def load_passwords():
    """Загружает пароли при включении и пишет в журнал, откуда они взяты."""
    global passwords, passwords_source, profile_names
    problems = []
    for path in (PASSWORDS_FILE, PASSWORDS_BACKUP, PASSWORDS_TEMP):
        try:
            passwords, profile_names = read_passwords_file(path)
            passwords_source = path
            break
        except OSError as e:
            # errno 2 — файла просто нет (для .bak и .tmp это нормально)
            if path == PASSWORDS_FILE or e.errno != 2:
                problems.append("{}: {}".format(path, repr(e)))
        except Exception as e:
            # repr ошибки не содержит текста пароля, только тип и номер строки
            problems.append("{}: {}".format(path, repr(e)))
    else:
        passwords = {}
        passwords_source = None

    for p in problems:
        log("Пароли: не удалось прочитать " + p)
    if passwords_source is None:
        log("Пароли: НЕ ЗАГРУЖЕНЫ ни из одного файла. Набор и Gen Pass отключены.")
    elif passwords_source != PASSWORDS_FILE:
        log("Пароли: ВНИМАНИЕ, загружена резервная копия {}. "
            "Пароли могут быть устаревшими.".format(passwords_source))
    for n in bad_char_profiles():
        log("Пароли: в профиле {} есть символы, которые устройство не может набрать "
            "(не английские и не русские буквы). Этот профиль набираться не будет.".format(n))


# Русская раскладка (ЙЦУКЕН): какая клавиша даёт какую букву.
# Например, «й» — это клавиша Q, «Й» — Shift+Q.
_RU_LETTERS = "йцукенгшщзхъфывапролджэячсмитьбю"
_RU_LETTERS_UPPER = "ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ"  # (upper() в CircuitPython не знает кириллицу)
_RU_KEYS = (
    Keycode.Q, Keycode.W, Keycode.E, Keycode.R, Keycode.T, Keycode.Y, Keycode.U,
    Keycode.I, Keycode.O, Keycode.P, Keycode.LEFT_BRACKET, Keycode.RIGHT_BRACKET,
    Keycode.A, Keycode.S, Keycode.D, Keycode.F, Keycode.G, Keycode.H, Keycode.J,
    Keycode.K, Keycode.L, Keycode.SEMICOLON, Keycode.QUOTE,
    Keycode.Z, Keycode.X, Keycode.C, Keycode.V, Keycode.B, Keycode.N, Keycode.M,
    Keycode.COMMA, Keycode.PERIOD,
)
RU_KEYMAP = {}            # {"й": (клавиша, нужен Shift), ...}
for _low, _up, _key in zip(_RU_LETTERS, _RU_LETTERS_UPPER, _RU_KEYS):
    RU_KEYMAP[_low] = (_key, False)
    RU_KEYMAP[_up] = (_key, True)
RU_KEYMAP["ё"] = (Keycode.GRAVE_ACCENT, False)
RU_KEYMAP["Ё"] = (Keycode.GRAVE_ACCENT, True)
RU_KEYMAP["№"] = (Keycode.THREE, True)

# Символы для Gen Pass в режиме «Gen: RU»: русские буквы (без ё) и цифры.
# Цифры одинаковые в обеих раскладках, поэтому раскладка внутри пароля не переключается.
RU_GEN_CHARS = _RU_LETTERS + _RU_LETTERS_UPPER + "0123456789"
DIGITS = "0123456789"


def char_lang(c):
    """"en" — символ английской клавиатуры, "ru" — русская буква, None — набрать нельзя."""
    if 32 <= ord(c) <= 126:
        return "en"
    if c in RU_KEYMAP:
        return "ru"
    return None


def is_typable(text):
    """Можно ли набрать весь текст (английские символы и русские буквы)."""
    for c in text:
        if char_lang(c) is None:
            return False
    return True


def has_russian(text):
    for c in text:
        if char_lang(c) == "ru":
            return True
    return False


def bad_char_profiles():
    return [n for n in sorted(passwords) if not is_typable(passwords[n])]


def escape_password(pw):
    return pw.replace("\\", "\\\\").replace('"', '\\"')


def passwords_file_text():
    """Собирает текст passwords.py из текущих паролей."""
    lines = [
        "# ================= Пароли PassPuck =================",
        "# Удобнее всего менять этот файл через PassPuck Editor.html.",
        "#",
        "# PROFILE_NAMES — названия профилей на экране (можно по-русски, до 20 символов).",
        "# Профили 1-3: пароль можно сгенерировать на устройстве (меню -> Gen Pass).",
        "# Профили 4-6: пароль задаётся только здесь.",
        "#",
        "# Как менять вручную:",
        "#  - меняйте только текст внутри кавычек;",
        "#  - можно латиницу, цифры, символы с английской клавиатуры и русские буквы;",
        "#  - для русских букв в Windows должны быть настроены сочетания",
        "#    Ctrl+Shift+1 (английский) и Ctrl+Shift+2 (русский), см. инструкцию;",
        "#  - символы \" и \\ пишите как \\\" и \\\\ ;",
        "#  - после сохранения подождите 10 секунд, прежде чем отключать устройство.",
        "# ====================================================",
        "",
        "PROFILE_NAMES = {",
    ]
    for n in range(1, TOTAL_PROFILES + 1):
        lines.append('    {}: "{}",'.format(n, escape_password(profile_names.get(n, ""))))
    lines += ["}", "", "AUTO_PASSWORDS = {"]
    for n in (1, 2, 3):
        lines.append('    {}: "{}",'.format(n, escape_password(passwords.get(n, ""))))
    lines += ["}", "", "MANUAL_PASSWORDS = {"]
    for n in (4, 5, 6):
        lines.append('    {}: "{}",'.format(n, escape_password(passwords.get(n, ""))))
    lines += ["}", ""]
    return "\n".join(lines)


def save_passwords():
    """Безопасно сохраняет пароли. Возвращает None при успехе или короткий текст ошибки для экрана."""
    if not FS_WRITABLE:
        return "Edit mode: no save"
    try:
        with open(PASSWORDS_TEMP, "w") as f:
            f.write(passwords_file_text())
        os.sync()
        if read_passwords_file(PASSWORDS_TEMP)[0] != passwords:
            raise ValueError("проверка записанного файла не совпала")
        try:
            os.remove(PASSWORDS_BACKUP)
        except OSError:
            pass
        try:
            os.rename(PASSWORDS_FILE, PASSWORDS_BACKUP)
        except OSError:
            pass
        os.rename(PASSWORDS_TEMP, PASSWORDS_FILE)
        os.sync()
        return None
    except Exception as e:
        log_exception("сохранение паролей", e)
        return "SAVE ERROR"


def generate_password(chars):
    """Случайный пароль из набора символов chars. Берём аппаратный генератор случайных
    чисел (os.urandom) и отбрасываем «лишние» значения, чтобы все символы выпадали
    с равной вероятностью."""
    n = len(chars)
    limit = 256 - (256 % n)
    result = []
    while len(result) < PASSWORD_LENGTH:
        for b in os.urandom(16):
            if b < limit and len(result) < PASSWORD_LENGTH:
                result.append(chars[b % n])
    return "".join(result)


# =====================================================================
#  4. ПАМЯТЬ НАСТРОЕК (NVM) — не стирается при отключении и перепрошивке файлов
#  Байты 0-3: метка "PWD6" (память размечена)
#  Байты 4-15: по 2 байта на профиль: Auto Enter и запасной байт
#              (раньше там был Shift+1, теперь не используется)  (P1: 4-5, ... P6: 14-15)
#  Байт 16: Jiggle, байт 17: запасной (раньше Random, теперь не используется)
#  Байты 18-19: счётчик включений (для журнала)
#  Байты 20-25: «Ctrl first» по профилям (P1: 20, ... P6: 25)
#  Байт 26: через сколько засыпать (номер в SLEEP_PRESETS), байт 27: стиль сна
#  Байт 28: как часто Jiggle (номер в JIGGLE_PRESETS)
#  Байт 29: яркость экрана, байт 30: яркость светодиода (номера в списках яркости)
#  Байты 31-36: алфавит Gen Pass по профилям (1 = RU, иначе EN)  (P1: 31, ... P6: 36)
#  Байт 38: переключение раскладки (1 = Off, иначе Auto)
#  Байт 37: одноразовая отметка «следующее включение — режим редактирования»
#           (ставит пункт SETTINGS → Edit mode, стирает boot.py)
#  Значение 1 = включено, всё остальное = выключено.
# =====================================================================

nvm = microcontroller.nvm
NVM_MAGIC = b"PWD6"
NVM_USED = 39
NVM_JIGGLE = 16
NVM_BOOT_COUNTER = 18
NVM_CTRL_FIRST = 20
NVM_SLEEP_PRESET = 26
NVM_SLEEP_STYLE = 27
NVM_JIGGLE_PRESET = 28
NVM_SCREEN_BRIGHTNESS = 29
NVM_LED_BRIGHTNESS = 30
NVM_GEN_RU = 31
NVM_EDIT_FLAG = 37        # если менять — поменяйте и в boot.py
EDIT_FLAG_VALUE = 0xA5
NVM_LAYOUT_OFF = 38


def nvm_prepare():
    """На новой плате память заполнена байтами 255. Размечаем её нулями (всё выключено)."""
    if bytes(nvm[0:4]) != NVM_MAGIC:
        nvm[0:NVM_USED] = NVM_MAGIC + bytes(NVM_USED - 4)
        nvm[NVM_SLEEP_PRESET] = SLEEP_DEFAULT_PRESET
        nvm[NVM_JIGGLE_PRESET] = JIGGLE_DEFAULT_PRESET
        nvm[NVM_SCREEN_BRIGHTNESS:NVM_LED_BRIGHTNESS + 1] = bytes([BRIGHTNESS_DEFAULT] * 2)


def load_brightness():
    """Возвращает (номер яркости экрана, номер яркости светодиода)."""
    screen = nvm[NVM_SCREEN_BRIGHTNESS]
    led = nvm[NVM_LED_BRIGHTNESS]
    if screen >= len(SCREEN_BRIGHTNESS):
        screen = BRIGHTNESS_DEFAULT
    if led >= len(LED_BRIGHTNESS):
        led = BRIGHTNESS_DEFAULT
    return screen, led


def save_brightness(screen, led):
    nvm[NVM_SCREEN_BRIGHTNESS:NVM_LED_BRIGHTNESS + 1] = bytes([screen, led])


def load_gen_ru(profile):
    """Генерировать ли для профиля русский пароль (иначе английский)."""
    return nvm[NVM_GEN_RU + profile - 1] == 1


def save_gen_ru(profile, enabled):
    nvm[NVM_GEN_RU + profile - 1] = 1 if enabled else 0


def load_layout_auto():
    """Переключать ли раскладку Windows автоматически (Ctrl+Shift+1 / Ctrl+Shift+2)."""
    return nvm[NVM_LAYOUT_OFF] != 1


def save_layout_auto(enabled):
    nvm[NVM_LAYOUT_OFF] = 0 if enabled else 1


def request_edit_mode():
    """Отметка для boot.py: при следующем запуске открыть диск CIRCUITPY."""
    nvm[NVM_EDIT_FLAG] = EDIT_FLAG_VALUE


def load_jiggle_preset():
    preset = nvm[NVM_JIGGLE_PRESET]
    return preset if preset < len(JIGGLE_PRESETS) else JIGGLE_DEFAULT_PRESET


def save_jiggle_preset(preset):
    nvm[NVM_JIGGLE_PRESET] = preset


def load_sleep_settings():
    """Возвращает (номер варианта времени сна, номер стиля сна)."""
    preset = nvm[NVM_SLEEP_PRESET]
    style = nvm[NVM_SLEEP_STYLE]
    if preset >= len(SLEEP_PRESETS):
        preset = SLEEP_DEFAULT_PRESET
    if style >= len(SLEEP_STYLES):
        style = 0
    return preset, style


def save_sleep_settings(preset, style):
    nvm[NVM_SLEEP_PRESET:NVM_SLEEP_STYLE + 1] = bytes([preset, style])


def nvm_next_boot_number():
    n = ((nvm[NVM_BOOT_COUNTER] << 8) | nvm[NVM_BOOT_COUNTER + 1]) + 1
    n &= 0xFFFF
    nvm[NVM_BOOT_COUNTER:NVM_BOOT_COUNTER + 2] = bytes([n >> 8, n & 0xFF])
    return n


def load_auto_enter(profile):
    """Нажимать ли Enter после пароля."""
    return nvm[4 + (profile - 1) * 2] == 1


def save_auto_enter(profile, enabled):
    nvm[4 + (profile - 1) * 2] = 1 if enabled else 0


def load_ctrl_first(profile):
    """Нажимать ли одиночный Ctrl перед набором (убирает заставку экрана блокировки)."""
    return nvm[NVM_CTRL_FIRST + profile - 1] == 1


def save_ctrl_first(profile, enabled):
    nvm[NVM_CTRL_FIRST + profile - 1] = 1 if enabled else 0


def load_jiggle_enabled():
    return nvm[NVM_JIGGLE] == 1


def save_jiggle_enabled(enabled):
    nvm[NVM_JIGGLE] = 1 if enabled else 0


# =====================================================================
#  5. СВЕТОДИОД, ЭКРАН, КНОПКИ, КЛАВИАТУРА
# =====================================================================

# --- Светодиод: синий пульс — готов, красный — меню, зелёная вспышка — пароль набран ---
try:
    pixel_pin = board.NEOPIXEL
except AttributeError:
    pixel_pin = board.GP16
pixel = neopixel.NeoPixel(pixel_pin, 1, brightness=1.0, auto_write=True)

in_menu = False


def update_led():
    if in_menu:
        pixel[0] = (255, 0, 0)
        return
    blue = int((math.sin(time.monotonic() * 1.2) + 1) * 5)
    pixel[0] = (0, 0, blue)


def flash_green():
    pixel[0] = (0, 255, 0)
    time.sleep(0.15)
    pixel[0] = (0, 0, 0)


# --- Кнопки: замыкают контакт на GND, поэтому «нажата» = значение False ---
def make_button(pin):
    b = digitalio.DigitalInOut(pin)
    b.direction = digitalio.Direction.INPUT
    b.pull = digitalio.Pull.UP
    return b


btn_back = make_button(PIN_BACK)
btn_enter = make_button(PIN_ENTER)
btn_fwd = make_button(PIN_FWD)


def pressed(btn):
    return not btn.value


def any_pressed():
    return pressed(btn_back) or pressed(btn_enter) or pressed(btn_fwd)


# --- Экран (создаётся в init_display) ---
display = None
splash = None
empty_splash = None
title_label = None
pass_label = None
bottom_label = None
icons_group = None
arrow_left = None
center_circle = None
arrow_right = None
jiggle_icon = None


CYRILLIC_FONT_LOADED = False
main_font = terminalio.FONT
FONT_GLYPHS = "".join(chr(c) for c in range(32, 127)) + \
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ№"


def load_main_font():
    """Загружает шрифт с кириллицей. Без него устройство работает, но без русских букв на экране."""
    global main_font, CYRILLIC_FONT_LOADED
    try:
        from adafruit_bitmap_font import bitmap_font
        main_font = bitmap_font.load_font(FONT_FILE)
        CYRILLIC_FONT_LOADED = True
    except Exception as e:
        main_font = terminalio.FONT
        CYRILLIC_FONT_LOADED = False
        log("Шрифт {} не загружен ({}). Русские буквы на экране будут «?».".format(FONT_FILE, repr(e)))


def preload_font_glyphs():
    """Заранее читает все нужные буквы шрифта (одним проходом по файлу — так быстрее)."""
    if CYRILLIC_FONT_LOADED:
        try:
            main_font.load_glyphs(FONT_GLYPHS)
        except Exception as e:
            log_exception("загрузка букв шрифта", e)


def init_display():
    """Запускает экран и рисует интерфейс. Ошибки здесь обычно значат проблему с проводами экрана."""
    global display, splash, empty_splash, title_label, pass_label, bottom_label
    global icons_group, arrow_left, center_circle, arrow_right, jiggle_icon

    displayio.release_displays()
    try:
        i2c = busio.I2C(PIN_SCL, PIN_SDA, frequency=I2C_FREQUENCY)
    except Exception as e:
        raise RuntimeError("Экран: нет связи по I2C (SDA=GP4, SCL=GP5). "
                           "Проверьте пайку и питание экрана. " + repr(e))
    try:
        import i2cdisplaybus
        display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=OLED_ADDRESS)
    except ImportError:
        display_bus = displayio.I2CDisplay(i2c, device_address=OLED_ADDRESS)

    if OLED_TYPE == "SSD1306":
        import adafruit_displayio_ssd1306
        display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)
    elif OLED_TYPE == "SH1106":
        import adafruit_displayio_sh1106
        display = adafruit_displayio_sh1106.SH1106(display_bus, width=132, height=64)
    else:
        raise RuntimeError("Неизвестный OLED_TYPE: " + str(OLED_TYPE))

    load_main_font()

    splash = displayio.Group(x=2)
    empty_splash = displayio.Group(x=2)
    display.root_group = splash

    title_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=5, y=6)
    splash.append(title_label)
    splash.append(Line(0, 14, 128, 14, color=0xFFFFFF))
    # Средняя строка (названия, пароли, меню) — шрифтом с кириллицей, если он есть
    pass_label = label.Label(main_font, text="", scale=1, color=0xFFFFFF, x=5, y=31)
    splash.append(pass_label)
    splash.append(Line(0, 48, 128, 48, color=0xFFFFFF))

    icons_group = displayio.Group()
    arrow_left = Triangle(22, 51, 12, 56, 22, 61, fill=0xFFFFFF, outline=0xFFFFFF)
    center_circle = Circle(64, 56, 4, fill=0xFFFFFF, outline=0xFFFFFF)
    arrow_right = Triangle(106, 51, 116, 56, 106, 61, fill=0xFFFFFF, outline=0xFFFFFF)
    icons_group.append(arrow_left)
    icons_group.append(center_circle)
    icons_group.append(arrow_right)
    splash.append(icons_group)

    bottom_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=5, y=56)
    splash.append(bottom_label)

    # Значок «мышка» в правом нижнем углу — виден, когда Jiggle включён
    jiggle_icon = displayio.Group()
    jiggle_icon.append(RoundRect(121, 50, 6, 10, 3, outline=0xFFFFFF))
    jiggle_icon.append(Line(124, 50, 124, 53, color=0xFFFFFF))
    jiggle_icon.hidden = True
    splash.append(jiggle_icon)

    init_sleep_animations()


def screen_text(text):
    """Если шрифта с кириллицей нет — русские буквы заменяются на «?»."""
    if CYRILLIC_FONT_LOADED:
        return text
    return "".join(c if 32 <= ord(c) <= 126 else "?" for c in text)


def set_centered_text(label_obj, text):
    """Пишет одну строку текста по центру экрана (6 пикселей на символ)."""
    if label_obj is pass_label:
        label_obj.y = 31
        text = screen_text(text)
    label_obj.text = text
    label_obj.x = max(0, (128 - len(text) * 6) // 2)


def set_bottom_mode(show_text=False):
    """Низ экрана: стрелки-подсказки или строка текста."""
    if show_text:
        icons_group.hidden = True
        jiggle_icon.hidden = True
        bottom_label.hidden = False
    else:
        bottom_label.hidden = True
        bottom_label.text = ""
        icons_group.hidden = False


def show_message(title, text, bottom=None):
    """Временное сообщение на экране."""
    set_centered_text(title_label, title)
    set_centered_text(pass_label, text)
    if bottom:
        set_bottom_mode(show_text=True)
        set_centered_text(bottom_label, bottom)
    else:
        set_bottom_mode(show_text=False)


# --- Клавиатура и мышь для компьютера ---
kbd = None
layout = None
mouse = None


def init_hid():
    global kbd, layout, mouse
    kbd = Keyboard(usb_hid.devices)
    layout = KeyboardLayoutUS(kbd)
    mouse = Mouse(usb_hid.devices)


def caps_lock_on():
    """Горит ли на компьютере Caps Lock (компьютер сообщает это всем клавиатурам)."""
    try:
        return kbd.led_on(Keyboard.LED_CAPS_LOCK)
    except Exception:
        return False


def caps_lock_off_for_typing():
    """Если Caps Lock включён — выключаем на время набора.
    Возвращает True, если выключали (после набора нужно включить обратно)."""
    if not caps_lock_on():
        return False
    kbd.send(Keycode.CAPS_LOCK)
    time.sleep(0.1)
    if caps_lock_on():
        # В Windows бывает настройка «Caps Lock выключается клавишей Shift»
        kbd.send(Keycode.SHIFT)
        time.sleep(0.1)
    if caps_lock_on():
        log("Caps Lock не удалось выключить перед набором P{}.".format(current_profile))
    return True


def send_keys(*keys):
    """Нажать и отпустить сочетание клавиш. Возвращает True, если компьютер принял."""
    try:
        kbd.send(*keys)
        return True
    except Exception as e:
        log_exception("отправка клавиш", e)
        return False


# =====================================================================
#  6. ДЕЙСТВИЯ
# =====================================================================

current_profile = 1
main_menu_index = 0       # 0-5 — профили, 6 — JIGGLE, 7 — SETTINGS
menu_index = 0            # пункт внутри меню
sleep_preset = SLEEP_DEFAULT_PRESET
sleep_style = 0           # 0 = Off (экран выключается)
screen_brightness = BRIGHTNESS_DEFAULT
layout_auto = True        # SETTINGS → Layout: Auto (переключать раскладку) / Off
led_brightness = BRIGHTNESS_DEFAULT
auto_enter_enabled = False
ctrl_first_enabled = False
gen_ru_enabled = False
mouse_jiggle_enabled = False
jiggle_preset = JIGGLE_DEFAULT_PRESET
last_mouse_jiggle_time = 0.0
next_mouse_jiggle_interval = 60.0
last_activity_time = 0.0
is_sleeping = False


def tick():
    """Фоновые дела, пока ждём кнопку: светодиод, Jiggle и анимация сна."""
    update_led()
    update_mouse_jiggle()
    update_sleep_animation()
    time.sleep(0.02)


def wait_all_released():
    while any_pressed():
        tick()


def apply_brightness():
    """Применяет выбранную яркость экрана и светодиода."""
    try:
        display.brightness = SCREEN_BRIGHTNESS[screen_brightness][1]
    except Exception:
        pass  # экран не поддерживает смену яркости — просто оставляем как есть
    pixel.brightness = LED_BRIGHTNESS[led_brightness][1]


def show_splash():
    """Заставка при включении: крупно «PassPuck» и версия.
    Пока она на экране, заранее загружаются буквы шрифта."""
    if SPLASH_TIME <= 0:
        preload_font_glyphs()
        return
    start = time.monotonic()
    group = displayio.Group(x=2)
    group.append(label.Label(terminalio.FONT, text="PassPuck", color=0xFFFFFF,
                             scale=2, x=(128 - 8 * 12) // 2, y=24))
    version = "v" + VERSION
    group.append(label.Label(terminalio.FONT, text=version, color=0xFFFFFF,
                             x=(128 - len(version) * 6) // 2, y=48))
    display.root_group = group
    preload_font_glyphs()
    rest = SPLASH_TIME - (time.monotonic() - start)
    if rest > 0:
        time.sleep(rest)
    display.root_group = splash


def seconds_label(s):
    """Секунды коротким текстом: 10s, 1m, 4m."""
    if s >= 60 and s % 60 == 0:
        return "{}m".format(s // 60)
    return "{}s".format(s)


def reset_jiggle_timer():
    """Отсчёт до следующего шевеления начинается заново."""
    global last_mouse_jiggle_time, next_mouse_jiggle_interval
    last_mouse_jiggle_time = time.monotonic()
    next_mouse_jiggle_interval = JIGGLE_PRESETS[jiggle_preset]


def update_mouse_jiggle():
    """Раз в интервал сдвигает курсор на 1 пиксель и сразу возвращает обратно,
    поэтому курсор остаётся на месте, а Windows видит движение мыши.
    Работает и во сне, но не в меню."""
    if not mouse_jiggle_enabled or in_menu:
        return
    if time.monotonic() - last_mouse_jiggle_time < next_mouse_jiggle_interval:
        return
    try:
        mouse.move(x=1)
        mouse.move(x=-1)
    except Exception:
        pass  # компьютер спит или не принимает — просто пропускаем шаг
    reset_jiggle_timer()


def get_current_password():
    return passwords.get(current_profile, "")


def type_password():
    """Набирает пароль текущего профиля. Сам пароль в журнал не пишется."""
    password = get_current_password()
    if not password:
        show_message(title_label.text, "No password!")
        time.sleep(1)
        return
    if not is_typable(password):
        show_message(title_label.text, "Bad chars in P{}".format(current_profile))
        log("Набор P{} отменён: в пароле недопустимые символы.".format(current_profile))
        time.sleep(1.5)
        return

    set_centered_text(pass_label, "Typing...")
    caps_restore = False
    try:
        if ctrl_first_enabled:
            # Одиночный Ctrl ничего не печатает, но убирает заставку (часы) экрана
            # блокировки Windows. Без этого первый символ пароля может потеряться.
            kbd.send(Keycode.LEFT_CONTROL)
            time.sleep(TYPING_START_DELAY)
        caps_restore = caps_lock_off_for_typing()
        if has_russian(password):
            # Пароль с русскими буквами: раскладка переключается автоматически
            # перед каждым куском русских или английских символов.
            current_lang = None
            for char in password:
                if char in DIGITS:
                    # цифры одинаковые в обеих раскладках — раскладку не трогаем
                    layout.write(char)
                    if TYPING_DELAY > 0:
                        time.sleep(TYPING_DELAY)
                    continue
                lang = char_lang(char)
                if lang != current_lang:
                    if layout_auto:
                        hotkey = LANG_RU_HOTKEY if lang == "ru" else LANG_EN_HOTKEY
                        kbd.send(*hotkey)
                        time.sleep(LANG_SWITCH_DELAY)
                    current_lang = lang
                if lang == "ru":
                    key, shift = RU_KEYMAP[char]
                    if shift:
                        kbd.send(Keycode.SHIFT, key)
                    else:
                        kbd.send(key)
                else:
                    layout.write(char)
                if TYPING_DELAY > 0:
                    time.sleep(TYPING_DELAY)
        else:
            # Пароль только из английских символов: сначала включаем английскую раскладку
            if layout_auto:
                kbd.send(*LANG_EN_HOTKEY)
                time.sleep(LANG_SWITCH_DELAY)
            for char in password:
                layout.write(char)
                if TYPING_DELAY > 0:
                    time.sleep(TYPING_DELAY)
        if auto_enter_enabled:
            kbd.send(Keycode.ENTER)
            time.sleep(0.05)
    except Exception as e:
        try:
            kbd.release_all()
        except Exception:
            pass
        log_exception("набор пароля P{}".format(current_profile), e)
        set_centered_text(pass_label, "Type ERROR")
        time.sleep(1.5)
        return
    finally:
        if caps_restore:
            # возвращаем Caps Lock как был
            try:
                kbd.send(Keycode.CAPS_LOCK)
            except Exception:
                pass
    flash_green()
    set_centered_text(pass_label, "Done!")
    time.sleep(0.5)


def show_password():
    """Показывает пароль на 4 секунды. Длинный пароль — в две строки.
    Без шрифта с кириллицей русские буквы показываются как «?»."""
    pw = screen_text(get_current_password() or "No password!")
    if len(pw) > 21:
        pass_label.y = 25
        pass_label.text = pw[:21] + "\n" + pw[21:42]
        pass_label.x = 2
    else:
        set_centered_text(pass_label, pw)
    set_bottom_mode(show_text=True)
    for seconds_left in range(4, 0, -1):
        set_centered_text(bottom_label, "Hiding in {}s...".format(seconds_left))
        t_start = time.monotonic()
        while time.monotonic() - t_start < 1.0:
            update_led()
            time.sleep(0.05)
    pass_label.y = 31


def ask_confirm(title, question, bottom="Back/Fwd = cancel"):
    """Спрашивает подтверждение: «Ввод» — да, «Назад»/«Вперёд» — нет. Через 15 с — нет."""
    show_message(title, question, bottom)
    wait_all_released()
    start = time.monotonic()
    while time.monotonic() - start < 15:
        if pressed(btn_enter):
            wait_all_released()
            return True
        if pressed(btn_back) or pressed(btn_fwd):
            wait_all_released()
            return False
        tick()
    return False


def gen_pass_flow():
    """Меню → Gen Pass: подтверждение, генерация, сохранение.
    Если сохранить не удалось, старый пароль остаётся (и в памяти, и в файле)."""
    global in_menu
    p = current_profile
    if p > 3:
        set_centered_text(pass_label, "Fixed Profile!")
        time.sleep(1)
        return
    if passwords_source is None:
        set_centered_text(pass_label, "Fix passwords.py")
        time.sleep(1.5)
        return
    if not FS_WRITABLE:
        set_centered_text(pass_label, "Edit mode: no save")
        time.sleep(1.5)
        return
    lang = "RU" if gen_ru_enabled else "EN"
    if not ask_confirm("Gen Pass P{} {}?".format(p, lang), "Enter = YES"):
        show_message("Gen Pass P{}".format(p), "Cancelled")
        time.sleep(0.7)
        return

    old = passwords[p]
    passwords[p] = generate_password(RU_GEN_CHARS if gen_ru_enabled else CHARS)
    show_message("Gen Pass P{}".format(p), "Saving...")
    error = save_passwords()
    if error:
        passwords[p] = old
        log("Gen Pass P{}: новый пароль НЕ сохранён, оставлен старый.".format(p))
        show_message("Gen Pass P{}".format(p), error, "Old pass kept")
        time.sleep(2.5)
    else:
        log("Gen Pass P{}: новый пароль сгенерирован и сохранён.".format(p))
        show_message("Gen Pass P{}".format(p), "Generated & Saved!")
        time.sleep(1)
        in_menu = False


def update_ui():
    """Перерисовывает главный экран или меню по текущему состоянию."""
    set_bottom_mode(show_text=False)
    on_jiggle = main_menu_index == JIGGLE_ITEM
    on_settings = main_menu_index == SETTINGS_ITEM
    jiggle_icon.hidden = in_menu or not mouse_jiggle_enabled

    if not in_menu:
        arrow_left.fill = center_circle.fill = arrow_right.fill = 0xFFFFFF
        if on_jiggle:
            set_centered_text(title_label, "=== JIGGLE ===")
            set_centered_text(pass_label, "Jiggle {} | {}".format(
                "ON" if mouse_jiggle_enabled else "OFF",
                seconds_label(JIGGLE_PRESETS[jiggle_preset])))
        elif on_settings:
            set_centered_text(title_label, "=== SETTINGS ===")
            set_centered_text(pass_label, "Sleep {} | {}".format(
                sleep_preset_label(), SLEEP_STYLES[sleep_style]))
        else:
            prof_type = "Auto" if current_profile <= 3 else "Manual"
            set_centered_text(title_label, "Prof {}/{} [{}]".format(current_profile, TOTAL_PROFILES, prof_type))
            set_centered_text(pass_label, profile_names.get(current_profile, "Profile {}".format(current_profile)))
    else:
        arrow_left.fill = center_circle.fill = arrow_right.fill = 0x000000
        if on_jiggle:
            set_centered_text(title_label, "=== JIGGLE ===")
            items = [
                "Every: " + seconds_label(JIGGLE_PRESETS[jiggle_preset]),
                "Exit",
            ]
        elif on_settings:
            set_centered_text(title_label, "=== SETTINGS ===")
            items = [
                "Sleep: " + sleep_preset_label(),
                "Style: " + SLEEP_STYLES[sleep_style],
                "Screen: " + SCREEN_BRIGHTNESS[screen_brightness][0],
                "LED: " + LED_BRIGHTNESS[led_brightness][0],
                "Layout: " + ("Auto" if layout_auto else "Off"),
                "Preview",
                "Edit mode" if FS_WRITABLE else "Exit edit mode",
                "Exit",
            ]
        else:
            set_centered_text(title_label, "=== MENU (P{}) ===".format(current_profile))
            items = [
                "1.Gen Pass",
                "2.Show Pass",
                "3.Enter: " + ("ON" if auto_enter_enabled else "OFF"),
                "4.Ctrl first: " + ("ON" if ctrl_first_enabled else "OFF"),
                "5.Gen: " + (("RU" if gen_ru_enabled else "EN") if current_profile <= 3 else "-"),
                "6.Exit",
            ]
        pass_label.x = 5
        pass_label.y = 31
        pass_label.text = "> " + items[menu_index]


def sleep_preset_label():
    """Текущее время сна текстом: 15s, 1m, Never..."""
    s = SLEEP_PRESETS[sleep_preset]
    if s == 0:
        return "Never"
    if s >= 60 and s % 60 == 0:
        return "{}m".format(s // 60)
    return "{}s".format(s)


def wake_up():
    """Любое нажатие: включить экран, если он спит, и сбросить таймер сна."""
    global is_sleeping, last_activity_time
    if is_sleeping:
        try:
            display.wake()          # включаем экран обратно (если он был выключен)
        except Exception:
            pass
        display.root_group = splash
        is_sleeping = False
    last_activity_time = time.monotonic()


def go_to_sleep(preview=False):
    """Сон: стиль Off — экран выключается; иначе включается выбранная анимация.
    Обычный сон после пробуждения возвращает на главный экран профиля.
    Preview (из SETTINGS) возвращает туда же, где были — в меню на строку Preview."""
    global is_sleeping, in_menu, menu_index, main_menu_index
    is_sleeping = True
    if not preview:
        in_menu = False
        menu_index = 0
        main_menu_index = current_profile - 1
        update_ui()                 # после пробуждения будет главный экран
    if sleep_style == 0:
        display.root_group = empty_splash
        try:
            display.sleep()
        except Exception:
            pass  # не получилось — экран всё равно чёрный
    else:
        start_sleep_animation()


def check_sleep():
    """Засыпаем, если долго не нажимали кнопки (время выбирается в SETTINGS)."""
    timeout = SLEEP_PRESETS[sleep_preset]
    if timeout and not is_sleeping and time.monotonic() - last_activity_time > timeout:
        go_to_sleep()


# --- Анимации сна: рисуются на отдельной картинке 128x64, пока устройство «спит» ---
ANIM_W = 128
ANIM_H = 64
anim_group = None
anim_bitmap = None
anim_logo = None
anim_items = []           # звёзды или капли
anim_next_frame = 0.0
anim_dx = 1
anim_dy = 1


def init_sleep_animations():
    global anim_group, anim_bitmap, anim_logo
    anim_bitmap = displayio.Bitmap(ANIM_W, ANIM_H, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000
    palette[1] = 0xFFFFFF
    anim_group = displayio.Group(x=2)
    anim_group.append(displayio.TileGrid(anim_bitmap, pixel_shader=palette))
    anim_logo = label.Label(terminalio.FONT, text="PassPuck", color=0xFFFFFF, x=40, y=30)
    anim_group.append(anim_logo)


def new_star():
    """Звезда вылетает из центра в случайном направлении: [x, y, скорость_x, скорость_y]."""
    angle = random.uniform(0, 6.283)
    speed = random.uniform(0.4, 1.2)
    return [64.0, 32.0, math.cos(angle) * speed, math.sin(angle) * speed]


def new_drop(y=0):
    """Капля дождя: [x, y, скорость, длина]."""
    return [random.randrange(ANIM_W), y, random.randrange(1, 3), random.randrange(3, 9)]


def start_sleep_animation():
    global anim_items, anim_next_frame
    anim_bitmap.fill(0)
    style = SLEEP_STYLES[sleep_style]
    anim_logo.hidden = style != "Bounce"
    anim_items = []
    if style == "Stars":
        anim_items = [new_star() for _ in range(24)]
    elif style == "Rain":
        anim_items = [new_drop(random.randrange(ANIM_H)) for _ in range(14)]
    elif style == "Bounce":
        anim_logo.x = random.randrange(0, ANIM_W - 48)
        anim_logo.y = random.randrange(8, ANIM_H - 8)
    anim_next_frame = 0.0
    display.root_group = anim_group


def update_sleep_animation():
    """Один кадр анимации (вызывается постоянно из tick, рисует не чаще ANIMATION_FRAME_TIME)."""
    global anim_next_frame, anim_dx, anim_dy
    if not is_sleeping or sleep_style == 0:
        return
    now = time.monotonic()
    if now < anim_next_frame:
        return
    anim_next_frame = now + ANIMATION_FRAME_TIME
    style = SLEEP_STYLES[sleep_style]

    if style == "Stars":
        for i in range(len(anim_items)):
            s = anim_items[i]
            x, y = int(s[0]), int(s[1])
            if 0 <= x < ANIM_W and 0 <= y < ANIM_H:
                anim_bitmap[x, y] = 0              # стираем звезду на старом месте
            s[0] += s[2]
            s[1] += s[3]
            s[2] *= 1.07                           # разгоняется к краю экрана
            s[3] *= 1.07
            x, y = int(s[0]), int(s[1])
            if 0 <= x < ANIM_W and 0 <= y < ANIM_H:
                anim_bitmap[x, y] = 1
            else:
                anim_items[i] = new_star()         # улетела за край — новая из центра

    elif style == "Rain":
        for i in range(len(anim_items)):
            d = anim_items[i]
            for _ in range(d[2]):
                tail = d[1] - d[3]
                if 0 <= tail < ANIM_H:
                    anim_bitmap[d[0], tail] = 0    # стираем хвост капли
                d[1] += 1
                if 0 <= d[1] < ANIM_H:
                    anim_bitmap[d[0], d[1]] = 1    # рисуем голову
            if d[1] - d[3] >= ANIM_H:
                anim_items[i] = new_drop()         # упала — новая сверху

    elif style == "Bounce":
        anim_logo.x += anim_dx
        anim_logo.y += anim_dy
        if anim_logo.x <= 0 or anim_logo.x >= ANIM_W - 48:
            anim_dx = -anim_dx
        if anim_logo.y <= 6 or anim_logo.y >= ANIM_H - 7:
            anim_dy = -anim_dy


# =====================================================================
#  7. ГЛАВНЫЙ ЦИКЛ — обработка нажатий
# =====================================================================

def handle_lock_combo():
    """«Назад»+«Вперёд»: если обе держать NAV_LOCK_HOLD_TIME — Win+L.
    Ждём, пока отпустят обе кнопки; обычные действия кнопок при этом не выполняются."""
    both_since = None
    sent = False
    while pressed(btn_back) or pressed(btn_fwd):
        if pressed(btn_back) and pressed(btn_fwd):
            if both_since is None:
                both_since = time.monotonic()
            if not sent and time.monotonic() - both_since >= NAV_LOCK_HOLD_TIME:
                send_keys(Keycode.WINDOWS, Keycode.L)
                sent = True
        tick()


def nav_press(btn, other, step):
    """«Назад» / «Вперёд»: листаем, когда кнопку ОТПУСТИЛИ.
    Если, пока кнопка зажата, нажали вторую — это комбинация блокировки (Win+L),
    и листание не выполняется."""
    while pressed(btn):
        if pressed(other):
            handle_lock_combo()
            return
        tick()
    navigate(step)
    time.sleep(BUTTON_DEBOUNCE)


def wait_enter():
    """Ждём «Ввод»: возвращает "long", как только прошло LONG_PRESS_TIME, иначе "short" при отпускании."""
    start = time.monotonic()
    while pressed(btn_enter):
        if time.monotonic() - start >= LONG_PRESS_TIME:
            return "long"
        tick()
    return "short"


def navigate(step):
    """«Вперёд» (+1) или «Назад» (-1): листаем профили или пункты меню."""
    global main_menu_index, menu_index, current_profile, auto_enter_enabled
    global ctrl_first_enabled, gen_ru_enabled
    if in_menu:
        if main_menu_index == JIGGLE_ITEM:
            count = 2
        elif main_menu_index == SETTINGS_ITEM:
            count = 8
        else:
            count = 6
        menu_index = (menu_index + step) % count
    else:
        main_menu_index = (main_menu_index + step) % MAIN_MENU_ITEMS
        if main_menu_index < TOTAL_PROFILES:
            current_profile = main_menu_index + 1
            auto_enter_enabled = load_auto_enter(current_profile)
            ctrl_first_enabled = load_ctrl_first(current_profile)
            gen_ru_enabled = load_gen_ru(current_profile)
    update_ui()


def on_enter(press):
    """«Ввод» коротко ("short") или долго ("long")."""
    global in_menu, menu_index, mouse_jiggle_enabled
    global jiggle_preset
    global auto_enter_enabled, ctrl_first_enabled, sleep_preset, sleep_style
    global screen_brightness, led_brightness, gen_ru_enabled, layout_auto
    on_jiggle = main_menu_index == JIGGLE_ITEM
    on_settings = main_menu_index == SETTINGS_ITEM

    # ---------- главный экран ----------
    if not in_menu:
        if press == "long" or on_settings:          # SETTINGS открывается любым нажатием
            in_menu = True
            menu_index = 0
            update_ui()
            update_led()
        elif on_jiggle:
            mouse_jiggle_enabled = not mouse_jiggle_enabled
            save_jiggle_enabled(mouse_jiggle_enabled)
            log("Jiggle: " + ("ON" if mouse_jiggle_enabled else "OFF"))
            reset_jiggle_timer()
            set_centered_text(pass_label, "Mouse: " + ("ON" if mouse_jiggle_enabled else "OFF"))
            time.sleep(0.7)
            update_ui()
        else:
            type_password()
            update_ui()
        return

    # ---------- меню JIGGLE: Every / Exit ----------
    if on_jiggle:
        if press == "long" or menu_index == 1:
            in_menu = False
        elif menu_index == 0:
            jiggle_preset = (jiggle_preset + 1) % len(JIGGLE_PRESETS)
            save_jiggle_preset(jiggle_preset)
            log("Jiggle: каждые " + seconds_label(JIGGLE_PRESETS[jiggle_preset]))
            reset_jiggle_timer()
        update_ui()
        update_led()
        return

    # ---------- меню SETTINGS: Sleep / Style / Screen / LED / Preview / Exit ----------
    if on_settings:
        if press == "long" or menu_index == 7:
            in_menu = False
        elif menu_index == 0:
            sleep_preset = (sleep_preset + 1) % len(SLEEP_PRESETS)
            save_sleep_settings(sleep_preset, sleep_style)
            log("Сон: через " + sleep_preset_label())
        elif menu_index == 1:
            sleep_style = (sleep_style + 1) % len(SLEEP_STYLES)
            save_sleep_settings(sleep_preset, sleep_style)
            log("Сон: стиль " + SLEEP_STYLES[sleep_style])
        elif menu_index == 2:
            screen_brightness = (screen_brightness + 1) % len(SCREEN_BRIGHTNESS)
            save_brightness(screen_brightness, led_brightness)
            apply_brightness()
            log("Яркость экрана: " + SCREEN_BRIGHTNESS[screen_brightness][0])
        elif menu_index == 3:
            led_brightness = (led_brightness + 1) % len(LED_BRIGHTNESS)
            save_brightness(screen_brightness, led_brightness)
            apply_brightness()
            log("Яркость светодиода: " + LED_BRIGHTNESS[led_brightness][0])
        elif menu_index == 4:
            layout_auto = not layout_auto
            save_layout_auto(layout_auto)
            log("Раскладка: " + ("Auto" if layout_auto else "Off"))
        elif menu_index == 5:
            go_to_sleep(preview=True)               # Preview: уснуть прямо сейчас
            return
        elif menu_index == 6:
            edit_mode_flow()                        # Edit mode / Exit edit mode
        update_ui()
        update_led()
        return

    # ---------- меню профиля ----------
    if press == "long" or menu_index == 5:          # долгое нажатие или «6.Exit»
        in_menu = False
    elif menu_index == 0:                           # 1.Gen Pass
        gen_pass_flow()
    elif menu_index == 1:                           # 2.Show Pass
        show_password()
    elif menu_index == 2:                           # 3.Enter: ON/OFF
        auto_enter_enabled = not auto_enter_enabled
        save_auto_enter(current_profile, auto_enter_enabled)
        log("P{}: Enter -> {}".format(current_profile, "ON" if auto_enter_enabled else "OFF"))
    elif menu_index == 3:                           # 4.Ctrl first: ON/OFF
        ctrl_first_enabled = not ctrl_first_enabled
        save_ctrl_first(current_profile, ctrl_first_enabled)
        log("P{}: Ctrl first -> {}".format(current_profile, "ON" if ctrl_first_enabled else "OFF"))
    elif menu_index == 4:                           # 5.Gen: EN/RU
        if current_profile > 3:
            set_centered_text(pass_label, "Fixed Profile!")
            time.sleep(1)
        else:
            gen_ru_enabled = not gen_ru_enabled
            save_gen_ru(current_profile, gen_ru_enabled)
            log("P{}: Gen -> {}".format(current_profile, "RU" if gen_ru_enabled else "EN"))
    update_ui()
    update_led()


def edit_mode_flow():
    """SETTINGS → Edit mode: перезапуск с открытым диском CIRCUITPY.
    В режиме редактирования тот же пункт (Exit edit mode) перезапускает в обычный режим."""
    if FS_WRITABLE:
        if not ask_confirm("Edit mode?", "Restart with disk", "Enter=YES Back=NO"):
            return
        request_edit_mode()
        log("Переход в режим редактирования из меню.")
    else:
        # Компьютер мог ещё не дописать файлы на флешку — предупреждаем
        if not ask_confirm("Exit edit mode?", "Wait 10s after save", "Enter=YES Back=NO"):
            return
    show_message("PassPuck", "Restarting...")
    time.sleep(0.5)
    microcontroller.reset()


def main_loop():
    while True:
        tick()
        if not any_pressed():
            check_sleep()
            continue

        # Экран погас: первое нажатие только будит его
        if is_sleeping:
            wake_up()
            wait_all_released()
            continue
        wake_up()

        if pressed(btn_back) and pressed(btn_fwd):
            handle_lock_combo()
        elif pressed(btn_fwd):
            nav_press(btn_fwd, btn_back, +1)
        elif pressed(btn_back):
            nav_press(btn_back, btn_fwd, -1)
        elif pressed(btn_enter):
            on_enter(wait_enter())
            wait_all_released()
            time.sleep(0.1)


# =====================================================================
#  8. ЗАПУСК И АВАРИЙНЫЙ ЭКРАН
# =====================================================================

def startup():
    global boot_number, auto_enter_enabled, ctrl_first_enabled, sleep_preset, sleep_style
    global mouse_jiggle_enabled
    global jiggle_preset, last_activity_time, screen_brightness, led_brightness
    global gen_ru_enabled, layout_auto

    nvm_prepare()
    boot_number = nvm_next_boot_number()
    reason = str(microcontroller.cpu.reset_reason).split(".")[-1]
    mode = "обычный" if FS_WRITABLE else "редактирование (запись на флешку выключена)"
    log("===== Включение. PassPuck v{} | причина: {} | режим: {} =====".format(VERSION, reason, mode))
    if HARDWARE_PINS_USED:
        log("Кнопки: используются контакты из hardware_pins.py")

    load_passwords()
    init_display()
    screen_brightness, led_brightness = load_brightness()
    layout_auto = load_layout_auto()
    apply_brightness()
    show_splash()
    init_hid()

    auto_enter_enabled = load_auto_enter(current_profile)
    ctrl_first_enabled = load_ctrl_first(current_profile)
    gen_ru_enabled = load_gen_ru(current_profile)
    mouse_jiggle_enabled = load_jiggle_enabled()
    sleep_preset, sleep_style = load_sleep_settings()
    jiggle_preset = load_jiggle_preset()
    reset_jiggle_timer()
    last_activity_time = time.monotonic()

    try:
        import gc
        gc.collect()
        print("Свободно памяти: {} байт".format(gc.mem_free()))
    except Exception:
        pass

    # Предупреждение о проблемах с паролями — 3 секунды при включении
    if passwords_source is None:
        show_message("! PASSWORDS !", "passwords.py ERROR", "see log.txt")
        time.sleep(3)
    elif passwords_source != PASSWORDS_FILE:
        show_message("! PASSWORDS !", "Backup loaded", "see log.txt")
        time.sleep(3)
    update_ui()


def fatal_error(e):
    """Непредвиденная ошибка: пишем в журнал, показываем на экране,
    мигаем красным и ждём любую кнопку для перезапуска."""
    log_exception("работа программы", e)
    try:
        if display is not None:
            try:
                display.wake()
            except Exception:
                pass
            display.root_group = splash
            show_message("!!! ERROR !!!", type(e).__name__, "log.txt | any btn")
    except Exception:
        pass
    try:
        kbd.release_all()
    except Exception:
        pass
    pixel.brightness = 1.0          # аварийное мигание всегда на полной яркости
    wait_start = time.monotonic()
    while True:
        on = int(time.monotonic() * 2) % 2 == 0
        pixel[0] = (255, 0, 0) if on else (0, 0, 0)
        # первые 2 секунды игнорируем кнопки, чтобы случайно не перезапуститься сразу
        if time.monotonic() - wait_start > 2 and any_pressed():
            supervisor.reload()
        time.sleep(0.05)


# Обычный запуск. (Если программу подключают из консоли командой «import code»
# для проверки — главный цикл не запускается.)
if __name__ != "code":
    try:
        startup()
        main_loop()
    except Exception as e:
        fatal_error(e)
