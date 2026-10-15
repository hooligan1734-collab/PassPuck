# PassPuck — запуск программы.
# Сама программа лежит в passpuck.mpy (собрана заранее), настройки — в settings.py.
# Этот файл менять не нужно.

try:
    import passpuck
except Exception as e:
    # passpuck.mpy не загрузился. Частая причина — другая версия CircuitPython:
    # passpuck.mpy собран для CircuitPython 10.x (см. инструкцию, раздел «Прошивка»).
    import time
    import board
    import neopixel
    import storage
    message = "PassPuck: не удалось загрузить passpuck.mpy: " + repr(e)
    print(message)
    try:
        if not storage.getmount("/").readonly:
            with open("/log.txt", "a") as f:
                f.write(message + "\n")
    except Exception:
        pass
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=1.0)
    while True:                      # мигаем красным: два коротких — пауза
        for _ in range(2):
            pixel[0] = (255, 0, 0)
            time.sleep(0.15)
            pixel[0] = (0, 0, 0)
            time.sleep(0.15)
        time.sleep(1.0)

passpuck.run()
