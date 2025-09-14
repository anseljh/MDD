# Standard libraries
import alarm
import board
import digitalio
import microcontroller
import rtc
import wifi

# Additional CircuitPython libraries
import adafruit_connection_manager
import adafruit_ntp
import adafruit_requests
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError

# More standard libraries; partially imported
from adafruit_datetime import datetime, timedelta
from time import sleep, monotonic
from os import getenv

# Get settings from environment variables
# Set them in settings.toml!

TZ_NAME = getenv("TZ_NAME")
LATITUDE = getenv("LATITUDE")
LONGITUDE = getenv("LONGITUDE")

SUNRISE_URL = f"https://api.sunrisesunset.io/json?lat={LATITUDE}&lng={LONGITUDE}&time_format=24&timezone={TZ_NAME}"

AIO_USERNAME = getenv("ADAFRUIT_AIO_USERNAME")
AIO_KEY = getenv("ADAFRUIT_AIO_KEY")
FEED_NAME = "mdd-activity"
FEED_API_ENDPOINT = f"https://io.adafruit.com/api/v2/{AIO_USERNAME}/feeds/{FEED_NAME}"

BANNER = """
----------------------------
Mouse Deterrent Device (MDD)
by Ansel Halliburton
for Xiao ESP32-C6
Powered by SunriseSunset.io
----------------------------
"""

# Init I/O

onboard_led = digitalio.DigitalInOut(microcontroller.pin.GPIO15)
onboard_led.direction = digitalio.Direction.OUTPUT
onboard_led.value = True  # off
uv_led = digitalio.DigitalInOut(board.D0)
uv_led.direction = digitalio.Direction.OUTPUT
uv_led.value = False  # off
requests = None
socket_pool = None
io = None
tz_offset = None  # hours offset from UTC

# LED convenience functions


def onboard_led_on():
    onboard_led.value = False


def onboard_led_off():
    onboard_led.value = True


def uv_on():
    uv_led.value = True
    print("UV on!")


def uv_off():
    uv_led.value = False
    print("UV off")


# Time/date and sunrise/sunset functions


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
    sunrise_today = datetime.fromisoformat(
        f"{today['results']['date']}T{today['results']['sunrise']}"
    )
    sunset_today = datetime.fromisoformat(
        f"{today['results']['date']}T{today['results']['sunset']}"
    )

    # determine tz_offset from sunrise data
    offset_minutes = today["results"]["utc_offset"]
    tz_offset = int(offset_minutes / 60)

    # Get correct local time from NTP, using TZ offset
    ntp = adafruit_ntp.NTP(socket_pool, tz_offset=tz_offset, cache_seconds=3600)
    ntp_now = ntp.datetime
    rtc.RTC().datetime = ntp_now
    now_dt = rtc_to_datetime(ntp_now)
    print("Local time: ", now_dt)

    return now_dt, sunrise_today, sunset_today


def get_sunrise_tomorrow():
    one_day = timedelta(days=1)
    now_dt = rtc_to_datetime(rtc.RTC().datetime)
    tomorrow_date = (now_dt + one_day).date()
    tomorrow = requests.get(SUNRISE_URL + f"&date={tomorrow_date.isoformat()}").json()
    sunrise_tomorrow = datetime.fromisoformat(
        f"{tomorrow['results']['date']}T{tomorrow['results']['sunrise']}"
    )
    return sunrise_tomorrow


def rtc_to_datetime(rtc_time) -> datetime:
    dt = datetime(
        rtc_time.tm_year,
        rtc_time.tm_mon,
        rtc_time.tm_mday,
        rtc_time.tm_hour,
        rtc_time.tm_min,
        rtc_time.tm_sec,
    )
    return dt

def log_to_aio(message: str):
    global io, FEED_NAME
    if wifi.radio.connected:
        try:
            io.send_data(FEED_NAME, message)
        except AdafruitIO_RequestError as e:
            print("Failed to log to Adafruit IO: ", e)
            return False
        return True
    else:
        print("Can't log to AIO because not on WiFi")
        return False

#################################################


def startup():
    """
    Called when the board starts, or wakes from deep sleep.
    """
    global requests, socket_pool, io
    print(BANNER)
    print("Starting up...")

    # Print WiFi info
    if wifi.radio.connected:
        connected_msg = f"Connected to WiFi: {wifi.radio.ap_info.ssid}"
        print(connected_msg)
        socket_pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
        ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
        requests = adafruit_requests.Session(socket_pool, ssl_context)
        io = IO_HTTP(AIO_USERNAME, AIO_KEY, requests)
        # io.send_data(FEED_NAME, connected_msg)
        log_to_aio(connected_msg)
    else:
        print("Not connected to WiFi!")

    # Blink LEDs 3X
    print("Blinking LEDs...")
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
    log_to_aio("Top of main loop")
    onboard_led_off()
    uv_off()
    sleep(1)

    # Blink onboard LED once
    onboard_led_on()
    sleep(0.25)
    onboard_led_off()
    sleep(1)

    now, today_sunrise, today_sunset = get_local_time_and_sun_data()

    print(f"Current local time: {now}")
    print(f"UTC offset: {tz_offset} hours")
    print(f"Sunrise: {today_sunrise}")
    print(f"Sunset: {today_sunset}")

    light_now = None
    sleep_overnight = False

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
            sleep_overnight = True

    alt_light_now = (now > today_sunrise) and (now < today_sunset)
    print(f"light_now: {light_now}, alt_light_now: {alt_light_now}")
    
    if light_now:
        log_to_aio("Sun is up; UV off")
    else:
        log_to_aio("Sun is down; UV on")

    if light_now:
        # it's light out; UV off, deep sleep until sunset
        uv_off()
        until_sunset_delta = today_sunset - now
        print("Delta until sunset: ", until_sunset_delta)
        seconds_to_wait = until_sunset_delta.total_seconds()
        print(f"Will sleep deeply for {seconds_to_wait} seconds until sunset...")
        log_to_aio(f"Sleeping deeply for {seconds_to_wait} seconds until sunset")
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + seconds_to_wait)
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
        print("This won't print because the program will restart.")
    else:
        # it's dark out; UV on, light sleep until sunrise
        uv_on()
        until_sunrise_delta = None
        if sleep_overnight:
            # it's before midnight; use tomorrow's sunrise time
            sunrise_tomorrow = get_sunrise_tomorrow()
            until_sunrise_delta = sunrise_tomorrow - now
        else:
            # it's past midnight; don't check tomorrow's sunrise
            until_sunrise_delta = today_sunrise - now
        print("Delta until sunrise: ", until_sunrise_delta)
        seconds_to_wait = until_sunrise_delta.total_seconds()
        print(f"Will sleep lightly for {seconds_to_wait} seconds until sunrise...")
        log_to_aio(f"Sleeping lightly for {seconds_to_wait} seconds until sunrise")
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + seconds_to_wait)
        alarm.light_sleep_until_alarms(time_alarm)

    print("Woke up!")
    onboard_led_on()
    sleep(1)
