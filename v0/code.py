# QT Py RP2040

import board
import analogio

PHOTOCELL_MAX = 65535

print("Simple photocell test")

photocell = analogio.AnalogIn(board.A0)
print(photocell.value)

photocell_percent = int(photocell.value / PHOTOCELL_MAX * 100)
print(photocell.photocell_percent)

print("The end.")
