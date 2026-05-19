import os
import random
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from luma.core.interface.serial import spi, noop
from luma.core.legacy import text
from luma.core.legacy.font import proportional, TINY_FONT
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.led_matrix.device import max7219

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
CLOCK_FONT = ImageFont.truetype(os.path.join(FONTS_DIR, 'MatrixChunky6X.ttf'), 6)
CLOCK_COLON_FONT = ImageFont.truetype(os.path.join(FONTS_DIR, 'pixelmix.ttf'), 6)
MSG_FONT = proportional(TINY_FONT)
DISPLAY_TIME = 8
ANIM_FRAME_DELAY = 0.5

# Pixel positions for icon + text layout on 32px wide display
FIRST_ICON_X = 0
FIRST_TEXT_X = 9
SECOND_ICON_X = 17
SECOND_TEXT_X = 24

# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------

def icon(draw, origin, icon_hex):
    """Render an 8x8 icon from a hex bitmap.

    Args:
        draw: A Pillow ImageDraw context from luma canvas.
        origin (tuple): The (x, y) pixel position of the icon's top-left corner.
        icon_hex (int): A 64-bit hex value encoding the 8x8 bitmap row by row.
    """
    points = []
    for y in range(8):
        row = (icon_hex >> y * 8) & 0xFF
        points.extend([(x+origin[0],y+origin[1]) for x in range(8) if (row >> x) & 0x1])
    draw.point(points, fill="white")

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

class Display:
    """Generic LED matrix display driver.

    Wraps the MAX7219 hardware and provides methods for rendering icons,
    text, scrolling messages, and animations. Knows nothing about the
    data being displayed — just how to display it.

    Attributes:
        device: The max7219 device instance (4 cascaded 8x8 modules, 32x8 pixels).
    """

    def __init__(self):
        serial = spi(port=0, device=0, gpio=noop())
        self.device = max7219(serial, cascaded=4, block_orientation=-90, blocks_arranged_in_reverse_order=False)
        self.device.contrast(0)
        self._last_frame = None

    def _push(self, image):
        """Display an image on the device and store it as the last frame.

        Args:
            image (PIL.Image): The image to display.
        """
        self.device.display(image)
        self._last_frame = image.copy()

    def dissolve(self, to_image, steps=20, delay=0.05):
        """Dissolve from the current display content to a new image.

        Randomly swaps pixels from the old frame to the new frame over
        several steps, creating a dissolve transition effect.

        Args:
            to_image (PIL.Image): The target image to dissolve into.
            steps (int): Number of transition frames.
            delay (float): Seconds between each transition frame.
        """
        from_image = self._last_frame or Image.new(self.device.mode, self.device.size, "black")

        pixels = [(x, y) for x in range(self.device.width) for y in range(self.device.height)]
        random.shuffle(pixels)

        chunk_size = len(pixels) // steps
        current = from_image.copy()
        current_px = current.load()
        to_px = to_image.load()

        for step in range(steps):
            start = step * chunk_size
            end = len(pixels) if step == steps - 1 else start + chunk_size
            for x, y in pixels[start:end]:
                current_px[x, y] = to_px[x, y]
            self.device.display(current)
            time.sleep(delay)

        self._push(to_image)

    def _build_frame(self, first_icon_hex, first_text, second_icon_hex=None, second_text=None, first_offset=(0,0), second_offset=(0,0), y_val=0):
        """Build a single display frame with icon/text pairs.

        Args:
            first_icon_hex (int): Hex bitmap for the first 8x8 icon.
            first_text (str): Text to display next to the first icon.
            second_icon_hex (int, optional): Hex bitmap for a second icon.
            second_text (str, optional): Text to display next to the second icon.
            first_offset (tuple): Pixel (x, y) offset for the first icon/text pair.
            second_offset (tuple): Pixel (x, y) offset for the second icon/text pair.
            y_val (int): Vertical pixel offset for the entire message.

        Returns:
            PIL.Image: The rendered frame.
        """
        image = Image.new(self.device.mode, self.device.size, "black")
        draw = ImageDraw.Draw(image)
        icon(draw, (FIRST_ICON_X + first_offset[0], y_val), first_icon_hex)
        text(draw, (FIRST_TEXT_X + first_offset[1], y_val), first_text, fill="white", font=MSG_FONT)
        if second_icon_hex and second_text:
            icon(draw, (SECOND_ICON_X + second_offset[0], y_val), second_icon_hex)
            text(draw, (SECOND_TEXT_X + second_offset[1], y_val), second_text, fill="white", font=MSG_FONT)
        return image

    def display_message(self, first_icon, first_text, second_icon=None, second_text=None, first_offset=(0,0), second_offset=(0,0), y_val=0, display_time=DISPLAY_TIME):
        """Show an icon + text pair (and optionally a second pair) on the display.

        Renders one or two icon/text combinations side by side, then holds
        for the specified duration. Icons are lists of hex bitmaps — a
        single-element list displays statically, multiple elements animate.

        Args:
            first_icon (list): List of hex bitmaps for the first 8x8 icon.
            first_text (str): Text to display next to the first icon.
            second_icon (list, optional): List of hex bitmaps for a second icon.
            second_text (str, optional): Text to display next to the second icon.
            first_offset (tuple): Pixel (x, y) offset for the first icon/text pair.
            second_offset (tuple): Pixel (x, y) offset for the second icon/text pair.
            y_val (int): Vertical pixel offset for the entire message.
            display_time (int): Seconds to hold the message. Defaults to DISPLAY_TIME.
        """

        second_icon_hex = second_icon[0] if second_icon else None

        # Show first frame with dissolve transition if applicable
        image = self._build_frame(first_icon[0], first_text, second_icon_hex, second_text, first_offset, second_offset, y_val)
        if self._last_frame is not None:
            self.dissolve(image)
        else:
            self._push(image)

        if len(first_icon) > 1:
            # Animate: cycle through icon frames for display_time
            elapsed = 0
            frame_idx = 1
            while elapsed < display_time:
                time.sleep(ANIM_FRAME_DELAY)
                elapsed += ANIM_FRAME_DELAY
                image = self._build_frame(first_icon[frame_idx % len(first_icon)], first_text, second_icon_hex, second_text, first_offset, second_offset, y_val)
                self._push(image)
                frame_idx += 1
        else:
            time.sleep(display_time)

    def scroll_message(self, msg, font, fill="white", scroll_delay=0.03, y_offset=1):
        """Scroll a message right-to-left using a Pillow TrueType font.

        Args:
            msg (str): The text message to scroll.
            font (PIL.ImageFont): A Pillow TrueType font instance.
            fill: The fill color to use (standard Pillow color name or RGB tuple).
            scroll_delay (float): Seconds to delay between each scroll step.
            y_offset (int): Vertical pixel offset for the text.
        """
        bbox = font.getbbox(msg)
        text_w = bbox[2] - bbox[0]

        total_w = text_w + self.device.width
        virtual = viewport(self.device, width=total_w + self.device.width, height=self.device.height)
        with canvas(virtual) as draw:
            draw.text((self.device.width, y_offset), msg, font=font, fill=fill)
        for i in range(total_w):
            virtual.set_position((i, 0))
            time.sleep(scroll_delay)
        self._last_frame = None

    def vertical_scroll(self, words=None):
        """Scroll a list of words vertically through the display.

        Each word is displayed for 10 seconds before scrolling to the next.

        Args:
            words (list, optional): List of strings to scroll. Defaults to placeholder values.
        """
        if words is None:
            words = ["foo", "bar", "bat", "bang"]
        messages = [" "] + words + [" "]
        virtual = viewport(self.device, width=self.device.width, height=len(messages) * 12)

        with canvas(virtual) as draw:
            for i, word in enumerate(messages):
                text(draw, (0, i * 12), word, fill="white", font=MSG_FONT)

        for i in range(virtual.height - 12):
            virtual.set_position((0, i))
            if i > 0 and i % 12 == 0:
                time.sleep(10)
            time.sleep(0.044)

    def transition(self, from_y, to_y, render_func):
        """Animate a render function by sliding it vertically.

        Args:
            from_y (int): Starting vertical pixel offset.
            to_y (int): Ending vertical pixel offset.
            render_func (callable): A function with signature (display, y_val)
                that renders a single frame.
        """
        current_y = from_y
        while current_y != to_y:
            render_func(self, current_y)
            time.sleep(0.065)
            current_y += 1 if to_y > from_y else -1

    def show_clock(self, display_time=DISPLAY_TIME, blink_interval=0.5):
        """Display the current time as HH:MM AM/PM with a blinking colon.

        Re-renders the time every blink_interval seconds, toggling the
        colon on and off, for a total of display_time seconds.

        Args:
            display_time (int): Total seconds to show the clock. Defaults to DISPLAY_TIME.
            blink_interval (float): Seconds between colon blink toggles.
        """
        x_hours = 1
        x_colon = 9
        x_min = 11
        x_ampm = 21
        y = 1

        colon_on = True
        elapsed = 0
        first_frame = True
        while elapsed < display_time:
            now = datetime.now()
            hours = now.strftime("%I")
            minutes = now.strftime("%M")
            ampm = now.strftime("%p")

            image = Image.new(self.device.mode, self.device.size, "black")
            draw = ImageDraw.Draw(image)
            draw.text((x_hours, y), hours, font=CLOCK_FONT, fill="white")
            if colon_on:
                draw.text((x_colon, y), ":", font=CLOCK_COLON_FONT, fill="white")
            draw.text((x_min, y), minutes, font=CLOCK_FONT, fill="white")
            draw.text((x_ampm, y), ampm, font=CLOCK_FONT, fill="white")

            if first_frame and self._last_frame is not None:
                self.dissolve(image)
                first_frame = False
            else:
                self._push(image)
            time.sleep(blink_interval)
            colon_on = not colon_on
            elapsed += blink_interval
