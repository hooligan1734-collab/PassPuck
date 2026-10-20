# PassPuck

Карманный аппаратный менеджер паролей на **Waveshare RP2040-Zero** и CircuitPython.
Компьютер видит его как обычную USB-клавиатуру: выберите профиль кнопками, нажмите «Ввод» — и устройство само наберёт пароль.

*English summary below.*

## Возможности

- 6 профилей паролей: 1–3 с генерацией пароля прямо на устройстве, 4–6 фиксированные
- Четыре вида генерации: **EN** и **RU** — случайные символы; **Words** и **Words RU** — запоминаемые пароли из двух коротких слов, цифр и символа (`Кот Луна 47!` → `RjnKeyf47!` или `КотЛуна47!`)
- Пароли на **латинице и по-русски** (раскладка Windows переключается автоматически)
- Крупное название профиля, значки его настроек, меню списком, листание удержанием кнопки, запоминание последнего профиля
- Автонажатие Enter, «Ctrl first» для экрана блокировки Windows
- Блокировка компьютера сочетанием кнопок (Win+L)
- **Пульт для музыки и видео** (включается в SETTINGS → Media): пауза, треки, громкость — работает в любом плеере, YouTube, Spotify
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

Скачайте со страницы [Releases](../../releases) файл **`PassPuck-2.3.uf2`** — в нём прошивка и все файлы сразу.

1. Зажмите **BOOT** на плате и подключите USB — появится диск `RPI-RP2` (совсем новая плата может открыть его и без кнопки).
2. Перетащите на него `PassPuck-2.3.uf2` и подождите около 30 секунд.
3. Устройство само откроется как диск `CIRCUITPY`, на экране — «PassPuck setup». Откройте на диске `PassPuck Editor.html` в Edge или Chrome, впишите пароли (или нажмите «Создать»), сохраните, подождите 10 секунд и переподключите устройство.
   Хотите создавать пароли прямо на устройстве — выберите вместо этого **SETTINGS → Exit edit mode**.
4. На каждом компьютере с Windows один раз запустите **`Настроить Windows.cmd`** (папка `windows/`, есть и в архиве PassPuck kit).

Пароли потом меняются так: **SETTINGS → Edit mode** (или подключить с зажатой «Назад») — снова появится диск с редактором.

**Обновление** работающего устройства (пароли сохранятся): откройте диск в режиме редактирования и скопируйте всё из `device/`, **кроме `passwords.py` и `settings.py`** (в них ваши пароли и настройки). `boot.py` — последним. Файл `hardware_pins.py`, если он есть, не удаляйте. **Не прошивайте** работающее устройство файлом `PassPuck-2.3.uf2` — он заменит пароли пустыми.

### Настройка Windows

`Настроить Windows.cmd` назначает сочетания **английский — Ctrl+Shift+1, русский — Ctrl+Shift+2** (через них PassPuck переключает раскладку) и по желанию копирует их на экран входа в Windows (спросит права администратора).
Вручную: Параметры → Время и язык → Ввод → Дополнительные параметры клавиатуры → Сочетания клавиш для языков ввода; для экрана входа — `intl.cpl` → Дополнительно → Копировать параметры.
На Mac/Linux выберите на устройстве **SETTINGS → Layout: Off**.

## Структура репозитория

```
device/     всё, что копируется на диск CIRCUITPY:
            code.py (запуск), passpuck.mpy (программа), settings.py (настройки),
            passwords.py (пустой шаблон), words.txt (словарь для паролей из слов),
            PassPuck Editor.html, boot.py, fonts/, lib/
src/        passpuck.py — исходный код программы
tools/      build.ps1 — сборка src/passpuck.py → device/passpuck.mpy
            make-image.ps1 — сборка установочного PassPuck-x.y.uf2 (прошивка + диск)
windows/    Настроить Windows.cmd — сочетания клавиш для языков
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

Установочный образ: запишите чистые файлы из `device/` на плату (пустой `passwords.py`!), затем `powershell -ExecutionPolicy Bypass -File tools\make-image.ps1 -Drive D: -Out PassPuck-x.y.uf2`. Скрипт читает диск платы целиком, затирает остатки удалённых файлов и ставит диск перед прошивкой (в обратном порядке загрузчик RP2040 не записывает вторую часть).

## Безопасность

Пароли хранятся во флеш-памяти устройства **открытым текстом**. Диск скрыт от компьютера, но любой, кто знает про режим редактирования, может их прочитать. Обращайтесь с устройством как с ключами.

**Не коммитьте свои пароли:** `device/passwords.py` в репозитории — пустой шаблон. Свои пароли храните только на устройстве.

## Лицензии

- Код и документация PassPuck — [MIT](LICENSE)
- CircuitPython и библиотеки Adafruit (`device/lib/`, `firmware/`) — MIT, © Adafruit Industries и авторы CircuitPython
- Шрифт Terminus (`device/fonts/`) — SIL Open Font License 1.1, © Dimitar Toshkov Zhekov

---

## English summary

**PassPuck** is a pocket hardware password manager built on a Waveshare RP2040-Zero running CircuitPython. It acts as a USB keyboard: pick a profile with the buttons, press Enter, and it types the password. Features: 6 profiles with on-device generation (random EN/RU or memorable two-word passwords typed in either layout), Latin and Cyrillic passwords (automatic Windows layout switching via Ctrl+Shift+1/2), auto-Enter, Win+L lock, optional media remote (play/pause, tracks, volume), mouse jiggler, 11 sleep animations plus Mix, list menus, brightness settings, an offline browser-based password editor stored on the device itself, a diagnostic log, and all tunables in `settings.py`.

Quick start: hold BOOT, plug in, drag the single `PassPuck-2.3.uf2` from Releases onto `RPI-RP2`. The device then opens its drive with `PassPuck Editor.html` for first-time setup. Run `windows/Настроить Windows.cmd` once per PC to set the language hotkeys. When updating an existing device, copy `device/` except `passwords.py` and `settings.py` (do not reflash the full image — it resets passwords). The program ships precompiled as `passpuck.mpy` (CircuitPython 10.x); the source is `src/passpuck.py`, rebuild with `tools/build.ps1`. The full manual (Russian) is in `docs/`.

Passwords are stored in plain text on the device flash. MIT licensed.
