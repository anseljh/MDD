# QT Py RP2040
import board
import analogio
import digitalio
from time import sleep

PHOTOCELL_MAX = 65535
THRESHOLD = 20
photocell = analogio.AnalogIn(board.A0)
uv_led = digitalio.DigitalInOut(board.A1)
uv_led.direction = digitalio.Direction.OUTPUT
uv_led.value = False
light_exists = None

print("Simple photocell test")

while True:
    photocell_percent = int(photocell.value / PHOTOCELL_MAX * 100)
    print(f"{photocell.value} / {photocell_percent}")

    if (photocell_percent < THRESHOLD):
        # it's dark. turn on the UV.
        uv_led.value = True
        if light_exists is True:
            print("Fiat UV!")
        light_exists = False
    else:
        # it's light.
        uv_led.value = False
        if light_exists is False:
            print("Fiat lux!")
        light_exists = True

    sleep(1)
