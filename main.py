#!/usr/bin/env python
# -*- coding: utf-8 -*-


# XXXXX
# https://community.home-assistant.io/t/howto-use-temperature-from-weather-home-as-trigger/200260

import logging
import signal
import time

from luma.core.interface.serial import spi, noop
from luma.core.legacy import text, show_message
from luma.core.legacy.font import proportional, TINY_FONT
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.led_matrix.device import max7219
from luma.core.sprite_system import framerate_regulator

import config
from messageprovider import MessageProvider

log = logging.getLogger(__name__)

CLOCK_FONT = proportional(TINY_FONT)
MSG_FONT = proportional(TINY_FONT)
DISPLAY_TIME = 8
HOUSE_ICON = 0x00007c5444281000
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

ha_weather_map = {
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

def show_message_icons(device, msg, y_offset=0, fill=None, font=None,
                 scroll_delay=0.03):
    """
    Scrolls a message right-to-left across the devices display.

    :param device: The device to scroll across.
    :param msg: The text message to display (must be ASCII only).
    :type msg: str
    :param y_offset: The row to use to display the text.
    :type y_offset: int
    :param fill: The fill color to use (standard Pillow color name or RGB
        tuple).
    :param font: The font (from :py:mod:`luma.core.legacy.font`) to use.
    :param scroll_delay: The number of seconds to delay between scrolling.
    :type scroll_delay: float
    """
    fps = 0 if scroll_delay == 0 else 1.0 / scroll_delay
    regulator = framerate_regulator(fps)
    with canvas(device) as draw:
        w, h = textsize(msg, font)

    x = device.width
    virtual = viewport(device, width=w + x + x, height=device.height)

    with canvas(virtual) as draw:
        text(draw, (x, y_offset), msg, font=font, fill=fill)

    i = 0
    while i <= w + x:
        with regulator:
            virtual.set_position((i, 0))
            i += 1


def vertical_scroll(device, words=None):
    if words is None:
        words = ["foo", "bar", "bat", "bang"]
    messages = [" "] + words + [" "]
    virtual = viewport(device, width=device.width, height=len(messages) * 12)

    with canvas(virtual) as draw:
        for i, word in enumerate(messages):
            text(draw, (0, i * 12), word, fill="white", font=MSG_FONT)

    for i in range(virtual.height - 12):
        virtual.set_position((0, i))
        if i > 0 and i % 12 == 0:
            time.sleep(10)
        time.sleep(0.044)


class Display:
    def __init__(self):
        serial = spi(port=0, device=0, gpio=noop())
        self.device = max7219(serial, cascaded=4, block_orientation=-90, blocks_arranged_in_reverse_order=False)
        self.device.contrast(0)
        

def humid_icon(humidity_str):
    humidity = int(humidity_str) if humidity_str.isdigit() else 0
    return next(icon for limit, icon in HUMID_ICONS if humidity > limit)

def aqi_to_text(aqi):
    """
    Converts an AQI value to its human-readable category using a tuple-based approach.
    Iterates from highest to lowest threshold and uses -1 for the lowest bound.
    
    Parameters:
        aqi (int): The Air Quality Index value.
        
    Returns:
        str: The human-readable name of the AQI category.
    """
    categories = [
        (300, 'Hazardous'),
        (200, 'Very Unhealthy'),
        (150, 'Unhealthy'),
        (100, 'Unhealthy for Sensitive Groups'),
        (50, 'Moderate'),
        (-1, 'Good'),  # Use -1 to cover all AQI starting at 0
    ]
    
    return next(name for limit, name in categories if aqi > limit)

def weather_icon(name):
    return WEATHER_ICONS.get(ha_weather_map.get(name, 'sunny'))

def icon(draw, origin, icon_hex):
    points = []
    for y in range(8):
        row = (icon_hex >> y * 8) & 0xFF
        points.extend([(x+origin[0],y+origin[1]) for x in range(8) if (row >> x) & 0x1])

    draw.point(points, fill="white")

def cp437_encode(str):
   return [c.encode('cp437') for c in str]

def transition(device, weather, from_y, to_y, display_func):
    """Animate the whole thing, moving it into/out of the abyss."""
    current_y = from_y
    while current_y != to_y:
        display_func(device, weather, current_y)
        time.sleep(0.065)
        current_y += 1 if to_y > from_y else -1

def display_message(device, first_icon, first_text, second_icon=None, second_text=None, first_offset=(0,0), second_offset=(0,0), y_val=0):
    with canvas(device) as draw:
        icon(draw, (0 + first_offset[0], y_val), first_icon)
        text(draw, (9 + first_offset[1], y_val), first_text, fill="white", font=MSG_FONT)
        if second_icon and second_text:
            icon(draw, (17 + second_offset[0], y_val), second_icon)
            text(draw, (24 + second_offset[1], y_val), second_text, fill="white", font=MSG_FONT)
    time.sleep(DISPLAY_TIME)



def show_aqi(device, weather, y_val=0):
    curr_aqi = int(weather['curr_aqi']) if weather['curr_aqi'].isdigit() else 0
    for_aqi = int(weather['for_aqi']) if weather['for_aqi'].isdigit() else 0
    msg = ''
    if curr_aqi > 60:
        msg += "AQI: {0} {1}   ".format(aqi_to_text(curr_aqi), curr_aqi)
    if for_aqi > 60:
        msg += "Tmrrw AQI: {0} {1}".format(aqi_to_text(for_aqi), for_aqi)
        
    if msg:
        show_message(device, msg, fill="white", font=MSG_FONT, scroll_delay=0.05)
        time.sleep(0)


def show_notifications(device, msg_provider):
    for msg in msg_provider.messages(filter_topics=['weather']):
        full_msg = "{}: {}".format(msg.get('name', ''), msg.get('value', ''))
        show_message(device, cp437_encode(full_msg), fill="white", font=MSG_FONT, scroll_delay=0.022)
    time.sleep(1)


def show_house_cond(device, weather, y_val=0):
    humidity = weather['in_humid']
    display_message(device, HOUSE_ICON, weather['in_temp'], humid_icon(humidity), humidity)

def show_curr_weather(device, weather, y_val=0):
    humidity = weather['out_humid']
    display_message(device, weather_icon(weather['cond']), weather['out_temp'], humid_icon(humidity), humidity)

def show_forecast(device, weather, y_val=0):
    display_message(device, weather_icon(weather['for_cond']), weather['for_temp'], first_offset=(0,2))

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    # Initialize display
    display = Display()

    # Start mqtt message subscription
    msg_provider = MessageProvider(config)
    msg_provider.loop_start()

    def exit_gracefully(sig, frame):
        log.info('Exiting...')
        msg_provider.loop_stop()
        exit(0)

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    log.info('Display started, waiting for MQTT data')
    time.sleep(0.5)
    while True:
        weather = msg_provider.message('weather')
        if not weather:
            show_message(display.device, "WAITING FOR DATA...", fill="white", font=MSG_FONT, scroll_delay=0.022)
            continue
            
        display_funcs = [
            show_house_cond,
            show_curr_weather,
            show_forecast,
            show_aqi,
            ]
        
        for item in display_funcs: item(display.device, weather)
        
        



if __name__ == "__main__":
    main()
