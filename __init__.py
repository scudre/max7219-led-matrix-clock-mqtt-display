#!/usr/bin/env python
# -*- coding: utf-8 -*-


# XXXXX
# https://community.home-assistant.io/t/howto-use-temperature-from-weather-home-as-trigger/200260

import signal
import time
from datetime import date
from datetime import datetime
from datetime import timedelta

from luma.core.interface.serial import spi, noop
from luma.core.legacy import text, show_message
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT, LCD_FONT
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.led_matrix.device import max7219

import config
from messageprovider import MessageProvider

CLOCK_ENABLED = False
CLOCK_FONT = proportional(TINY_FONT)
MSG_FONT = proportional(TINY_FONT)

# Replace with nice state class?
VALID_DISPLAY_VALUES = [
    'blank'
    'forecast',
    'current',
    'notifications'
    ]

weather = {
'sunny'     : 0x9142183dbc184289,
'foggy'     : 0x55aa55aa55aa55aa,
'cloudy'    : 0x00007c8282621c00,
'rainy'     : 0x152a7e818191710e,
'snowy'     : 0xa542a51818a542a5,
'tstorm'    : 0x0a04087e8191710e,
'windy'     : 0x005f807f001f2010,
'clear'     : 0x000c26034313460c,
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

class Display(object):
    def __init__(self, serial):
        self.device = max7219(serial, cascaded=4, block_orientation=-90, blocks_arranged_in_reverse_order=False)
        self.device.contrast(0)
        self._state = 'blank'
        #signal.signal(signal.SIGINT, self.exit_gracefully)
        #signal.signal(signal.SIGTERM, self.exit_gracefully)
        
    def state(self):
        return self._state
        
    def blank(self):
        return self._state == 'blank'
        
    def forecast(self):
        return self._state == 'forecast'
        
    def current(self):
        return self._state == 'current'
    
    def notifications(self):
        return self._state == 'notifications'

    

def weather_icon(name):
    mapping = ha_weather_map.get(name, 'sunny')
    return weather.get(mapping)

def icon(draw, origin, icon_hex):
    points = []
    for y in range(8):
        row = (icon_hex >> y * 8) & 0xFF
        points.extend([(x+origin[0],y+origin[1]) for x in range(8) if (row >> x) & 0x1])

    draw.point(points, fill="white")


def cp437_encode(str):
   return [c.encode('cp437') for c in str]


def animation(device, weather, from_y, to_y):
    """Animate the whole thing, moving it into/out of the abyss."""
    current_y = from_y
    while current_y != to_y:
        show_curr_weather(device, weather, current_y)
        time.sleep(0.065)
        current_y += 1 if to_y > from_y else -1


def transition(device, weather, from_y, to_y, display_func):
    """Animate the whole thing, moving it into/out of the abyss."""
    current_y = from_y
    while current_y != to_y:
        display_func(device, weather, current_y)
        time.sleep(0.065)
        current_y += 1 if to_y > from_y else -1

def vertical_scroll(device, words=["foo", "bar", "bat", "bang"]):
    messages = [" "] + words + [" "]
    virtual = viewport(device, width=device.width, height=len(messages) * 12)
    import pdb; pdb.set_trace()
    
    first_y_index = 0
    last_y_index = (len(messages) - 1) * 12
    
    with canvas(virtual) as draw:
        for i, word in enumerate(messages):
            text(draw, (0, i * 12), word, fill="white", font=MSG_FONT)
        
        if CLOCK_ENABLED:
            draw_clock_2(draw, ts, y_val=first_y_index)
            draw_clock_2(draw, ts, y_val=last_y_index)
    
    for i in range(virtual.height - 12):
        virtual.set_position((0, i))
        if i > 0 and i % 12 == 0:
            time.sleep(10)
        time.sleep(0.044)


def show_curr_weather(device, weather, y_val=0):
    with canvas(device) as draw:
        house = 0x00003e2a22140800
        icon(draw, (-1, y_val), house)
        text(draw, (6, y_val), weather.get('in_temp', '?'), fill="white", font=proportional(TINY_FONT))
        icon(draw, (15, y_val), weather_icon(weather.get('cond')))
        text(draw, (24, y_val), weather.get('out_temp', '?'), fill="white", font=proportional(TINY_FONT))

def draw_forecast(device, weather, y_val=0):
    with canvas(device) as draw:
        icon(draw, (0, y_val), weather_icon(weather.get('for_cond')))
        text(draw, (11, y_val), weather.get('for_temp', '?'), fill="white", font=proportional(TINY_FONT))

def show_forecast(device, weather, y_val=0):
    # XXX fix up animations -- use virtual canvas
    animation(device, weather, 0, 8)
    transition(device, weather, -8, 0, draw_forecast)

    draw_forecast(device, weather)

    time.sleep(40)
    transition(device, weather, 0, -8, draw_forecast)

    animation(device, weather, 8, 0)
    show_curr_weather(device, weather)


def show_notifications(device, msg_provider):
    #animation(device, 1, 8)
    for msg in msg_provider.messages(filter_topics=['weather']):
        show_message(device, cp437_encode(full_msg), fill="white", font=proportional(CLOCK_FONT), scroll_delay=0.022)
    #animation(device, 8, 1)
    time.sleep(1)

def main():
    serial = spi(port=0, device=0, gpio=noop())
    display = Display(serial)
    
    # Start mqtt message subscription
    msg_provider = MessageProvider(config)
    msg_provider.loop_start()
    
    #vertical_scroll(device)

    def exit_gracefully(signal, frame):
        print('stopping')
        msg_provider.loop_stop()
        exit(0)
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    
    print('okay lets go')
    while True:
        curr_time = datetime.now()
        #show_notifications(device, msg_provider)
        #after showing notifications, default to whatever curr screen should
        # show
         
        # update weather
        # can this be done keeping the old position
        # after updating weather -- based on time see if we need
        # to move position to show weather or forecast
        
        if curr_time.minute % 5 == 0:
            # XXX fix up animations -- use virtual canvas
            weather = msg_provider.message('weather')
            print('show forecast')
            print(weather)
            show_forecast(display.device, weather)
        else:
            print('current')
        
            weather = msg_provider.message('weather')
            print(weather)
            #check for notifications to display
            # pull from queue display twice?
            show_curr_weather(display.device, weather)
            
            display.current = True
            
        time.sleep(30)



if __name__ == "__main__":
    main()
