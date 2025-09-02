import adafruit_connection_manager
import adafruit_ntp
import adafruit_requests
import alarm
# import board
import digitalio
import microcontroller
import rtc
import wifi

from adafruit_datetime import datetime
from time import sleep, monotonic

# Constants
SLEEP_DURATION = 5
LIGHT_SLEEP = 1
DEEP_SLEEP = 2
SLEEP_MODE = LIGHT_SLEEP
SUNRISE_URL = "https://api.sunrisesunset.io/json?lat=37.414223&lng=-122.132170&time_format=24"

# Init I/O
onboard_led = digitalio.DigitalInOut(microcontroller.pin.GPIO15)
onboard_led.direction = digitalio.Direction.OUTPUT
onboard_led.value = False
requests = None
socket_pool = None
tz_offset = None # hours offset from UTC

def onboard_led_on():
        onboard_led.value = False

def onboard_led_off():
        onboard_led.value = True

# def get_time():
#     global socket_pool
#     ntp = adafruit_ntp.NTP(socket_pool, tz_offset=0, cache_seconds=3600)
#     now = ntp.datetime
#     rtc.RTC().datetime = now
#     print("UTC time: ", now)

def get_local_time_and_sun_data():
    global requests, socket_pool, tz_offset

    # Get sunrise data to determine tz_offset
    today = requests.get(SUNRISE_URL).json()
    offset_minutes = today['results']['utc_offset']
    sunrise_today = datetime.fromisoformat(f"{today['results']['date']}T{today['results']['sunrise']}")
    sunset_today = datetime.fromisoformat(f"{today['results']['date']}T{today['results']['sunset']}")
    tz_offset = int(offset_minutes / 60)
    
    # Get time from NTP, using TZ offset
    ntp = adafruit_ntp.NTP(socket_pool, tz_offset=tz_offset, cache_seconds=3600)
    ntp_now = ntp.datetime
    rtc.RTC().datetime = ntp_now
    now_dt = rtc_to_datetime(ntp_now)
    print("Local time: ", now_dt)

    return now_dt, sunrise_today, sunset_today


def rtc_to_datetime(rtc_time) -> datetime:
    dt = datetime(rtc_time.tm_year, rtc_time.tm_mon, rtc_time.tm_mday, rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec)
    return dt

def startup():
    global requests, socket_pool
    print("Starting up...")

    # Print WiFi info
    if wifi.radio.connected:
        print(f"Connected to WiFi: {wifi.radio.ap_info.ssid}")
        socket_pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        requests = adafruit_requests.Session(socket_pool, ssl_context)
        # get_time()
    else:
        print("Not connected to WiFi!")

    sleep(1)

    # Blink onboard LED 5X
    for x in range(5):
        onboard_led_on()
        sleep(0.25)
        onboard_led_off()
        sleep(0.25)


#################################################

startup()

print("Entering main loop...")

while True:
    # main loop
    print("Top of main loop")
    onboard_led_off()
    sleep(1)
    
    # Blink onboard LED once
    onboard_led_on()
    sleep(0.25)
    onboard_led_off()
    sleep(1)

    now, today_sunrise, today_sunset = get_local_time_and_sun_data()

    print("*"*20)

    print(f"Current local time: {now}")
    print(f"UTC offset: {tz_offset} hours")
    print(f"Sunrise: {today_sunrise}")
    print(f"Sunset: {today_sunset}")

    light_now = None

    if now < today_sunrise: 
        print("it's before today's sunrise")
        light_now = False
    else: 
        print("it's after today's sunrise")

        if now < today_sunset: 
            print("it's before today's sunset")
            light_now = True
        else: 
            print("it's after today's sunset")
            light_now = False
    
    alt_light_now = (now > today_sunrise) and (now < today_sunset)
    
    print(f"light_now: {light_now}, alt_light_now: {alt_light_now}")

    print("*"*20)

    time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + SLEEP_DURATION)
    if SLEEP_MODE == LIGHT_SLEEP:
        print(f"Light sleep for {SLEEP_DURATION} seconds...")
        onboard_led_on()
        alarm.light_sleep_until_alarms(time_alarm)
    elif SLEEP_MODE == DEEP_SLEEP:
        print(f"Deep sleep for {SLEEP_DURATION} seconds...")
        onboard_led_on()
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)

    print("Woke up!")
    sleep(1)
