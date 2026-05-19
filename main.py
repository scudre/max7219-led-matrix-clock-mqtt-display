#!/usr/bin/env python
# -*- coding: utf-8 -*-

# https://community.home-assistant.io/t/howto-use-temperature-from-weather-home-as-trigger/200260

import logging
import os
import signal
import time

from PIL import ImageFont
from dotenv import load_dotenv

from display import Display
from messageprovider import MessageProvider

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOUSE_ICON = [0x00007c5444281000]
AQI_DISPLAY_THRESHOLD = 60

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
STATUS_FONT = ImageFont.truetype(os.path.join(FONTS_DIR, 'MatrixLight6X.ttf'), 6)

HUMID_ICONS = [
    (70, 0x001c3e3e3e3e1c08),
    (40, 0x001c3e3e22361c08),
    (30, 0x001c3e2222361c08),
    (-1, 0x001c362222361c08),
]

WEATHER_ICONS = {
    'sunny'     : 0x9142183dbc184289,
    'foggy'     : 0x55aa55aa55aa55aa,
    'cloudy'    : 0x00007c8282621c00,
    'rainy'     : 0x152a7e818191710e,
    'snowy'     : 0xa542a51818a542a5,
    'tstorm'    : 0x0a04087e8191710e,
    'windy'     : 0x005f807f001f2010,
    'clear'     : 0x00184c0686268c18,
}

ANIMATED_WEATHER_ICONS = {
    'sunny': [
        0x1042183dbc184208,     # diagonal tips off
        0x9142183dbc184289,     # diagonal tips on (original)
    ],
    'clear': [
        0x00184c0686260c18,     # star A off
        0x00184c0686068c18,     # star B off
        0x00184c0606268c18,     # star C off
        0x00180c0686268c18,     # star D off
    ],
    'rainy': [
        0x002a007e818191710e,   # rain drops low
        0x152a7e818191710e,     # rain drops high
        0x0a54007e818191710e,   # rain drops shifted
    ],
    'tstorm': [
        0x0a04087e8191710e,     # lightning bolt left
        0x5020107e8191710e,     # lightning bolt right
    ],
    'foggy': [
        0x55aa55aa55aa55aa,     # fog pattern A
        0xaa55aa55aa55aa55,     # fog pattern B
    ],
    'windy': [
        0x025f807f021f2010,     # particles at x=1
        0x085f807f081f2010,     # particles at x=3
        0x205f807f201f2010,     # particles at x=5
        0x805f807f801f2010,     # particles at x=7
    ],
}

HA_WEATHER_MAP = {
    'clear-night'     : 'clear',
    'cloudy'          : 'cloudy',
    'fog'             : 'foggy',
    'hail'            : 'tstorm',
    'lightning'       : 'tstorm',
    'lightning-rainy' : 'tstorm',
    'partlycloudy'    : 'cloudy',
    'pouring'         : 'rainy',
    'rainy'           : 'rainy',
    'snowy'           : 'snowy',
    'snowy-rainy'     : 'snowy',
    'sunny'           : 'sunny',
    'windy'           : 'windy',
    'windy-variant'   : 'windy',
    'exceptional'     : 'sunny',
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def weather_icon(name):
    """Map a Home Assistant weather state to a list of icon frames.

    Returns animated frames if available, otherwise wraps the static
    icon in a single-element list.

    Args:
        name (str): A Home Assistant weather condition string (e.g. 'sunny', 'rainy').

    Returns:
        list: A list of hex bitmaps (one for static icons, multiple for animated).
    """
    key = HA_WEATHER_MAP.get(name, 'sunny')
    if key in ANIMATED_WEATHER_ICONS:
        return ANIMATED_WEATHER_ICONS[key]
    return [WEATHER_ICONS[key]]

def humid_icon(humidity_str):
    """Pick a humidity icon based on the humidity percentage.

    Args:
        humidity_str (str): Humidity value as a string (e.g. '65').

    Returns:
        list: Single-element list with the hex bitmap for the appropriate humidity level icon.
    """
    humidity = int(humidity_str) if humidity_str.isdigit() else 0
    return [next(bitmap for limit, bitmap in HUMID_ICONS if humidity > limit)]

def aqi_to_text(aqi):
    """Convert an AQI value to its human-readable category.

    Iterates from highest to lowest threshold and uses -1 for the lowest bound.

    Args:
        aqi (int): The Air Quality Index value.

    Returns:
        str: The human-readable name of the AQI category
            (e.g. 'Good', 'Moderate', 'Hazardous').
    """
    categories = [
        (300, 'Hazardous'),
        (200, 'Very Unhealthy'),
        (150, 'Unhealthy'),
        (100, 'Unhealthy for Sensitive Groups'),
        (50, 'Moderate'),
        (-1, 'Good'),
    ]
    return next(name for limit, name in categories if aqi > limit)

# ---------------------------------------------------------------------------
# Display screen helpers
# ---------------------------------------------------------------------------

def show_aqi(display, weather):
    """Display AQI as a scrolling message if current or forecast exceeds AQI_DISPLAY_THRESHOLD.

    Args:
        display (Display): The display instance to render to.
        weather (dict): Weather data containing 'curr_aqi' and 'for_aqi' keys.
    """
    curr_aqi = int(weather['curr_aqi']) if weather['curr_aqi'].isdigit() else 0
    for_aqi = int(weather['for_aqi']) if weather['for_aqi'].isdigit() else 0
    msg = ''
    if curr_aqi > AQI_DISPLAY_THRESHOLD:
        msg += f"AQI: {aqi_to_text(curr_aqi)} {curr_aqi}   "
    if for_aqi > AQI_DISPLAY_THRESHOLD:
        msg += f"Tmrrw AQI: {aqi_to_text(for_aqi)} {for_aqi}"
    if msg:
        display.scroll_message(msg, font=STATUS_FONT, scroll_delay=0.022)

def show_notifications(display, msg_provider):
    """Scroll through any non-weather MQTT notifications.

    Args:
        display (Display): The display instance to render to.
        msg_provider (MessageProvider): The MQTT message provider to read notifications from.
    """
    notifications = msg_provider.messages(filter_topics=['weather'])
    for msg in notifications:
        text = msg.get('notification', '')
        display.scroll_message(text, font=STATUS_FONT, scroll_delay=0.022)
        display.scroll_message(text, font=STATUS_FONT, scroll_delay=0.022)
    if notifications:
        time.sleep(1)

# ---------------------------------------------------------------------------
# Display screens
# ---------------------------------------------------------------------------

DISPLAY_SCREENS = [
    {
        'name': 'house_conditions',
        'render': lambda d, w: d.display_message(
            HOUSE_ICON, w['in_temp'],
            humid_icon(w['in_humid']), w['in_humid'],
        ),
    },
    {
        'name': 'current_weather',
        'render': lambda d, w: d.display_message(
            weather_icon(w['cond']), w['out_temp'],
            humid_icon(w['out_humid']), w['out_humid'],
        ),
    },
    {
        'name': 'forecast',
        'render': lambda d, w: d.display_message(
            weather_icon(w['for_cond']), w['for_temp'],
            first_offset=(0, 2),
        ),
    },
    {
        'name': 'aqi',
        'render': show_aqi,
    },
    {
        'name': 'clock',
        'render': lambda d, w: d.show_clock(),
    },
]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Application entry point.

    Initializes the LED matrix display, connects to MQTT, and continuously
    cycles through display screens (house conditions, current weather,
    forecast, AQI) until interrupted.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    # Load config
    load_dotenv('config.env')

    # Initialize display
    display = Display()

    # Start mqtt message subscription
    msg_provider = MessageProvider(
        host=os.environ['MQTT_HOST'],
        port=int(os.environ.get('MQTT_PORT', 1883)),
        username=os.environ['MQTT_USERNAME'],
        password=os.environ['MQTT_PASSWORD'],
    )
    msg_provider.loop_start()

    def exit_gracefully(sig, frame):
        log.info('Exiting...')
        msg_provider.loop_stop()
        exit(0)

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    log.info('Display started, waiting for MQTT data')

    while True:
        weather = msg_provider.message('weather')
        if not weather:
            if not msg_provider.connected:
                display.scroll_message("No Connection...", font=STATUS_FONT, scroll_delay=0.022)
            else:
                display.scroll_message("Weather Unavailable...", font=STATUS_FONT, scroll_delay=0.022)
            continue

        for screen in DISPLAY_SCREENS:
            screen['render'](display, weather)

        show_notifications(display, msg_provider)


if __name__ == "__main__":
    main()
