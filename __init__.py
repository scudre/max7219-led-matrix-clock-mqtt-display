#!/usr/bin/env python
# -*- coding: utf-8 -*-


# XXXXX
# https://community.home-assistant.io/t/howto-use-temperature-from-weather-home-as-trigger/200260


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
LONG_MSG_LEN = 11

weather = {
'sunny'     : 0x9142183dbc184289,
'foggy'     : 0x55aa55aa55aa55aa,
'cloudy'    : 0x00007e818999710e,
'rainy'     : 0x152a7e818191710e,
'snowy'     : 0xa542a51818a542a5,
'tstorm'    : 0x0a04087e8191710e,
'windy'     : 0x005f807f001f2010,
'clear'     : '',
}

ha_weather_map = {
    'clear-night'     : 'clear', 
    'cloudy'          : 'cloudy',
    'fog'             : 'foggy',
    'hail'            : 'tstorm'
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

def icon(draw, origin, icon_hex):
    points = []
    for y in range(8):
        row = (icon_hex >> y * 8) & 0xFF
        points.extend([(x+origin[0],y+origin[1]) for x in range(8) if (row >> x) & 0x1])

    draw.point(points, fill="white")

class HoursMinutes:
    def __init__(self):
        self.ts = datetime.now()
        self._set_hm()

    def next(self):
        self.ts = self.ts + timedelta(seconds=1)
        self._set_hm()
    
    def _set_hm(self):
        self.hours = self.ts.strftime('%H')
        self.minutes = self.ts.strftime('%M')


def cp437_encode(str):
   return [c.encode('cp437') for c in str]


def animation(device, from_y, to_y):
    """Animate the whole thing, moving it into/out of the abyss."""
    ts = now()
    current_y = from_y
    while current_y != to_y:
        draw_clock(device, ts, y_val=current_y)
        time.sleep(0.065)
        current_y += 1 if to_y > from_y else -1

def vertical_scroll(device, words):
    ts = now()
    messages = [" "] + words + [" "]
    virtual = viewport(device, width=device.width, height=len(messages) * 12)
    
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

def draw_clock_2(draw, ts, y_val=1, toggle=True):
    text(draw, (0, y_val), ts.hours, fill="white", font=CLOCK_FONT)
    text(draw, (15, y_val), ":" if toggle else " ", fill="white", font=proportional(TINY_FONT))
    text(draw, (17, y_val), ts.minutes, fill="white", font=CLOCK_FONT)
    #text(draw, (device.width - 2 * 8, 1), day_of_week(), fill="white", font=proportional(CLOCK_FONT))


def draw_clock(device, ts, y_val=1, toggle=True):
    with canvas(device) as draw:
        text(draw, (0, y_val), ts.hours, fill="white", font=CLOCK_FONT)
        text(draw, (15, y_val), ":" if toggle else " ", fill="white", font=proportional(TINY_FONT))
        text(draw, (17, y_val), ts.minutes, fill="white", font=CLOCK_FONT)
        #text(draw, (device.width - 2 * 8, 1), day_of_week(), fill="white", font=proportional(CLOCK_FONT))

def main():
    serial = spi(port=0, device=0, gpio=noop())
    # XXX make configurable
    device = max7219(serial, cascaded=4, block_orientation=90, blocks_arranged_in_reverse_order=True)
    device.contrast(0)
    
    msg = str(chr(177) * 8)
    #show_message(device, msg, fill="white", font=CP437_FONT)
    
    # Start mqtt message subscription
    msg_provider = MessageProvider(config)
    msg_provider.loop_start()
    
    # The time ascends from the abyss...
    if CLOCK_ENABLED:
        animation(device, 8, 1)
    
    toggle = False  # Toggle the second indicator every second
    count = 0
    while True:
        try:
            toggle = not toggle
            sec = datetime.now().second
            if sec == 59 and CLOCK_ENABLED:
                # When we change minutes, animate the minute change
                minute_change(device)
            elif sec == 10:
                today = date.today()
                #messages = [today.strftime("%2d.%2m.%4Y")] +
                #messages = [m for m in msg_provider.messages() if len(m) <= LONG_MSG_LEN]
                #print(msg_provider.messages())
                #vertical_scroll(device, messages)
            elif sec == 40:
                print('here')
                count = count+1
                today = date.today()
                long_messages = [ m for m in msg_provider.messages() if len(m) > LONG_MSG_LEN ]
                print(msg_provider.messages())
                if count == 10 and len(long_messages) > 0:
                    count = 0
                    messages = long_messages
                    #animation(device, 1, 8)
                    for full_msg in messages:
                       show_message(device, cp437_encode(full_msg), fill="white", font=proportional(CLOCK_FONT), scroll_delay=0.022)
                    #animation(device, 8, 1)
                    time.sleep(1)

            elif CLOCK_ENABLED:
                #device.clear()
                
                ts = now()
                draw_clock(device, ts, toggle=toggle)

                time.sleep(0.5)
            else:
                message = (msg_provider.messages() or [''])[0]
                with canvas(device) as draw:

                    val =  #weather['STORM'] #0x00003e2a22140800 #0x18187e247e241800 #0xff99998142241800
                    icon(draw, (0, 0), val)
                    #text(draw, (8, 0), '68', fill="white", font=proportional(TINY_FONT))
       
                    text(draw, (10, 0), message, fill="white", font=proportional(TINY_FONT))
                
        except KeyboardInterrupt:
            msg_provider.loop_stop()
            break


if __name__ == "__main__":
    main()
