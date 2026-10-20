# =====================================================================
#  PassPuck — карманный менеджер паролей на RP2040-Zero (CircuitPython)
#  Версия 2.1
#
#  Это исходник программы. На устройство кладётся собранный из него
#  passpuck.mpy (сборка: tools/build.ps1), а запускает его маленький code.py.
#  Настройки меняются в settings.py на устройстве, а не здесь.
#
#  Файл разбит на разделы:
#    1. Настройки по умолчанию (их заменяют значения из settings.py)
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
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_display_text import label
from adafruit_display_shapes.line import Line
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.roundrect import RoundRect
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.triangle import Triangle


# =====================================================================
#  1. НАСТРОЙКИ ПО УМОЛЧАНИЮ
#  Менять их нужно в settings.py на устройстве: значения оттуда заменяют эти.
#  Если какой-то строки в settings.py нет — используется значение отсюда.
# =====================================================================

VERSION = "2.3"

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
# Вид пароля выбирается для каждого профиля в его меню (пункт «Gen»):
#   EN    — случайные символы из CHARS;
#   RU    — случайные русские буквы и цифры;
#   Words — запоминаемый: два русских слова из WORDS_FILE, набранные в английской
#           раскладке, плюс 2 цифры и символ. Например, «Кот Луна 47!» вводится как RjnKeyf47!
#   Words RU — те же слова русскими буквами: КотЛуна47!
PASSWORD_LENGTH = 12      # длина нового пароля EN и RU
CHARS ="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-="
WORDS_FILE = "/words.txt" # словарь для Words: одно слово на строке
WORDS_SYMBOLS = "!#$%&*?@" # из них выбирается символ в конце пароля Words
WORDS_RU_SYMBOLS = "!%*+-=" # ... и Words RU (эти символы одинаковы в обеих раскладках)

# Сон экрана. Выбирается прямо на устройстве: пункт SETTINGS на главном экране.
SLEEP_PRESETS = (15, 30, 60, 120, 300, 0)   # варианты «Sleep», секунды. 0 = никогда
                                            # (экран горит всегда — OLED со временем может выгорать)
SLEEP_DEFAULT_PRESET = 1                    # по умолчанию 30 с (номер в списке выше, считая с нуля)
# Off — экран выключается, остальное — анимации. Mix — анимации меняются сами.
SLEEP_STYLES = ("Off", "Stars", "Bounce", "Rain", "Eyes", "Fireworks",
                "Snake", "Matrix", "Pulse", "Warp", "Snow", "Lock", "Mix")
ANIMATION_FRAME_TIME = 0.05                 # скорость анимации: пауза между кадрами, сек
MIX_PERIOD = 120                            # Mix: сколько секунд показывать каждую анимацию

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
NAV_REPEAT_DELAY = 0.5    # держите «Назад» или «Вперёд» дольше — листает само
NAV_REPEAT_INTERVAL = 0.25  # ... с такой паузой между шагами, сек
MEDIA_VOLUME_INTERVAL = 0.1 # пульт MEDIA: держите «Вперёд»/«Назад» — громкость меняется с таким шагом, сек

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
I2C_FREQUENCY = 400000    # скорость связи с экраном. Если экран сбоит — поставьте 100000
BUTTON_DEBOUNCE = 0.03    # защита от дребезга кнопок, сек

# --- Настройки из settings.py заменяют значения по умолчанию выше ---
# Берутся все имена из ЗАГЛАВНЫХ букв. Если файла нет или он сломан — остаются умолчания.
SETTINGS_STATUS = "по умолчанию (settings.py нет)"
try:
    import settings as _settings
    for _name in dir(_settings):
        if _name.isupper():
            globals()[_name] = getattr(_settings, _name)
    SETTINGS_STATUS = "из settings.py"
except ImportError:
    pass
except Exception as _e:
    SETTINGS_STATUS = "по умолчанию: settings.py не читается ({})".format(repr(_e))

# --- Особенности конкретного устройства: hardware_pins.py (применяется последним) ---
# Если на конкретном устройстве кнопки припаяны к другим контактам, положите рядом
# hardware_pins.py, например:
#     import board
#     PIN_ENTER = board.GP8
#     PIN_FWD = board.GP7
HARDWARE_PINS_USED = False
try:
    import hardware_pins as _hw
    PIN_BACK = getattr(_hw, "PIN_BACK", PIN_BACK)
    PIN_ENTER = getattr(_hw, "PIN_ENTER", PIN_ENTER)
    PIN_FWD = getattr(_hw, "PIN_FWD", PIN_FWD)
    HARDWARE_PINS_USED = True
except ImportError:
    pass

# --- ниже этой линии менять без необходимости не стоит ---

TOTAL_PROFILES = 6
MEDIA_ITEM = TOTAL_PROFILES            # 7-й пункт главного экрана — MEDIA (пульт для музыки)
JIGGLE_ITEM = TOTAL_PROFILES + 1       # 8-й — JIGGLE
SETTINGS_ITEM = TOTAL_PROFILES + 2     # 9-й — SETTINGS
MAIN_MENU_ITEMS = TOTAL_PROFILES + 3


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

# Виды пароля для Gen Pass (номер хранится в памяти настроек, см. NVM_GEN_MODE)
GEN_MODES = ("EN", "RU", "Words", "Words RU")
GEN_WORDS = 2             # номера видов «из слов» в GEN_MODES
GEN_WORDS_RU = 3
# Цифры и эти символы стоят на одних и тех же клавишах в русской и английской
# раскладке — для них раскладку не переключаем
LAYOUT_NEUTRAL = "0123456789!%*()_-+= "
# Words: русская буква → английская буква на той же клавише (й → q, ц → w, ...).
# Только буквы, которые и в английской раскладке буквы (без х ъ ж э б ю ё).
_WORD_LETTERS = "йцукенгшщзфывапролдячсмить"
_WORD_KEYS = "qwertyuiopasdfghjklzxcvbnm"
WORDS_MIN = 100           # меньше слов в словаре — пароль слишком лёгкий, не генерируем


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


def random_below(n):
    """Случайное число от 0 до n-1 (n не больше 65536), все с равной вероятностью."""
    limit = 65536 - (65536 % n)
    while True:
        b = os.urandom(2)
        v = (b[0] << 8) | b[1]
        if v < limit:
            return v % n


def is_word(text):
    """Подходит ли строка словаря: 3 или 4 русские буквы из _WORD_LETTERS
    (короткие слова — пароль легче запомнить)."""
    if not 3 <= len(text) <= 4:
        return False
    for c in text:
        if c not in _WORD_LETTERS:
            return False
    return True


def dictionary_words():
    """Слова словаря по одному. Весь файл в память не загружается.
    Неподходящие строки (комментарии, длинные слова, буквы ж х ъ э б ю ё) пропускаются."""
    with open(WORDS_FILE, "r") as f:
        for line in f:
            w = line.strip()
            if is_word(w):
                yield w


_words_count = None       # сколько слов в словаре (считается один раз)


def words_count():
    global _words_count
    if _words_count is None:
        n = 0
        for _ in dictionary_words():
            n += 1
        _words_count = n
    return _words_count


def word_to_keys(word):
    """«кот» → «Rjn»: те же клавиши в английской раскладке, первая буква заглавная."""
    keys = "".join(_WORD_KEYS[_WORD_LETTERS.index(c)] for c in word)
    return keys[0].upper() + keys[1:]


def word_title_ru(word):
    """«кот» → «Кот» (upper() в CircuitPython не знает кириллицу)."""
    return _RU_LETTERS_UPPER[_RU_LETTERS.index(word[0])] + word[1:]


def generate_words_password(russian=False):
    """Пароль из двух разных случайных слов, 2 цифр и символа.
    Words: «Кот Луна 47!» → RjnKeyf47!   Words RU (russian=True): КотЛуна47!
    None — словаря нет или в нём меньше WORDS_MIN слов."""
    try:
        total = words_count()
    except OSError:
        total = 0
    if total < WORDS_MIN:
        return None
    a = random_below(total)
    b = random_below(total - 1)
    if b >= a:
        b += 1                # второе слово всегда другое
    picked = {}
    for i, w in enumerate(dictionary_words()):
        if i == a or i == b:
            picked[i] = w
    digits = DIGITS[random_below(10)] + DIGITS[random_below(10)]
    symbols = WORDS_RU_SYMBOLS if russian else WORDS_SYMBOLS
    symbol = symbols[random_below(len(symbols))]
    convert = word_title_ru if russian else word_to_keys
    return convert(picked[a]) + convert(picked[b]) + digits + symbol


def words_hint(pw):
    """Подсказка для запоминания пароля из слов: «RjnKeyf47!» → «Кот Луна 47!».
    None — пароль не из слов словаря (обычный случайный, введённый вручную и т.п.)."""
    parts = []
    i = 0
    while i < len(pw) and "A" <= pw[i] <= "Z":
        j = i + 1
        while j < len(pw) and "a" <= pw[j] <= "z":
            j += 1
        parts.append(pw[i:j].lower())
        i = j
    tail = pw[i:]
    if len(parts) < 2 or any(c.isalpha() for c in tail):
        return None
    words = []
    for part in parts:
        w = ""
        for c in part:
            k = _WORD_KEYS.find(c)
            if k < 0:
                return None
            w += _WORD_LETTERS[k]
        words.append(w)
    missing = set(words)
    try:
        for w in dictionary_words():
            missing.discard(w)
    except OSError:
        return None
    if missing:
        return None
    return " ".join(word_title_ru(w) for w in words) + (" " + tail if tail else "")


# =====================================================================
#  4. ПАМЯТЬ НАСТРОЕК (NVM) — не стирается при отключении и перепрошивке файлов
#  Байты 0-3: метка "PWD6" (память размечена)
#  Байты 4-15: по 2 байта на профиль: Auto Enter и запасной байт
#              (раньше там был Shift+1, теперь не используется)  (P1: 4-5, ... P6: 14-15)
#  Байт 16: Jiggle, байт 17: последний профиль (с него начинается работа после включения)
#  Байты 18-19: счётчик включений (для журнала)
#  Байты 20-25: «Ctrl first» по профилям (P1: 20, ... P6: 25)
#  Байт 26: через сколько засыпать (номер в SLEEP_PRESETS), байт 27: стиль сна
#  Байт 28: как часто Jiggle (номер в JIGGLE_PRESETS)
#  Байт 29: яркость экрана, байт 30: яркость светодиода (номера в списках яркости)
#  Байты 31-36: вид пароля Gen Pass по профилям (0 = EN, 1 = RU, 2 = Words)  (P1: 31, ... P6: 36)
#  Байт 38: переключение раскладки (1 = Off, иначе Auto)
#  Байт 37: одноразовая отметка «следующее включение — режим редактирования»
#           (ставит пункт SETTINGS → Edit mode, стирает boot.py)
#  Байт 39: первая настройка через редактор пропущена (SETTINGS → Exit edit mode
#           на новом устройстве) — boot.py больше не открывает диск сам
#  Байт 40: пульт MEDIA включён (SETTINGS → Media: On)
#  Значение 1 = включено, всё остальное = выключено.
# =====================================================================

nvm = microcontroller.nvm
NVM_MAGIC = b"PWD6"
NVM_USED = 39
NVM_JIGGLE = 16
NVM_LAST_PROFILE = 17
NVM_BOOT_COUNTER = 18
NVM_CTRL_FIRST = 20
NVM_SLEEP_PRESET = 26
NVM_SLEEP_STYLE = 27
NVM_JIGGLE_PRESET = 28
NVM_SCREEN_BRIGHTNESS = 29
NVM_LED_BRIGHTNESS = 30
NVM_GEN_MODE = 31
NVM_EDIT_FLAG = 37        # если менять — поменяйте и в boot.py
EDIT_FLAG_VALUE = 0xA5
NVM_LAYOUT_OFF = 38
NVM_SETUP_SKIPPED = 39    # если менять — поменяйте и в boot.py
NVM_MEDIA_ON = 40


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


def load_last_profile():
    p = nvm[NVM_LAST_PROFILE]
    return p if 1 <= p <= TOTAL_PROFILES else 1


def remember_profile():
    """Запоминает текущий профиль, чтобы после включения начать с него.
    Пишем, только если он изменился: частая перезапись изнашивает память настроек,
    поэтому вызывается не при каждом листании, а при наборе пароля и засыпании."""
    if nvm[NVM_LAST_PROFILE] != current_profile:
        nvm[NVM_LAST_PROFILE] = current_profile


def load_gen_mode(profile):
    """Какой пароль генерировать для профиля: номер в GEN_MODES (0 = EN)."""
    mode = nvm[NVM_GEN_MODE + profile - 1]
    return mode if mode < len(GEN_MODES) else 0


def save_gen_mode(profile, mode):
    nvm[NVM_GEN_MODE + profile - 1] = mode


def load_layout_auto():
    """Переключать ли раскладку Windows автоматически (Ctrl+Shift+1 / Ctrl+Shift+2)."""
    return nvm[NVM_LAYOUT_OFF] != 1


def save_layout_auto(enabled):
    nvm[NVM_LAYOUT_OFF] = 0 if enabled else 1


def load_media_enabled():
    """Показывать ли пульт MEDIA (SETTINGS → Media). По умолчанию выключен."""
    return nvm[NVM_MEDIA_ON] == 1


def save_media_enabled(enabled):
    nvm[NVM_MEDIA_ON] = 1 if enabled else 0


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
icons_group = None        # нижняя строка: точки «где я» (6 профилей, JIGGLE, SETTINGS)
nav_dots = []
badge_enter = None        # значки в верхней строке профиля: ENT, CTL и вид Gen
badge_ctrl = None
gen_badge = None
bottom_line = None        # линия над нижней строкой (в меню-списке убирается)
menu_group = None         # меню списком: см. init_display и draw_menu
menu_highlight = None
menu_names = []
menu_values = []
menu_scroll = None
menu_scroll_track = None
menu_counter = None
MENU_ROWS = 4             # сколько строк меню видно сразу
MENU_ROW_W = 121          # ширина строки (справа — полоска прокрутки)
MENU_THUMB = 10           # высота бегунка полоски прокрутки
menu_memory = {}          # на каком пункте закрыли каждое меню (до выключения)
media_icons = None        # значки пульта MEDIA
jiggle_icon = None


CYRILLIC_FONT_LOADED = False
main_font = terminalio.FONT


_font_tried = False


def load_main_font():
    """Загружает шрифт с кириллицей — один раз, когда на экране впервые нужна русская буква.
    Без него устройство работает, но русские буквы на экране будут «?»."""
    global main_font, CYRILLIC_FONT_LOADED, _font_tried
    if _font_tried:
        return CYRILLIC_FONT_LOADED
    _font_tried = True
    try:
        from adafruit_bitmap_font import bitmap_font
        main_font = bitmap_font.load_font(FONT_FILE)
        CYRILLIC_FONT_LOADED = True
    except Exception as e:
        main_font = terminalio.FONT
        CYRILLIC_FONT_LOADED = False
        log("Шрифт {} не загружен ({}). Русские буквы на экране будут «?».".format(FONT_FILE, repr(e)))
    return CYRILLIC_FONT_LOADED


class MiddleLine:
    """Средняя строка экрана (названия, пароли, меню).
    Текст латиницей выводится встроенным шрифтом платы — он не тратит оперативную память.
    Строки с русскими буквами — шрифтом с кириллицей, причём из файла шрифта загружаются
    только буквы этой строки (загруженные запоминаются). Снаружи работает как обычная
    надпись: text, x, y."""

    def __init__(self, group):
        self.group = group
        self.ascii = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=5, y=31)
        group.append(self.ascii)
        self.cyr = None                    # создаётся при первой русской букве
        self._active = self.ascii

    def _cyr_label(self):
        if self.cyr is None and load_main_font():
            self.cyr = label.Label(main_font, text="", color=0xFFFFFF,
                                   x=self.ascii.x, y=self.ascii.y, scale=self.ascii.scale)
            self.cyr.hidden = True
            self.group.append(self.cyr)
        return self.cyr

    @property
    def text(self):
        return self._active.text

    @text.setter
    def text(self, value):
        target = self.ascii
        if any(ord(c) > 126 for c in value):
            if self._cyr_label() is not None:
                try:
                    main_font.load_glyphs(value)   # только недостающие буквы этой строки
                    target = self.cyr
                except Exception as e:
                    log_exception("загрузка букв шрифта", e)
            if target is self.ascii:              # шрифта нет — русские буквы как «?»
                value = "".join(c if ord(c) <= 126 else "?" for c in value)
        if target is not self._active:
            target.x = self._active.x
            target.y = self._active.y
            self._active.text = ""
            self._active.hidden = True
            target.hidden = False
            self._active = target
        target.text = value

    @property
    def x(self):
        return self._active.x

    @x.setter
    def x(self, value):
        self.ascii.x = value
        if self.cyr is not None:
            self.cyr.x = value

    @property
    def y(self):
        return self._active.y

    @y.setter
    def y(self, value):
        self.ascii.y = value
        if self.cyr is not None:
            self.cyr.y = value

    @property
    def scale(self):
        return self.ascii.scale

    @scale.setter
    def scale(self, value):
        # Меняем только если отличается: смена размера перерисовывает надпись
        if self.ascii.scale != value:
            self.ascii.scale = value
        if self.cyr is not None and self.cyr.scale != value:
            self.cyr.scale = value


def init_display():
    """Запускает экран и рисует интерфейс. Ошибки здесь обычно значат проблему с проводами экрана."""
    global display, splash, empty_splash, title_label, pass_label, bottom_label
    global icons_group, nav_dots, badge_enter, badge_ctrl, gen_badge, jiggle_icon
    global bottom_line, menu_group, menu_highlight, menu_names, menu_values
    global menu_scroll, menu_scroll_track, menu_counter, media_icons

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

    splash = displayio.Group(x=2)
    empty_splash = displayio.Group(x=2)
    display.root_group = splash

    title_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=5, y=6)
    splash.append(title_label)
    splash.append(Line(0, 14, 128, 14, color=0xFFFFFF))
    # Средняя строка (названия, пароли, меню): сама выбирает шрифт, см. MiddleLine
    pass_label = MiddleLine(splash)
    bottom_line = Line(0, 48, 128, 48, color=0xFFFFFF)
    splash.append(bottom_line)

    # Меню списком: 4 строки (название слева, значение справа), выбранная — белой
    # полосой, справа полоска прокрутки, вверху справа «номер/всего»
    menu_group = displayio.Group()
    menu_highlight = Rect(0, 15, MENU_ROW_W, 12, fill=0xFFFFFF)
    menu_group.append(menu_highlight)
    menu_names = []
    menu_values = []
    for row in range(MENU_ROWS):
        y = 21 + row * 12
        name = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=3, y=y)
        value = label.Label(terminalio.FONT, text="", color=0xFFFFFF, y=y)
        menu_group.append(name)
        menu_group.append(value)
        menu_names.append(name)
        menu_values.append(value)
    menu_scroll_track = Line(125, 15, 125, 63, color=0xFFFFFF)
    menu_group.append(menu_scroll_track)
    menu_scroll = Rect(124, 15, 3, MENU_THUMB, fill=0xFFFFFF)
    menu_group.append(menu_scroll)
    menu_counter = label.Label(terminalio.FONT, text="", color=0xFFFFFF, y=6)
    menu_group.append(menu_counter)
    menu_group.hidden = True
    splash.append(menu_group)

    # Пульт MEDIA: значки «назад», «пауза/играть», «вперёд»
    media_icons = displayio.Group()
    for shape in (
        Rect(14, 25, 2, 13, fill=0xFFFFFF),                                  # |◀◀
        Triangle(26, 25, 17, 31, 26, 37, fill=0xFFFFFF, outline=0xFFFFFF),
        Triangle(35, 25, 26, 31, 35, 37, fill=0xFFFFFF, outline=0xFFFFFF),
        Triangle(51, 25, 51, 37, 60, 31, fill=0xFFFFFF, outline=0xFFFFFF),   # ▶||
        Rect(65, 25, 3, 13, fill=0xFFFFFF),
        Rect(71, 25, 3, 13, fill=0xFFFFFF),
        Triangle(89, 25, 98, 31, 89, 37, fill=0xFFFFFF, outline=0xFFFFFF),   # ▶▶|
        Triangle(98, 25, 107, 31, 98, 37, fill=0xFFFFFF, outline=0xFFFFFF),
        Rect(108, 25, 2, 13, fill=0xFFFFFF),
    ):
        media_icons.append(shape)
    media_icons.hidden = True
    splash.append(media_icons)

    # Верхняя строка профиля: справа значки ENT (Auto Enter) и CTL (Ctrl first) —
    # видны, когда включены, — и вид пароля для Gen Pass (EN / RU / Words)
    def make_badge(text):
        g = displayio.Group(y=1)
        g.append(Rect(0, 0, len(text) * 6 + 3, 11, fill=0xFFFFFF))
        g.append(label.Label(terminalio.FONT, text=text, color=0x000000, x=2, y=5))
        g.hidden = True
        splash.append(g)
        return g
    badge_enter = make_badge("ENT")
    badge_ctrl = make_badge("CTL")
    gen_badge = label.Label(terminalio.FONT, text="", color=0xFFFFFF, y=6)
    splash.append(gen_badge)

    # Нижняя строка: точки «где я». Кружки — профили, квадраты — MEDIA, JIGGLE и SETTINGS.
    # Закрашена текущая. Где стоять каждой точке, решает update_ui (MEDIA может быть скрыт).
    icons_group = displayio.Group()
    nav_dots = []
    for i in range(MAIN_MENU_ITEMS):
        if i < TOTAL_PROFILES:
            dot = Circle(0, 56, 2, fill=None, outline=0xFFFFFF)
        else:
            dot = Rect(-2, 54, 5, 5, fill=None, outline=0xFFFFFF)
        nav_dots.append(dot)
        icons_group.append(dot)
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


def set_menu_view(visible):
    """Меню списком или обычный экран (средняя строка между двумя линиями)."""
    menu_group.hidden = not visible
    bottom_line.hidden = visible
    if visible:
        pass_label.text = ""


def draw_menu(title, items):
    """Рисует меню списком. items — пары (название, значение); выбран пункт menu_index.
    Видно MENU_ROWS строк, выбранная — белой полосой, над ней видна одна строка."""
    set_menu_view(True)
    title_label.text = title
    title_label.x = 1
    count = len(items)
    menu_counter.text = "{}/{}".format(menu_index + 1, count)
    menu_counter.x = 123 - len(menu_counter.text) * 6
    first = min(max(menu_index - 1, 0), max(count - MENU_ROWS, 0))
    for row in range(MENU_ROWS):
        i = first + row
        name, value = items[i] if i < count else ("", "")
        color = 0x000000 if i == menu_index else 0xFFFFFF
        menu_names[row].text = name
        menu_names[row].color = color
        menu_values[row].text = value
        menu_values[row].color = color
        menu_values[row].x = MENU_ROW_W - 2 - len(value) * 6
    menu_highlight.y = 15 + (menu_index - first) * 12
    # Полоска прокрутки: бегунок показывает, где выбранный пункт в списке.
    # Если всё помещается на экран — полоска не нужна.
    scroll_needed = count > MENU_ROWS
    menu_scroll.hidden = menu_scroll_track.hidden = not scroll_needed
    if scroll_needed:
        menu_scroll.y = 15 + (48 - MENU_THUMB) * menu_index // (count - 1)


def set_centered_text(label_obj, text):
    """Пишет одну строку текста по центру экрана (6 пикселей на символ)."""
    if label_obj is pass_label:
        set_menu_view(False)              # сообщение поверх меню — меню прячем
        label_obj.scale = 1
        label_obj.y = 31
    label_obj.text = text
    label_obj.x = max(0, (128 - len(text) * 6) // 2)


def set_name_text(text):
    """Название профиля на главном экране: крупно, если помещается (до 10 символов),
    иначе обычным размером."""
    big = len(text) <= 10
    pass_label.scale = 2 if big else 1
    pass_label.y = 31
    pass_label.text = text
    pass_label.x = max(0, (128 - len(text) * (12 if big else 6)) // 2)


def hide_badges():
    badge_enter.hidden = True
    badge_ctrl.hidden = True
    gen_badge.text = ""


def set_bottom_mode(show_text=False):
    """Низ экрана: точки «где я» или строка текста."""
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
    hide_badges()
    set_centered_text(title_label, title)
    set_centered_text(pass_label, text)
    if bottom:
        set_bottom_mode(show_text=True)
        set_centered_text(bottom_label, bottom)
    else:
        set_bottom_mode(show_text=False)


# --- Клавиатура, мышь и мультимедийные клавиши для компьютера ---
kbd = None
layout = None
mouse = None
media_keys = None         # пауза, треки, громкость (пульт MEDIA)


def init_hid():
    global kbd, layout, mouse, media_keys
    kbd = Keyboard(usb_hid.devices)
    layout = KeyboardLayoutUS(kbd)
    mouse = Mouse(usb_hid.devices)
    try:
        media_keys = ConsumerControl(usb_hid.devices)
    except Exception as e:
        log_exception("мультимедийные клавиши (пульт MEDIA не будет работать)", e)


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
main_menu_index = 0       # 0-5 — профили, 6 — MEDIA, 7 — JIGGLE, 8 — SETTINGS
media_enabled = False     # SETTINGS → Media: есть ли экран MEDIA в карусели
media_mode = False        # включён пульт MEDIA: кнопки управляют музыкой
media_status_until = 0.0  # до какого времени внизу показано последнее действие пульта
menu_index = 0            # пункт внутри меню
sleep_preset = SLEEP_DEFAULT_PRESET
sleep_style = 0           # 0 = Off (экран выключается)
screen_brightness = BRIGHTNESS_DEFAULT
layout_auto = True        # SETTINGS → Layout: Auto (переключать раскладку) / Off
led_brightness = BRIGHTNESS_DEFAULT
auto_enter_enabled = False
ctrl_first_enabled = False
gen_mode = 0              # вид пароля Gen Pass для текущего профиля (номер в GEN_MODES)
mouse_jiggle_enabled = False
jiggle_preset = JIGGLE_DEFAULT_PRESET
last_mouse_jiggle_time = 0.0
next_mouse_jiggle_interval = 60.0
last_activity_time = 0.0
is_sleeping = False


def tick():
    """Фоновые дела, пока ждём кнопку: светодиод, Jiggle, анимация сна и подсказка пульта."""
    update_led()
    update_mouse_jiggle()
    update_sleep_animation()
    update_media_status()
    time.sleep(0.02)


# --- Пульт MEDIA: кнопки управляют музыкой и видео на компьютере ---

def enter_media_mode():
    global media_mode
    if media_keys is None:
        set_centered_text(pass_label, "No media keys")
        time.sleep(1.5)
        update_ui()
        return
    media_mode = True
    log("Пульт MEDIA включён.")
    update_ui()


def exit_media_mode():
    global media_mode
    media_mode = False
    update_ui()


def media_send(code, name):
    """Отправить мультимедийную клавишу и на секунду показать внизу, что нажато."""
    global media_status_until
    try:
        media_keys.send(code)
    except Exception as e:
        log_exception("пульт MEDIA", e)
        name = "Media ERROR"
    if not is_sleeping:
        set_centered_text(bottom_label, name)
        media_status_until = time.monotonic() + 1.0


def update_media_status():
    """Через секунду после действия внизу снова подсказка «hold Enter = exit»."""
    global media_status_until
    if media_status_until and time.monotonic() > media_status_until:
        media_status_until = 0.0
        if media_mode and not is_sleeping:
            set_centered_text(bottom_label, "hold Enter = exit")


def media_hold(btn, other, tap_code, tap_name, hold_code, hold_name):
    """«Вперёд»/«Назад» в пульте: коротко — трек, держать — громкость, пока держите.
    Нажали вторую кнопку — комбинация блокировки (Win+L), как везде."""
    next_step = time.monotonic() + NAV_REPEAT_DELAY
    held = False
    while pressed(btn):
        if pressed(other):
            handle_lock_combo()
            return
        now = time.monotonic()
        if now >= next_step:
            media_send(hold_code, hold_name)
            held = True
            next_step = now + MEDIA_VOLUME_INTERVAL
        tick()
    if not held:
        media_send(tap_code, tap_name)
    time.sleep(BUTTON_DEBOUNCE)


def media_press():
    """Нажатие кнопки, пока включён пульт MEDIA."""
    if pressed(btn_back) and pressed(btn_fwd):
        handle_lock_combo()
    elif pressed(btn_enter):
        if wait_enter() == "long":
            exit_media_mode()               # держать «Ввод» — выйти из пульта
        else:
            media_send(ConsumerControlCode.PLAY_PAUSE, "Play / Pause")
        wait_all_released()
    elif pressed(btn_fwd):
        media_hold(btn_fwd, btn_back, ConsumerControlCode.SCAN_NEXT_TRACK, "Next >>",
                   ConsumerControlCode.VOLUME_INCREMENT, "Volume +")
    elif pressed(btn_back):
        media_hold(btn_back, btn_fwd, ConsumerControlCode.SCAN_PREVIOUS_TRACK, "<< Prev",
                   ConsumerControlCode.VOLUME_DECREMENT, "Volume -")


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
    """Заставка при включении: крупно «PassPuck» и версия."""
    if SPLASH_TIME <= 0:
        return
    group = displayio.Group(x=2)
    group.append(label.Label(terminalio.FONT, text="PassPuck", color=0xFFFFFF,
                             scale=2, x=(128 - 8 * 12) // 2, y=24))
    version = "v" + VERSION
    group.append(label.Label(terminalio.FONT, text=version, color=0xFFFFFF,
                             x=(128 - len(version) * 6) // 2, y=48))
    display.root_group = group
    time.sleep(SPLASH_TIME)
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


def no_passwords_at_all():
    """Новое устройство: не задано ни одного пароля."""
    return passwords_source is not None and not any(passwords.values())


def type_password():
    """Набирает пароль текущего профиля. Сам пароль в журнал не пишется."""
    password = get_current_password()
    if not password:
        show_message("Profile {}".format(current_profile), "No password!")
        time.sleep(1)
        return
    if not is_typable(password):
        show_message("Profile {}".format(current_profile), "Bad chars in P{}".format(current_profile))
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
                if char in LAYOUT_NEUTRAL:
                    # цифры и символы ! % * ( ) - _ = + одинаковые в обеих раскладках —
                    # раскладку не трогаем
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
    remember_profile()
    flash_green()
    set_centered_text(pass_label, "Done!")
    time.sleep(0.5)


def show_password():
    """Показывает пароль на 4 секунды. Длинный пароль — в две строки.
    Пароль из слов — 6 секунд, а под ним по-русски, как его запомнить.
    Без шрифта с кириллицей русские буквы показываются как «?»."""
    pw = get_current_password() or "No password!"
    hint = words_hint(pw)
    seconds = 6 if hint else 4
    set_menu_view(False)
    pass_label.scale = 1
    if hint:
        width = max(len(pw), len(hint))
        pass_label.y = 25
        pass_label.text = (" " * ((width - len(pw)) // 2) + pw + "\n"
                           + " " * ((width - len(hint)) // 2) + hint)
        pass_label.x = max(0, (128 - width * 6) // 2)
    elif len(pw) > 21:
        pass_label.y = 25
        pass_label.text = pw[:21] + "\n" + pw[21:42]
        pass_label.x = 2
    else:
        set_centered_text(pass_label, pw)
    set_bottom_mode(show_text=True)
    for seconds_left in range(seconds, 0, -1):
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
    if not ask_confirm("Gen Pass P{} {}?".format(p, GEN_MODES[gen_mode]), "Enter = YES"):
        show_message("Gen Pass P{}".format(p), "Cancelled")
        time.sleep(0.7)
        return

    if gen_mode in (GEN_WORDS, GEN_WORDS_RU):
        new = generate_words_password(russian=gen_mode == GEN_WORDS_RU)
        if new is None:
            log("Gen Pass P{}: словарь {} не найден или в нём меньше {} слов.".format(
                p, WORDS_FILE, WORDS_MIN))
            show_message("Gen Pass P{}".format(p), "No words.txt", "Old pass kept")
            time.sleep(2.5)
            return
    else:
        new = generate_password(RU_GEN_CHARS if gen_mode == 1 else CHARS)
    old = passwords[p]
    passwords[p] = new
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
        show_password()             # сразу показываем новый пароль, чтобы его запомнить
        in_menu = False


def update_ui():
    """Перерисовывает главный экран или меню по текущему состоянию."""
    set_bottom_mode(show_text=False)
    hide_badges()
    media_icons.hidden = True
    on_jiggle = main_menu_index == JIGGLE_ITEM
    on_settings = main_menu_index == SETTINGS_ITEM
    jiggle_icon.hidden = in_menu or not mouse_jiggle_enabled

    if not in_menu:
        set_menu_view(False)
        icons_group.hidden = False
        # Точки по центру, через 8 пикселей; точки MEDIA нет, если пульт выключен
        shown = [i for i in range(MAIN_MENU_ITEMS) if i != MEDIA_ITEM or media_enabled]
        left = 64 - (len(shown) - 1) * 4
        for i, dot in enumerate(nav_dots):
            dot.hidden = i not in shown
            if i in shown:
                dot.x = left + shown.index(i) * 8 - 2
            dot.fill = 0xFFFFFF if i == main_menu_index else None
        if main_menu_index == MEDIA_ITEM:
            set_centered_text(title_label, "=== MEDIA ===")
            if media_mode:
                # Пульт включён: значки в центре, внизу — подсказка или последнее действие
                pass_label.text = ""
                media_icons.hidden = False
                set_bottom_mode(show_text=True)
                set_centered_text(bottom_label, "hold Enter = exit")
            else:
                set_centered_text(pass_label, "Enter = remote")
        elif on_jiggle:
            set_centered_text(title_label, "=== JIGGLE ===")
            set_centered_text(pass_label, "Jiggle {} | {}".format(
                "ON" if mouse_jiggle_enabled else "OFF",
                seconds_label(JIGGLE_PRESETS[jiggle_preset])))
        elif on_settings:
            set_centered_text(title_label, "=== SETTINGS ===")
            set_centered_text(pass_label, "Sleep {} | {}".format(
                sleep_preset_label(), SLEEP_STYLES[sleep_style]))
        else:
            # Слева «1/6», справа значки: ENT, CTL (если включены) и вид Gen (профили 1-3)
            title_label.text = "{}/{}".format(current_profile, TOTAL_PROFILES)
            title_label.x = 1
            right = 128
            if current_profile <= 3:
                gen_badge.text = GEN_MODES[gen_mode]
                gen_badge.x = right - len(gen_badge.text) * 6
                right = gen_badge.x - 3
            for badge, on in ((badge_ctrl, ctrl_first_enabled), (badge_enter, auto_enter_enabled)):
                badge.hidden = not on
                if on:
                    badge.x = right - 21
                    right = badge.x - 3
            set_name_text(profile_names.get(current_profile, "Profile {}".format(current_profile)))
            # Пароля нет или его нельзя набрать — сразу говорим об этом внизу
            pw = get_current_password()
            if no_passwords_at_all():
                warning = "Open Editor.html"    # новое устройство: диск открыт для редактора
            elif not pw:
                warning = "No password!"
            else:
                warning = "Bad chars!" if not is_typable(pw) else None
            if warning:
                set_bottom_mode(show_text=True)
                set_centered_text(bottom_label, warning)
    else:
        icons_group.hidden = True
        # Пункт Exit напоминает, что выйти можно и долгим нажатием «Ввод»
        exit_item = ("Exit", "hold Enter")
        if on_jiggle:
            title = "JIGGLE"
            items = [
                ("Every", seconds_label(JIGGLE_PRESETS[jiggle_preset])),
                exit_item,
            ]
        elif on_settings:
            title = "SETTINGS"
            items = [
                ("Sleep", sleep_preset_label()),
                ("Style", SLEEP_STYLES[sleep_style]),
                ("Preview", ""),
                ("Screen", SCREEN_BRIGHTNESS[screen_brightness][0]),
                ("LED", LED_BRIGHTNESS[led_brightness][0]),
                ("Layout", "Auto" if layout_auto else "Off"),
                ("Media", "On" if media_enabled else "Off"),
                ("Edit mode" if FS_WRITABLE else "Exit edit mode", ""),
                exit_item,
            ]
        else:
            # Порядок по смыслу: сначала то, что нужно чаще; вид пароля — перед Gen Pass
            title = "P{} MENU".format(current_profile)
            items = [
                ("Show Pass", ""),
                ("Gen type", GEN_MODES[gen_mode] if current_profile <= 3 else "-"),
                ("Gen Pass", ""),
                ("Enter", "ON" if auto_enter_enabled else "OFF"),
                ("Ctrl first", "ON" if ctrl_first_enabled else "OFF"),
                exit_item,
            ]
        draw_menu(title, items)


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
        remember_profile()
        in_menu = False
        menu_index = 0
        if not media_mode:              # пульт MEDIA сон не выключает
            main_menu_index = current_profile - 1
        update_ui()                 # после пробуждения будет главный экран (или пульт)
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
anim_items = []           # звёзды, капли, искры салюта
anim_next_frame = 0.0
anim_dx = 1
anim_dy = 1
anim_active = ""          # какая анимация идёт сейчас (в Mix меняется сама)
mix_next_switch = 0.0
anim_s = {}               # состояние текущей анимации

try:
    import bitmaptools    # быстрые встроенные функции рисования
except ImportError:
    bitmaptools = None


def fill_rect(x1, y1, x2, y2, value):
    """Закрасить прямоугольник [x1..x2) × [y1..y2) на картинке анимации (с обрезкой по краям)."""
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(ANIM_W, x2)
    y2 = min(ANIM_H, y2)
    if x1 >= x2 or y1 >= y2:
        return
    if bitmaptools:
        bitmaptools.fill_region(anim_bitmap, x1, y1, x2, y2, value)
    else:
        for yy in range(y1, y2):
            for xx in range(x1, x2):
                anim_bitmap[xx, yy] = value


def set_px(x, y, value):
    if 0 <= x < ANIM_W and 0 <= y < ANIM_H:
        anim_bitmap[x, y] = value


def draw_shape(rows, x, y, value):
    """Маленькая картинка из строк "0101..." (1 — закрасить точку)."""
    for r in range(len(rows)):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == "1":
                set_px(x + c, y + r, value)


def draw_line(x1, y1, x2, y2, value):
    """Линия на картинке анимации. Концы прижимаются к краям картинки."""
    x1 = max(0, min(ANIM_W - 1, int(x1)))
    x2 = max(0, min(ANIM_W - 1, int(x2)))
    y1 = max(0, min(ANIM_H - 1, int(y1)))
    y2 = max(0, min(ANIM_H - 1, int(y2)))
    if bitmaptools:
        bitmaptools.draw_line(anim_bitmap, x1, y1, x2, y2, value)
        return
    steps = max(abs(x2 - x1), abs(y2 - y1), 1)
    for i in range(steps + 1):
        set_px(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps, value)


def draw_circle(cx, cy, r, value):
    if bitmaptools:
        bitmaptools.draw_circle(anim_bitmap, cx, cy, r, value)
        return
    for i in range(64):
        a = i * 6.283 / 64
        set_px(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), value)


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
    """Запускает выбранную анимацию. В режиме Mix — случайную, не ту же, что была."""
    global anim_active, mix_next_switch
    style = SLEEP_STYLES[sleep_style]
    if style == "Mix":
        choices = [s for s in SLEEP_STYLES if s not in ("Off", "Mix", anim_active)]
        anim_active = random.choice(choices)
        mix_next_switch = time.monotonic() + MIX_PERIOD
    else:
        anim_active = style
    begin_animation(anim_active)
    display.root_group = anim_group


def begin_animation(name):
    """Готовит картинку и начальное состояние анимации name."""
    global anim_items, anim_next_frame, anim_s
    anim_bitmap.fill(0)
    anim_logo.hidden = name not in ("Bounce", "Pulse")
    anim_items = []
    anim_s = {}
    if name in NEW_ANIMATIONS:                     # анимации со своей функцией запуска
        NEW_ANIMATIONS[name][0]()
        anim_next_frame = 0.0
        return
    if name == "Stars":
        anim_items = [new_star() for _ in range(24)]
    elif name == "Rain":
        anim_items = [new_drop(random.randrange(ANIM_H)) for _ in range(14)]
    elif name == "Bounce":
        anim_logo.text = "PassPuck"
        anim_logo.x = random.randrange(0, ANIM_W - 48)
        anim_logo.y = random.randrange(8, ANIM_H - 8)
    elif name == "Eyes":
        anim_s = {"px": 0.0, "py": 0.0, "tx": 0, "ty": 0, "open": 1.0,
                  "blink": [], "next_look": 0.0, "next_blink": time.monotonic() + 2,
                  "sleepy_until": 0.0, "drawn": None}
    elif name == "Fireworks":
        anim_s = {"rockets": [], "next_launch": 0.0}
    anim_next_frame = 0.0


# ---------- Глаза: смотрят по сторонам, моргают, иногда прищуриваются ----------
EYE_W = 34
EYE_H = 38
EYE_CENTERS = ((36, 32), (92, 32))
EYE_LOOKS = ((0, 0), (-9, 0), (9, 0), (0, -6), (0, 6), (-8, -5), (8, -5), (-8, 5), (8, 5))


def draw_eyes(openness, px, py):
    fill_rect(14, 6, 115, 60, 0)                       # стираем оба глаза
    h = max(2, int(EYE_H * openness))
    for cx, cy in EYE_CENTERS:
        x0 = cx - EYE_W // 2
        y0 = cy - h // 2
        fill_rect(x0, y0, x0 + EYE_W, y0 + h, 1)      # белок
        if h > 6:                                      # скруглённые уголки
            for ux, uy in ((x0, y0), (x0 + EYE_W - 2, y0), (x0, y0 + h - 2), (x0 + EYE_W - 2, y0 + h - 2)):
                fill_rect(ux, uy, ux + 2, uy + 2, 0)
        if h > 10:                                     # зрачок, не вылезает за белок
            zx = cx + px - 6
            zy = max(y0 + 2, min(y0 + h - 16, cy + py - 7))
            fill_rect(zx, zy, zx + 12, zy + 14, 0)


def update_eyes(now):
    s = anim_s
    if now >= s["next_look"]:                          # новое направление взгляда
        s["tx"], s["ty"] = random.choice(EYE_LOOKS)
        s["next_look"] = now + random.uniform(1.0, 3.0)
    if not s["blink"] and now >= s["next_blink"]:      # моргнуть
        s["blink"] = [0.6, 0.25, 0.05, 0.25, 0.6, 1.0]
        s["next_blink"] = now + random.uniform(2.5, 6.0)
        if random.randrange(6) == 0:                   # иногда — сонно прищуриться
            s["sleepy_until"] = now + random.uniform(2.0, 4.0)
    if s["blink"]:
        s["open"] = s["blink"].pop(0)
    else:
        s["open"] = 0.35 if now < s["sleepy_until"] else 1.0
    s["px"] += (s["tx"] - s["px"]) * 0.3               # зрачки плавно догоняют цель
    s["py"] += (s["ty"] - s["py"]) * 0.3
    state = (s["open"], int(s["px"]), int(s["py"]))
    if state != s["drawn"]:                            # рисуем, только если что-то изменилось
        draw_eyes(*state)
        s["drawn"] = state


# ---------- Салют: ракета взлетает и разлетается искрами ----------
def update_fireworks(now):
    global anim_items
    s = anim_s
    if len(s["rockets"]) < 2 and len(anim_items) < 40 and now >= s["next_launch"]:
        s["rockets"].append([float(random.randrange(20, 108)), 63.0,
                             -random.uniform(1.8, 2.6), random.randrange(10, 30)])
        s["next_launch"] = now + random.uniform(0.6, 1.8)
    rockets = []
    for r in s["rockets"]:
        set_px(int(r[0]), int(r[1]), 0)
        set_px(int(r[0]), int(r[1]) + 1, 0)
        r[1] += r[2]
        r[2] += 0.03                                   # притяжение тормозит ракету
        if r[1] <= r[3] or r[2] >= -0.3:               # взрыв
            for _ in range(random.randrange(16, 24)):
                a = random.uniform(0, 6.283)
                v = random.uniform(0.4, 1.6)
                anim_items.append([r[0], r[1], math.cos(a) * v, math.sin(a) * v,
                                   random.randrange(22, 38)])
        else:
            set_px(int(r[0]), int(r[1]), 1)
            set_px(int(r[0]), int(r[1]) + 1, 1)        # хвостик
            rockets.append(r)
    s["rockets"] = rockets
    sparks = []
    for p in anim_items:                               # искры: [x, y, vx, vy, жизнь]
        set_px(int(p[0]), int(p[1]), 0)
        p[0] += p[2]
        p[1] += p[3]
        p[3] += 0.04
        p[2] *= 0.97
        p[4] -= 1
        if p[4] > 0 and 0 <= p[0] < ANIM_W and p[1] < ANIM_H:
            if p[4] > 6 or p[4] % 2:                   # перед угасанием мерцает
                set_px(int(p[0]), int(p[1]), 1)
            sparks.append(p)
    anim_items = sparks


# ---------- Змейка: сама ползает к еде, растёт; застряла — начинает заново ----------
SNAKE_W = 32              # поле 32×16 клеток по 4 пикселя
SNAKE_H = 16


def snake_cell(cx, cy, value):
    fill_rect(cx * 4, cy * 4, cx * 4 + 3, cy * 4 + 3, value)


def snake_food():
    s = anim_s
    while True:
        f = (random.randrange(SNAKE_W), random.randrange(SNAKE_H))
        if f not in s["body"]:
            break
    s["food"] = f
    fill_rect(f[0] * 4 + 1, f[1] * 4 + 1, f[0] * 4 + 3, f[1] * 4 + 3, 1)


def begin_snake():
    anim_bitmap.fill(0)
    anim_s["body"] = [(10, 8), (9, 8), (8, 8)]        # голова первая
    anim_s["dir"] = (1, 0)
    anim_s["step"] = 0
    for c in anim_s["body"]:
        snake_cell(c[0], c[1], 1)
    snake_food()


def update_snake(now):
    s = anim_s
    s["step"] += 1
    if s["step"] % 2:                                 # шаг через кадр — не слишком быстро
        return
    body = s["body"]
    hx, hy = body[0]
    fx, fy = s["food"]
    options = []
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if d[0] == -s["dir"][0] and d[1] == -s["dir"][1]:
            continue                                  # назад нельзя
        nx, ny = hx + d[0], hy + d[1]
        if 0 <= nx < SNAKE_W and 0 <= ny < SNAKE_H and (nx, ny) not in body[:-1]:
            options.append((abs(fx - nx) + abs(fy - ny) + random.random() * 0.5, d, (nx, ny)))
    if not options or len(body) > 70:
        begin_snake()
        return
    options.sort()
    s["dir"] = options[0][1]
    new = options[0][2]
    body.insert(0, new)
    if new == s["food"]:
        snake_cell(new[0], new[1], 1)
        snake_food()
    else:
        tail = body.pop()
        snake_cell(tail[0], tail[1], 0)               # сначала стираем хвост,
        snake_cell(new[0], new[1], 1)                 # потом рисуем голову


# ---------- Матрица: колонки бегущих символов ----------
MATRIX_GLYPHS = (0b111101101101111, 0b010110010010111, 0b111001111100111, 0b111001011001111,
                 0b101101111001001, 0b111100111001111, 0b110001010100011, 0b101010101010101,
                 0b011100110100011, 0b111010010010010, 0b100110101011001, 0b011101111101101)
MATRIX_ROWS = 11          # символ 3×5 + промежуток, строки по 6 пикселей


def matrix_glyph(x, y, value):
    fill_rect(x, y, x + 3, y + 5, 0)
    if value:
        g = random.choice(MATRIX_GLYPHS)
        for i in range(15):
            if (g >> (14 - i)) & 1:
                set_px(x + i % 3, y + i // 3, 1)


def matrix_column():
    # [голова (строка), скорость (кадров на шаг), длина хвоста, счётчик]
    return [random.randrange(-8, 0), random.randrange(1, 4), random.randrange(4, 10), 0]


def begin_matrix():
    global anim_items
    anim_items = [matrix_column() for _ in range(21)]


def update_matrix(now):
    for i in range(len(anim_items)):
        c = anim_items[i]
        c[3] += 1
        if c[3] < c[1]:
            continue
        c[3] = 0
        x = 1 + i * 6
        if 0 <= c[0] < MATRIX_ROWS:
            matrix_glyph(x, c[0] * 6, 1)              # новый символ внизу колонки
        tail = c[0] - c[2]
        if 0 <= tail < MATRIX_ROWS:
            matrix_glyph(x, tail * 6, 0)              # хвост исчезает
        c[0] += 1
        if tail >= MATRIX_ROWS:
            anim_items[i] = matrix_column()


# ---------- Кардиограмма: живой пульс с бьющимся сердечком ----------
# Пульс то спокойный, то учащается; каждый удар немного другой; линия «дышит»;
# изредка бывает лишний или пропущенный удар. Сердечко в углу вздрагивает на каждом ударе.
PULSE_BEAT = (0, -1, -2, -2, -1, 0, 0, 1, 3, -6, -18, -24, -12, 4, 7, 3, 0, 0,
              -1, -2, -3, -3, -2, -1, 0, 0)
PULSE_BASE_Y = 44
PULSE_TOP = 14                       # выше — сердечко и BPM
PULSE_HEART_BIG = ("01101100", "11111110", "11111110", "11111110", "01111100", "00111000", "00010000")
PULSE_HEART_SMALL = ("00000000", "00101000", "01111100", "01111100", "00111000", "00010000", "00000000")


def pulse_heart(big):
    fill_rect(1, 1, 10, 9, 0)
    draw_shape(PULSE_HEART_BIG if big else PULSE_HEART_SMALL, 1, 1, 1)


def begin_pulse():
    anim_s.update(x=0, i=-1, gap=10, prev=PULSE_BASE_Y, bpm=72.0, target=72.0,
                  next_mood=time.monotonic() + 8, amp=1.0, breath=0.0, heart=0)
    anim_logo.x = 13
    anim_logo.y = 5
    anim_logo.text = "72"
    pulse_heart(False)


def update_pulse(now):
    s = anim_s
    if now >= s["next_mood"]:                         # настроение: спокойно / волнение
        s["target"] = random.choice((62.0, 68.0, 74.0, 80.0, 96.0, 110.0))
        s["next_mood"] = now + random.uniform(6, 14)
    s["bpm"] += (s["target"] - s["bpm"]) * 0.02       # пульс меняется плавно
    s["breath"] += 0.04
    if s["heart"] > 0:                                # сердечко «бьётся»
        s["heart"] -= 1
        if s["heart"] == 0:
            pulse_heart(False)
    for _ in range(3):                                # 3 пикселя за кадр
        x = s["x"]
        fill_rect(x, PULSE_TOP, x + 6, ANIM_H, 0)     # просвет перед линией
        base = PULSE_BASE_Y + int(math.sin(s["breath"]) * 2)   # дыхание
        if s["i"] < 0:                                # пауза между ударами
            y = base + (random.randrange(3) - 1 if random.randrange(5) == 0 else 0)
            s["gap"] -= 1
            if s["gap"] <= 0:
                s["i"] = 0
                s["amp"] = random.uniform(0.75, 1.15)  # каждый удар чуть другой
        else:
            y = base + int(PULSE_BEAT[s["i"]] * s["amp"])
            if s["i"] == 10:                          # пик удара — сердечко вздрагивает
                pulse_heart(True)
                s["heart"] = 3
                anim_logo.text = str(int(s["bpm"]))
            s["i"] += 1
            if s["i"] >= len(PULSE_BEAT):
                s["i"] = -1
                period = int(60 * 60 / s["bpm"])      # 60 пикселей в секунду
                s["gap"] = max(2, period - len(PULSE_BEAT))
                r = random.randrange(40)
                if r == 0:
                    s["gap"] = max(2, s["gap"] // 3)  # лишний (ранний) удар
                elif r == 1:
                    s["gap"] += period                # пропущенный удар
        y = max(PULSE_TOP, min(ANIM_H - 1, y))
        fill_rect(x, min(y, s["prev"]), x + 1, max(y, s["prev"]) + 1, 1)
        s["prev"] = y
        s["x"] = x + 1 if x + 1 < ANIM_W else 0


# ---------- Гиперпрыжок: звёзды растягиваются в линии ----------
def warp_star():
    a = random.uniform(0, 6.283)
    r = random.uniform(2, 10)
    v = random.uniform(0.3, 0.8)
    x = 64 + math.cos(a) * r
    y = 32 + math.sin(a) * r
    return [x, y, math.cos(a) * v, math.sin(a) * v, None]   # последний — нарисованный отрезок


def begin_warp():
    global anim_items
    anim_items = [warp_star() for _ in range(12)]


def update_warp(now):
    for i in range(len(anim_items)):
        s = anim_items[i]
        if s[4]:
            draw_line(s[4][0], s[4][1], s[4][2], s[4][3], 0)
        tail_x, tail_y = s[0], s[1]
        s[0] += s[2]
        s[1] += s[3]
        s[2] *= 1.09
        s[3] *= 1.09
        if 0 <= s[0] < ANIM_W and 0 <= s[1] < ANIM_H:
            seg = (int(tail_x), int(tail_y), int(s[0]), int(s[1]))
            draw_line(seg[0], seg[1], seg[2], seg[3], 1)
            s[4] = seg
        else:
            anim_items[i] = warp_star()


# ---------- Снег: снежинки падают и копятся сугробом ----------
def snowflake():
    return [random.uniform(0, ANIM_W - 1), random.uniform(-20, 0),
            random.uniform(0.3, 0.8), random.uniform(0, 6.283)]


def begin_snow():
    global anim_items
    anim_items = [snowflake() for _ in range(30)]
    anim_s["ground"] = [0] * ANIM_W                     # высота сугроба в каждой колонке


def update_snow(now):
    ground = anim_s["ground"]
    for i in range(len(anim_items)):
        f = anim_items[i]
        set_px(int(f[0]), int(f[1]), 0)
        f[1] += f[2]
        f[3] += 0.15
        f[0] = max(0.0, min(ANIM_W - 1.0, f[0] + math.sin(f[3]) * 0.4))
        x = int(f[0])
        for nx in (x - 1, x + 1):                       # снежинка скатывается в ямку рядом
            if 0 <= nx < ANIM_W and ground[nx] + 1 < ground[x]:
                x = nx
        top = ANIM_H - 1 - ground[x]
        if f[1] >= top:                                 # легла на сугроб
            set_px(x, top, 1)
            ground[x] += 1
            anim_items[i] = snowflake()
        else:
            set_px(x, int(f[1]), 1)
    if max(ground) > 28:                                # сугроб вырос — зима заново
        anim_bitmap.fill(0)
        anim_s["ground"] = [0] * ANIM_W


# ---------- Замок: защёлкивается, открывается, щёлкает ----------
def draw_lock(lift, shake):
    fill_rect(36, 2, 92, 62, 0)
    x = shake
    top = 14 - lift
    fill_rect(52 + x, top, 76 + x, top + 4, 1)           # верх дужки
    fill_rect(52 + x, top, 56 + x, 31, 1)                # левая нога дужки (всегда в корпусе)
    fill_rect(72 + x, top, 76 + x, 31 - lift, 1)         # правая нога (выходит из корпуса)
    fill_rect(46 + x, 30, 82 + x, 56, 1)                 # корпус
    for ux, uy in ((46, 30), (81, 30), (46, 55), (81, 55)):
        set_px(ux + x, uy, 0)                            # скруглённые углы
    fill_rect(62 + x, 37, 66 + x, 42, 0)                 # замочная скважина
    fill_rect(63 + x, 42, 65 + x, 49, 0)


def begin_lock():
    anim_s.update(phase="closed", until=time.monotonic() + 2.5, lift=0, shake=0, frame=0, drawn=None)


def update_lock(now):
    s = anim_s
    ph = s["phase"]
    if ph == "closed" and now >= s["until"]:
        s["phase"] = "opening"
    elif ph == "opening":
        s["lift"] += 1
        if s["lift"] >= 7:
            s["phase"] = "open"
            s["until"] = now + random.uniform(1.0, 2.0)
    elif ph == "open" and now >= s["until"]:
        s["phase"] = "closing"
    elif ph == "closing":
        s["lift"] -= 2
        if s["lift"] <= 0:
            s["lift"] = 0
            s["phase"] = "click"
            s["frame"] = 0
    elif ph == "click":                                  # «щелчок»: замок вздрагивает
        s["frame"] += 1
        s["shake"] = (1, -1, 1, 0)[min(s["frame"] - 1, 3)]
        if s["frame"] >= 4:
            s["phase"] = "closed"
            s["until"] = now + random.uniform(2.5, 4.5)
    state = (s["lift"], s["shake"])
    if state != s["drawn"]:
        draw_lock(*state)
        s["drawn"] = state


# Новые анимации: имя -> (функция запуска, функция кадра)
NEW_ANIMATIONS = {
    "Snake": (begin_snake, update_snake),
    "Matrix": (begin_matrix, update_matrix),
    "Pulse": (begin_pulse, update_pulse),
    "Warp": (begin_warp, update_warp),
    "Snow": (begin_snow, update_snow),
    "Lock": (begin_lock, update_lock),
}


def update_sleep_animation():
    """Один кадр анимации (вызывается постоянно из tick, рисует не чаще ANIMATION_FRAME_TIME)."""
    global anim_next_frame, anim_dx, anim_dy
    if not is_sleeping or sleep_style == 0:
        return
    now = time.monotonic()
    if now < anim_next_frame:
        return
    anim_next_frame = now + ANIMATION_FRAME_TIME
    if SLEEP_STYLES[sleep_style] == "Mix" and now >= mix_next_switch:
        start_sleep_animation()                    # Mix: пора сменить анимацию
        return
    style = anim_active

    if style in NEW_ANIMATIONS:
        NEW_ANIMATIONS[style][1](now)
    elif style == "Eyes":
        update_eyes(now)
    elif style == "Fireworks":
        update_fireworks(now)
    elif style == "Stars":
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
    """«Назад» / «Вперёд»: короткое нажатие листает, когда кнопку ОТПУСТИЛИ.
    Если держать дольше NAV_REPEAT_DELAY — листает само, пока кнопку не отпустят.
    Если, пока кнопка зажата, нажали вторую — это комбинация блокировки (Win+L)."""
    next_step = time.monotonic() + NAV_REPEAT_DELAY
    repeated = False
    while pressed(btn):
        if pressed(other):
            handle_lock_combo()
            return
        now = time.monotonic()
        if now >= next_step:
            navigate(step)
            repeated = True
            next_step = now + NAV_REPEAT_INTERVAL
        tick()
    if not repeated:
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


def menu_key():
    """Какое меню открыто: у профилей одно общее, у JIGGLE и SETTINGS — свои."""
    return main_menu_index if main_menu_index >= TOTAL_PROFILES else "profile"


def navigate(step):
    """«Вперёд» (+1) или «Назад» (-1): листаем профили или пункты меню."""
    global main_menu_index, menu_index, current_profile, auto_enter_enabled
    global ctrl_first_enabled, gen_mode
    if in_menu:
        if main_menu_index == JIGGLE_ITEM:
            count = 2
        elif main_menu_index == SETTINGS_ITEM:
            count = 9
        else:
            count = 6
        menu_index = (menu_index + step) % count
        menu_memory[menu_key()] = menu_index
    else:
        main_menu_index = (main_menu_index + step) % MAIN_MENU_ITEMS
        if main_menu_index == MEDIA_ITEM and not media_enabled:
            main_menu_index = (main_menu_index + step) % MAIN_MENU_ITEMS   # пульт выключен — пропускаем
        if main_menu_index < TOTAL_PROFILES:
            current_profile = main_menu_index + 1
            auto_enter_enabled = load_auto_enter(current_profile)
            ctrl_first_enabled = load_ctrl_first(current_profile)
            gen_mode = load_gen_mode(current_profile)
    update_ui()


def on_enter(press):
    """«Ввод» коротко ("short") или долго ("long")."""
    global in_menu, menu_index, mouse_jiggle_enabled
    global jiggle_preset
    global auto_enter_enabled, ctrl_first_enabled, sleep_preset, sleep_style
    global screen_brightness, led_brightness, gen_mode, layout_auto, media_enabled
    on_jiggle = main_menu_index == JIGGLE_ITEM
    on_settings = main_menu_index == SETTINGS_ITEM

    # ---------- главный экран ----------
    if not in_menu:
        if main_menu_index == MEDIA_ITEM:           # MEDIA: любое нажатие включает пульт
            enter_media_mode()
            return
        if press == "long" or on_settings:          # SETTINGS открывается любым нажатием
            in_menu = True
            menu_index = menu_memory.get(menu_key(), 0)   # там, где закрыли в прошлый раз
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

    # ---------- меню SETTINGS: Sleep / Style / Preview / Screen / LED / Layout / Media / Edit / Exit ----------
    if on_settings:
        if press == "long" or menu_index == 8:
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
            go_to_sleep(preview=True)               # Preview: уснуть прямо сейчас
            return
        elif menu_index == 3:
            screen_brightness = (screen_brightness + 1) % len(SCREEN_BRIGHTNESS)
            save_brightness(screen_brightness, led_brightness)
            apply_brightness()
            log("Яркость экрана: " + SCREEN_BRIGHTNESS[screen_brightness][0])
        elif menu_index == 4:
            led_brightness = (led_brightness + 1) % len(LED_BRIGHTNESS)
            save_brightness(screen_brightness, led_brightness)
            apply_brightness()
            log("Яркость светодиода: " + LED_BRIGHTNESS[led_brightness][0])
        elif menu_index == 5:
            layout_auto = not layout_auto
            save_layout_auto(layout_auto)
            log("Раскладка: " + ("Auto" if layout_auto else "Off"))
        elif menu_index == 6:
            media_enabled = not media_enabled       # показать / убрать экран MEDIA
            save_media_enabled(media_enabled)
            log("Пульт MEDIA: " + ("On" if media_enabled else "Off"))
        elif menu_index == 7:
            edit_mode_flow()                        # Edit mode / Exit edit mode
        update_ui()
        update_led()
        return

    # ---------- меню профиля ----------
    if press == "long" or menu_index == 5:          # долгое нажатие или Exit
        in_menu = False
    elif menu_index == 0:                           # Show Pass
        show_password()
    elif menu_index == 2:                           # Gen Pass
        gen_pass_flow()
    elif menu_index == 3:                           # Enter: ON/OFF
        auto_enter_enabled = not auto_enter_enabled
        save_auto_enter(current_profile, auto_enter_enabled)
        log("P{}: Enter -> {}".format(current_profile, "ON" if auto_enter_enabled else "OFF"))
    elif menu_index == 4:                           # Ctrl first: ON/OFF
        ctrl_first_enabled = not ctrl_first_enabled
        save_ctrl_first(current_profile, ctrl_first_enabled)
        log("P{}: Ctrl first -> {}".format(current_profile, "ON" if ctrl_first_enabled else "OFF"))
    elif menu_index == 1:                           # Gen type: EN/RU/Words
        if current_profile > 3:
            set_centered_text(pass_label, "Fixed Profile!")
            time.sleep(1)
        else:
            gen_mode = (gen_mode + 1) % len(GEN_MODES)
            save_gen_mode(current_profile, gen_mode)
            log("P{}: Gen -> {}".format(current_profile, GEN_MODES[gen_mode]))
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
        if no_passwords_at_all():
            # Новое устройство, а пароли решили создавать прямо на нём (Gen Pass):
            # запоминаем, чтобы boot.py больше не открывал диск сам
            nvm[NVM_SETUP_SKIPPED] = EDIT_FLAG_VALUE
            log("Первая настройка через редактор пропущена.")
    show_message("PassPuck", "Restarting...")
    time.sleep(0.5)
    microcontroller.reset()


def main_loop():
    while True:
        tick()
        if not any_pressed():
            check_sleep()
            continue

        # Экран погас: первое нажатие только будит его.
        # Кроме пульта MEDIA: там нажатие сразу выполняет действие (пауза, трек) —
        # это безопасно, пароль так не напечатается.
        if is_sleeping and not media_mode:
            wake_up()
            wait_all_released()
            continue
        wake_up()

        if media_mode:
            media_press()
        elif pressed(btn_back) and pressed(btn_fwd):
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
    global gen_mode, layout_auto, current_profile, main_menu_index, media_enabled

    nvm_prepare()
    boot_number = nvm_next_boot_number()
    reason = str(microcontroller.cpu.reset_reason).split(".")[-1]
    mode = "обычный" if FS_WRITABLE else "редактирование (запись на флешку выключена)"
    log("===== Включение. PassPuck v{} | причина: {} | режим: {} =====".format(VERSION, reason, mode))
    log("Настройки: " + SETTINGS_STATUS)
    if HARDWARE_PINS_USED:
        log("Кнопки: используются контакты из hardware_pins.py")

    load_passwords()
    init_display()
    screen_brightness, led_brightness = load_brightness()
    layout_auto = load_layout_auto()
    media_enabled = load_media_enabled()
    apply_brightness()
    show_splash()
    init_hid()

    current_profile = load_last_profile()      # начинаем с профиля, которым пользовались
    main_menu_index = current_profile - 1
    auto_enter_enabled = load_auto_enter(current_profile)
    ctrl_first_enabled = load_ctrl_first(current_profile)
    gen_mode = load_gen_mode(current_profile)
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
    elif no_passwords_at_all():
        # Первая настройка: boot.py уже открыл диск — подсказываем, что делать
        log("Паролей ещё нет: первая настройка, диск CIRCUITPY открыт.")
        show_message("PassPuck setup", "Open disk CIRCUITPY", "PassPuck Editor.html")
        time.sleep(4)
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


def run():
    """Запуск устройства. Вызывается из code.py.
    (Для проверки из консоли можно сделать «import passpuck» без запуска.)"""
    try:
        startup()
        main_loop()
    except Exception as e:
        fatal_error(e)
