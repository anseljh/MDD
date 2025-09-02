import alarm
import analogio
import board
import digitalio
import microcontroller
import wifi
from time import sleep, monotonic

# Constants
PHOTOCELL_MAX = 65535 # absolute
PHOTOCELL_THRESHOLD = 20 # percent
SLEEP_DURATION = 5

# Init I/O
photocell = analogio.AnalogIn(board.A0)
uv_led = digitalio.DigitalInOut(board.D1)
uv_led.direction = digitalio.Direction.OUTPUT
uv_led.value = False

onboard_led = digitalio.DigitalInOut(microcontroller.pin.GPIO15)
onboard_led.direction = digitalio.Direction.OUTPUT
onboard_led.value = True # true is off; false is on

#################################################

def read_photocell() -> int:
    return int(photocell.value / PHOTOCELL_MAX * 100)

def uv_on():
    uv_led.value = True

def uv_off():
    uv_led.value = False

def onboard_led_on():
        onboard_led.value = False

def onboard_led_off():
        onboard_led.value = True

def startup():
    print("Starting up...")

    # Print WiFi info
    if wifi.radio.connected:
        print(f"Connected to WiFi: {wifi.radio.ap_info.ssid}")
    else:
        print("Not connected to WiFi!")

    sleep(1)

    # Blink LEDs 3X
    for x in range(3):
        onboard_led_on()
        uv_on()
        sleep(0.25)
        onboard_led_off()
        uv_off()
        sleep(0.5)

#################################################

startup()

print("Entering main loop...")

while True:
    # main loop
    print("Top of main loop")

    # Are we at home?
    if wifi.radio.connected:
        print("At home.")
    else:
        print("Not at home.")

    # Read photocell   
    photocell_value = read_photocell()
    print(f"Photocell: {photocell_value}%")
    
    if (photocell_value < PHOTOCELL_THRESHOLD):
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

    print(f"Light sleep for {SLEEP_DURATION} seconds...")
    time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + SLEEP_DURATION)
    alarm.light_sleep_until_alarms(time_alarm)

    print("Woke up!")
    sleep(1)
