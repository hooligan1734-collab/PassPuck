# =====================================================================
#  boot.py — выполняется один раз при включении, ДО основной программы.
#  Решает, кто может писать на флешку: компьютер или само устройство.
#
#  Обычный режим:
#    - диск CIRCUITPY скрыт от компьютера (пароли нельзя просто скопировать);
#    - устройство само может писать файлы: сохранять Gen Pass и вести log.txt.
#
#  Режим редактирования — включается любым из способов:
#    - подключить USB с зажатой кнопкой «Назад»;
#    - в меню устройства: SETTINGS → Edit mode (устройство само перезапустится).
#  В этом режиме диск CIRCUITPY виден, файлы можно менять с компьютера,
#  а устройство само ничего записать не может.
#
#  Первая настройка: пока в passwords.py нет ни одного пароля (новое устройство),
#  диск открывается сам — чтобы сразу открыть на нём PassPuck Editor.html.
#  Если вместо этого выбрать на устройстве SETTINGS → Exit edit mode — устройство
#  запомнит это и дальше работает как обычно (пароли можно создать через Gen Pass).
# =====================================================================

import storage
import board
import digitalio
import microcontroller

NVM_EDIT_FLAG = 37        # те же номера, что в программе (src/passpuck.py)
NVM_SETUP_SKIPPED = 39
EDIT_FLAG_VALUE = 0xA5

btn_back = digitalio.DigitalInOut(board.GP6)
btn_back.direction = digitalio.Direction.INPUT
btn_back.pull = digitalio.Pull.UP
back_pressed = not btn_back.value
btn_back.deinit()

# Отметка «Edit mode» из меню — одноразовая: сразу стираем её,
# чтобы следующее включение снова было обычным.
edit_requested = microcontroller.nvm[NVM_EDIT_FLAG] == EDIT_FLAG_VALUE
if edit_requested:
    microcontroller.nvm[NVM_EDIT_FLAG] = 0



def no_passwords_yet():
    """True — паролей ещё нет совсем (новое устройство или файла passwords.py нет).
    Если файл сломан — False: тогда работаем как обычно, программа возьмёт резервную копию."""
    try:
        data = {}
        with open("/passwords.py") as f:
            exec(f.read(), data)
    except OSError as e:
        return e.errno == 2                 # 2 — файла нет
    except Exception:
        return False
    for group in ("AUTO_PASSWORDS", "MANUAL_PASSWORDS"):
        for value in data.get(group, {}).values():
            if value:
                return False
    return True


# Первую настройку можно пропустить: SETTINGS → Exit edit mode на новом устройстве —
# тогда пароли создаются прямо на нём (Gen Pass), и диск больше сам не открывается
setup_skipped = microcontroller.nvm[NVM_SETUP_SKIPPED] == EDIT_FLAG_VALUE
first_setup = (not back_pressed and not edit_requested and not setup_skipped
               and no_passwords_yet())

if not back_pressed and not edit_requested and not first_setup:  # обычный режим
    storage.disable_usb_drive()
    try:
        storage.remount("/", readonly=False)
    except Exception as e:
        print("Не удалось разрешить запись:", e)
elif first_setup:
    print("Первая настройка: паролей нет, диск открыт для PassPuck Editor.html")
else:
    print("Режим редактирования:", "кнопка «Назад»" if back_pressed else "из меню")
