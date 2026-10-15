# PassPuck

Карманный аппаратный менеджер паролей на **Waveshare RP2040-Zero** и CircuitPython.
Компьютер видит его как обычную USB-клавиатуру: выберите профиль кнопками, нажмите «Ввод» — и устройство само наберёт пароль.

*English summary below.*

## Возможности

- 6 профилей паролей: 1–3 с генерацией пароля прямо на устройстве (латиницей или по-русски), 4–6 фиксированные
- Пароли на **латинице и по-русски** (раскладка Windows переключается автоматически)
- Автонажатие Enter, «Ctrl first» для экрана блокировки Windows
- Блокировка компьютера сочетанием кнопок (Win+L)
- **Jiggle** — не даёт компьютеру уснуть (курсор сдвигается на 1 пиксель и сразу обратно)
- Сон экрана: выключение или одна из 11 анимаций (Stars, Bounce, Rain, Eyes, Fireworks, Snake, Matrix, Pulse, Warp, Snow, Lock) либо Mix — анимации сменяют друг друга
- Яркость экрана и светодиода, заставка при включении, режим редактирования из меню
- **Редактор паролей** `PassPuck Editor.html` лежит прямо на устройстве: открывается в Edge/Chrome, без интернета
- Журнал `log.txt` для диагностики (без паролей), безопасное сохранение с резервной копией
- Все настройки — в понятном `settings.py` на устройстве

## Детали

| Деталь | Что именно |
|---|---|
| Плата | Waveshare RP2040-Zero |
| Экран | OLED 1.3″ I2C (SH1106) или 0.96″ (SSD1306), 4 контакта |
| Кнопки | 3 тактовые кнопки 6×6 мм |
| Корпус | `case/PassPuck_case_rp2040.3mf` для 3D-печати |

## Подключение

| Откуда | Куда на RP2040-Zero |
|---|---|
| Экран VDD / GND | 3V3 / GND |
| Экран SCL / SDA | GP5 / GP4 |
| Кнопки «Назад» / «Ввод» / «Вперёд» | GP6 / GP7 / GP8 (вторая ножка каждой — на GND) |

Подробные схемы пайки, распиновка экрана и кнопок — в [инструкции](docs/PassPuck-manual.pdf) ([тёмная версия](docs/PassPuck-manual-dark.pdf), [HTML](docs/manual.html)).

## Быстрый старт

Проще всего скачать готовый архив **PassPuck kit** со страницы [Releases](../../releases) — внутри всё ниже плюс инструкция.

1. Зажмите **BOOT** на плате и подключите USB — появится диск `RPI-RP2`.
2. Скопируйте на него файл из `firmware/` (CircuitPython 10.2.1). Плата перезагрузится и появится диск `CIRCUITPY`.
3. Скопируйте на `CIRCUITPY` всё содержимое папки `device/`. **`boot.py` — последним.**
4. Переподключите устройство без кнопок: заставка «PassPuck», затем главный экран.
5. Задайте пароли: на устройстве **SETTINGS → Edit mode**, затем на диске откройте `PassPuck Editor.html` в Edge или Chrome. После сохранения подождите 10 секунд и выберите **SETTINGS → Exit edit mode**.

**Обновление** работающего устройства: скопируйте всё из `device/`, **кроме `passwords.py` и `settings.py`** (в них ваши пароли и настройки). `boot.py` — последним.

### Настройка Windows (один раз на каждом компьютере)

Параметры → Время и язык → Ввод → Дополнительные параметры клавиатуры → Сочетания клавиш для языков ввода:
**английский — Ctrl+Shift+1, русский — Ctrl+Shift+2.**
Для пароля от входа в Windows скопируйте эти настройки на экран приветствия: `intl.cpl` → Дополнительно → Копировать параметры.
На Mac/Linux выберите на устройстве **SETTINGS → Layout: Off**.

## Структура репозитория

```
device/     всё, что копируется на диск CIRCUITPY:
            code.py (запуск), passpuck.mpy (программа), settings.py (настройки),
            passwords.py (пустой шаблон), PassPuck Editor.html, boot.py, fonts/, lib/
src/        passpuck.py — исходный код программы
tools/      build.ps1 — сборка src/passpuck.py → device/passpuck.mpy
firmware/   CircuitPython 10.2.1 для RP2040-Zero
case/       3D-модель корпуса
docs/       инструкция (PDF и HTML)
examples/   hardware_pins.py — если кнопки припаяны к другим контактам
```

## Изменение программы

Программа хранится на устройстве заранее собранной (`passpuck.mpy`) — так ей хватает памяти. Чтобы что-то поменять:

1. Отредактируйте `src/passpuck.py`.
2. Соберите: `powershell -ExecutionPolicy Bypass -File tools\build.ps1` — скрипт сам скачает официальную утилиту Adafruit `mpy-cross` 10.2.1 и проверит её контрольную сумму.
3. Скопируйте `device/passpuck.mpy` на устройство.

`passpuck.mpy` работает только на CircuitPython 10.x. На другой версии светодиод мигает красным «два коротких — пауза», а причина пишется в `log.txt`.

## Безопасность

Пароли хранятся во флеш-памяти устройства **открытым текстом**. Диск скрыт от компьютера, но любой, кто знает про режим редактирования, может их прочитать. Обращайтесь с устройством как с ключами.

**Не коммитьте свои пароли:** `device/passwords.py` в репозитории — пустой шаблон. Свои пароли храните только на устройстве.

## Лицензии

- Код и документация PassPuck — [MIT](LICENSE)
- CircuitPython и библиотеки Adafruit (`device/lib/`, `firmware/`) — MIT, © Adafruit Industries и авторы CircuitPython
- Шрифт Terminus (`device/fonts/`) — SIL Open Font License 1.1, © Dimitar Toshkov Zhekov

---

## English summary

**PassPuck** is a pocket hardware password manager built on a Waveshare RP2040-Zero running CircuitPython. It acts as a USB keyboard: pick a profile with the buttons, press Enter, and it types the password. Features: 6 profiles with on-device generation, Latin and Cyrillic passwords (automatic Windows layout switching via Ctrl+Shift+1/2), auto-Enter, Win+L lock, mouse jiggler, 11 sleep animations plus Mix, brightness settings, an offline browser-based password editor stored on the device itself, a diagnostic log, and all tunables in `settings.py`.

Quick start: flash `firmware/*.uf2` (hold BOOT while plugging in), copy `device/` to the `CIRCUITPY` drive (`boot.py` last), then edit passwords with `PassPuck Editor.html` from the device drive (SETTINGS → Edit mode). When updating, keep your `passwords.py` and `settings.py`. The program ships precompiled as `passpuck.mpy` (CircuitPython 10.x); the source is `src/passpuck.py`, rebuild with `tools/build.ps1`. The full manual (Russian) is in `docs/`.

Passwords are stored in plain text on the device flash. MIT licensed.
