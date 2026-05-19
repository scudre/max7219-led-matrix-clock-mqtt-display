#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys


def font_test():
    """Cycle through all TTF fonts in the fonts/ directory.

    For each font, displays a static centered '09:08 AM' for 5 seconds,
    then scrolls 'No Connection...' across the display.
    Loops forever until Ctrl+C.
    """
    import os
    import time
    from glob import glob
    from PIL import Image, ImageDraw, ImageFont
    from display import Display

    display = Display()
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    ttf_files = sorted(glob(os.path.join(fonts_dir, '*.ttf')))

    # Bitmap TTFs only support their native pixel size
    FONT_SIZES = {
        'MatrixChunky6.ttf':      6,
        'MatrixChunky6X.ttf':     6,
        'MatrixChunky8.ttf':      8,
        'MatrixChunky8X.ttf':     8,
        'MatrixLight6.ttf':       6,
        'MatrixLight6X.ttf':      6,
        'MatrixLight8.ttf':       8,
        'MatrixLight8X.ttf':      8,
        'Minecraftia-Regular.ttf': 8,
        'pixelmix.ttf':           8,
        'pixelmix_bold.ttf':      8,
    }

    clock_msg = "09:08 AM"
    scroll_msg = "No Connection..."

    while True:
        for ttf_path in ttf_files:
            font_name = os.path.basename(ttf_path)
            size = FONT_SIZES.get(font_name)
            if size:
                font = ImageFont.truetype(ttf_path, size)
            else:
                # Unknown font — try common sizes
                font = None
                for try_size in [6, 8, 10, 12]:
                    try:
                        font = ImageFont.truetype(ttf_path, try_size)
                        size = try_size
                        break
                    except OSError:
                        continue
                if font is None:
                    print(f"SKIP {font_name} (no valid size)")
                    continue

            # Auto-center vertically on the 8px display
            bbox = font.getbbox(clock_msg)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x_start = (display.device.width - text_w) // 2
            y_start = max(0, (display.device.height - text_h) // 2)

            print(f"{font_name} (size={size}, h={text_h}, y={y_start})")

            # Show static clock centered
            image = Image.new(display.device.mode, display.device.size, "black")
            draw = ImageDraw.Draw(image)
            draw.text((x_start, y_start), clock_msg, font=font, fill="white")
            display._push(image)
            time.sleep(5)

            # Scroll a message
            display.scroll_message(scroll_msg, font=font, scroll_delay=0.022,
                                   y_offset=y_start)


def message_test():
    """Preview status and AQI messages, plus a static clock, using STATUS_FONT.

    Loops forever until the process is killed (Ctrl+C).
    """
    import time
    from PIL import Image, ImageDraw
    from display import Display
    from main import STATUS_FONT

    display = Display()

    scroll_messages = [
        ("No Connection...", 0.022),
        ("Weather Unavailable...", 0.022),
        ("AQI: Moderate 85   Tmrrw AQI: Unhealthy 155", 0.022),
    ]

    clock_msg = "09:08 AM"

    while True:
        for msg, delay in scroll_messages:
            print(msg)
            display.scroll_message(msg, font=STATUS_FONT, scroll_delay=delay)
            time.sleep(1)

        # Show static clock centered
        print(clock_msg)
        bbox = STATUS_FONT.getbbox(clock_msg)
        text_w = bbox[2] - bbox[0]
        x_start = (display.device.width - text_w) // 2
        image = Image.new(display.device.mode, display.device.size, "black")
        draw = ImageDraw.Draw(image)
        draw.text((x_start, 1), clock_msg, font=STATUS_FONT, fill="white")
        display._push(image)
        time.sleep(5)


def dissolve_test():
    """Demo the dissolve transition between static screens."""
    import time
    from display import Display, icon
    from main import HOUSE_ICON, WEATHER_ICONS, HUMID_ICONS

    display = Display()

    # Build a few fake screens to dissolve between
    screens = [
        ('House conditions', lambda d: d.display_message(
            HOUSE_ICON, "72", [HUMID_ICONS[0][1]], "65", display_time=2,
        )),
        ('Current weather', lambda d: d.display_message(
            [WEATHER_ICONS['sunny']], "85", [HUMID_ICONS[1][1]], "40", display_time=2,
        )),
        ('Forecast', lambda d: d.display_message(
            [WEATHER_ICONS['rainy']], "68", first_offset=(0, 2), display_time=2,
        )),
        ('Back to house', lambda d: d.display_message(
            HOUSE_ICON, "72", [HUMID_ICONS[0][1]], "65", display_time=2,
        )),
        ('Cloudy weather', lambda d: d.display_message(
            [WEATHER_ICONS['cloudy']], "59", [HUMID_ICONS[2][1]], "30", display_time=2,
        )),
    ]

    print("Dissolve transition demo")
    print("First screen appears instantly, then dissolves between each screen")
    for name, render in screens:
        print(f"  {name}")
        render(display)


def weather_anim_test():
    """Preview animated weather icons on the display.

    Each weather type cycles its animation frames for a few seconds,
    with the name scrolled before each. Loops forever until Ctrl+C.
    """
    import time
    from PIL import Image, ImageDraw
    from display import Display, icon
    from main import WEATHER_ICONS, ANIMATED_WEATHER_ICONS

    display = Display()

    while True:
        for name, frames in ANIMATED_WEATHER_ICONS.items():
            print(name)

            # Animate: static original on left, animated on right
            static_icon = WEATHER_ICONS[name]
            frame_delay = 0.5
            elapsed = 0
            frame_idx = 0
            while elapsed < 10:
                image = Image.new(display.device.mode, display.device.size, "black")
                draw = ImageDraw.Draw(image)
                # Static original icon on the left
                icon(draw, (4, 0), static_icon)
                # Animated icon on the right
                icon(draw, (20, 0), frames[frame_idx % len(frames)])
                display.device.display(image)
                time.sleep(frame_delay)
                elapsed += frame_delay
                frame_idx += 1


from main import main

if __name__ == "__main__":
    test = sys.argv[1] if len(sys.argv) > 1 else None
    if test == "fonttest":
        font_test()
    elif test == "msgtest":
        message_test()
    elif test == "dissolve":
        dissolve_test()
    elif test == "weather":
        weather_anim_test()
    else:
        main()
