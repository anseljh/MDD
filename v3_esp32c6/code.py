import adafruit_connection_manager
import adafruit_ntp
import adafruit_requests
import analogio
import alarm
import board
import digitalio
import microcontroller
import rtc
import wifi

from adafruit_datetime import datetime, timedelta
from time import sleep, monotonic

# Constants
# SLEEP_DURATION = 5
# LIGHT_SLEEP = 1
# DEEP_SLEEP = 2
# SLEEP_MODE = LIGHT_SLEEP
TZ_NAME = "America/Los_Angeles"
SUNRISE_URL = f"https://api.sunrisesunset.io/json?lat=37.414223&lng=-122.132170&time_format=24&timezone={TZ_NAME}"
PHOTOCELL_MAX = 65535 # absolute
PHOTOCELL_THRESHOLD = 20 # percent

BANNER = """
----------------------------
Mouse Deterrent Device (MDD)
by Ansel Halliburton
for ESP32-C6
Powered by SunriseSunset.io
----------------------------
"""

# Init I/O
onboard_led = digitalio.DigitalInOut(microcontroller.pin.GPIO15)
onboard_led.direction = digitalio.Direction.OUTPUT
onboard_led.value = True # off
uv_led = digitalio.DigitalInOut(board.D1)
uv_led.direction = digitalio.Direction.OUTPUT
uv_led.value = False # off
requests = None
socket_pool = None
tz_offset = None # hours offset from UTC

def onboard_led_on():
        onboard_led.value = False

def onboard_led_off():
        onboard_led.value = True

def uv_on():
    uv_led.value = True

def uv_off():
    uv_led.value = False

def get_local_time_and_sun_data():
    global requests, socket_pool, tz_offset

    # Get approximate time from NTP, just to get the right date in this timezone
    ntp = adafruit_ntp.NTP(socket_pool, tz_offset=-7, cache_seconds=3600)
    approx_dt = rtc_to_datetime(ntp.datetime)
    approx_date_str = approx_dt.date().isoformat()
    print("Approx date: ", approx_date_str)

    # Get sunrise data 
    url = SUNRISE_URL + f"&date={approx_date_str}"
    today = requests.get(url).json()
    sunrise_today = datetime.fromisoformat(f"{today['results']['date']}T{today['results']['sunrise']}")
    sunset_today = datetime.fromisoformat(f"{today['results']['date']}T{today['results']['sunset']}")

    # determine tz_offset from sunrise data
    offset_minutes = today['results']['utc_offset']
    tz_offset = int(offset_minutes / 60)
    
    # Get correct local time from NTP, using TZ offset
    ntp = adafruit_ntp.NTP(socket_pool, tz_offset=tz_offset, cache_seconds=3600)
    ntp_now = ntp.datetime
    rtc.RTC().datetime = ntp_now
    now_dt = rtc_to_datetime(ntp_now)
    print("Local time: ", now_dt)
    
    print("-"*20)
    print(now_dt)
    print(sunrise_today)
    print(sunset_today)
    print("-"*20)

    return now_dt, sunrise_today, sunset_today

def get_sunrise_tomorrow():
    one_day = timedelta(days=1)
    now_dt = rtc_to_datetime(rtc.RTC().datetime)
    tomorrow_date = (now_dt + one_day).date()
    tomorrow = requests.get(SUNRISE_URL + f"&date={tomorrow_date.isoformat()}").json()
    sunrise_tomorrow = datetime.fromisoformat(f"{tomorrow['results']['date']}T{tomorrow['results']['sunrise']}")
    return sunrise_tomorrow


def rtc_to_datetime(rtc_time) -> datetime:
    dt = datetime(rtc_time.tm_year, rtc_time.tm_mon, rtc_time.tm_mday, rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec)
    return dt

def startup():
    global requests, socket_pool
    print(BANNER)
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

    # Blink LEDs 3X
    for x in range(3):
        onboard_led_on()
        uv_on()
        sleep(0.25)
        onboard_led_off()
        uv_off()
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
    print(now)
    print(f"UTC offset: {tz_offset} hours")
    print(f"Sunrise: {today_sunrise}")
    print(today_sunrise)
    print(f"Sunset: {today_sunset}")
    print(today_sunset)

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

    if light_now:
        # it's light out; UV off, deep sleep until sunset
        uv_off()
        until_sunset_delta = (today_sunset - now)
        print("Delta until sunset: ", until_sunset_delta)
        seconds_to_wait = until_sunset_delta.total_seconds()
        print(f"Will sleep deeply for {seconds_to_wait} seconds until sunset...")
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + seconds_to_wait)
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
        print("This won't print because the program will restart.")
    else:
        # it's light out; UV on, light sleep until sunrise
        uv_on()
        sunrise_tomorrow = get_sunrise_tomorrow()
        until_sunrise_delta = (sunrise_tomorrow - now)
        print("Delta until sunrise: ", until_sunrise_delta)
        seconds_to_wait = until_sunrise_delta.total_seconds()
        print(f"Will sleep lightly for {seconds_to_wait} seconds until sunrise...")
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + seconds_to_wait)
        alarm.light_sleep_until_alarms(time_alarm)

    print("Woke up!")
    onboard_led_on()
    sleep(1)
