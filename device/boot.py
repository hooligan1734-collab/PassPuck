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
# =====================================================================

import storage
import board
import digitalio
import microcontroller

NVM_EDIT_FLAG = 37        # тот же номер, что в code.py
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

if not back_pressed and not edit_requested:  # обычный режим
    storage.disable_usb_drive()
    try:
        storage.remount("/", readonly=False)
    except Exception as e:
        print("Не удалось разрешить запись:", e)
else:
    print("Режим редактирования:", "кнопка «Назад»" if back_pressed else "из меню")
