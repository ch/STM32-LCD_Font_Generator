from PIL import Image, ImageFont, ImageDraw
import argparse
import math
import re
import time
import textwrap
import regex

# Greyscale threshold from 0 - 255
THRESHOLD = 128
# Font Character Set
CHAR_SET = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~'


def get_charset_perceived():
    # https://stackoverflow.com/questions/6805311/playing-around-with-devanagari-characters
    return regex.findall(r'\X', CHAR_SET)


def get_max_size(font):
    mw = 0
    mh = 0
    for ch in get_charset_perceived():
        left, top, right, bottom = font.getbbox(ch)
        if ch=='_':
            if right > mw:
                mw = right
            if (bottom-top) > mh:
                mh = bottom-top
        else:
            if right > mw:
                mw = right
            if bottom > mh:
                mh = bottom
    return mw, mh


def bin_to_c_hex_array(bin_text, bytes_per_line, lsb_padding=0, msb_padding=0):
    # create comment with preview of line
    comment = bin_text.replace('0', ' ').replace('1', '#')

    # pad the top or bottom remaining bits with 0's
    bin_text = ("0" * msb_padding) + bin_text + ("0" * lsb_padding)
    # ensure the length matches the number of bytes
    assert len(bin_text) == (bytes_per_line * 8)

    # split up into 8 digits each of bytes
    bin_list = re.findall('.{8}', bin_text)
    # convert to hex representation
    bin_list = map(lambda a: "0x{:02X}".format(int(a, 2)), bin_list)
    array = ', '.join(bin_list)

    return f'{array}, /* |{comment}| */\r\n'


def generate_font_data(font, x_size, y_size):
    data = ''

    # find bytes per line needed to fit the font width
    bytes_per_line = math.ceil(x_size / 8)

    # Output preview of font
    ll = len(get_charset_perceived())
    w = x_size*ll
    h = y_size

    size = [w, h]
    im = Image.new("RGB", size)
    drawer = ImageDraw.Draw(im)

    for i, ch in enumerate(get_charset_perceived()):
        left, top, right, bottom = font.getbbox(ch)
        x_start = i*x_size
        x_end = (i+1)*x_size

        f_start = x_start + (x_size - (right + left)) // 2
        drawer.text((f_start, 0), ch, font=font)

        # the starting array index of the current char
        array_offset = i * (bytes_per_line * y_size)
        assert data.count('0x') == array_offset

        # comment separator for each char
        data += '\r\n'
        data += f"// @{array_offset} '{ch}' ({font_width} pixels wide)\r\n"

        x_coordinates = range(x_start, (x_end-1))

        # for each row, convert to hex representation
        for y in range(y_size):
            # get list of row pixels
            pixels = map(lambda x: im.getpixel((x, y))[0], x_coordinates)
            # convert to bin text
            bin_text = map(lambda val: '1' if val > THRESHOLD else '0', pixels)
            bin_text = ''.join(bin_text)
            ll = len(bin_text)
            for s in range((x_size - ll) // 2):
                bin_text = '0' + bin_text + '0'
            ll = len(bin_text)
            if ll < x_size:
                bin_text = bin_text + '0'
            # convert to c-style hex array
            data += bin_to_c_hex_array(bin_text, bytes_per_line)

    return data
def output_preview(font, filename, x_size, y_size):

    # Output preview of font
    ll = len(get_charset_perceived())
    ascent, descent = font.getmetrics()
    w = x_size * ll
    h = y_size

    size = [w, h]
    im = Image.new("RGB", size)
    drawer = ImageDraw.Draw(im)

    for i, ch in enumerate(get_charset_perceived()):
        x_start = i * x_size
        x_end = (i + 1) * x_size
        drawer.rectangle([(x_start, 0), (x_end - 1, h - 1)], outline="red")
        left, top, right, bottom = font.getbbox(ch)
        drawer.rectangle([(x_start + left, top), (x_start + right, bottom)], outline="red")
    drawer.line([(0, ascent), (w, ascent)], fill="blue")

    for i, ch in enumerate(get_charset_perceived()):
        left, top, right, bottom = font.getbbox(ch)
        x_start = i * x_size
        x_end = (i + 1) * x_size

        f_start = x_start + (x_size - (right + left)) // 2
        drawer.text((f_start, 0), ch, font=font)

    im.save(f'{filename}.png')

def output_files(font, font_width, font_height, font_data, font_name):
    generated_time = time.strftime("%Y-%m-%d %H:%M:%S")

    # create filename, remove invalid chars
    filename = f'Font{font_name}{font_height}'
    filename = ''.join(c if c.isalnum() else '' for c in filename)

    # C file template
    output = f"""/**
 * This file provides '{font_name}' [{font_height}px] text font
 * for STM32xx-EVAL's LCD driver.
 *
 * Generated on {generated_time}
 */
#pragma once

#include "fonts.h"

//#define {filename}_Name ("{font_name} {font_height}px")

// {font_data.count('0x')} bytes
const uint8_t {filename}_Table [] = {{{font_data}}};

sFONT {filename} = {{
    {filename}_Table,
    {font_width}, /* Width */
    {font_height}, /* Height */
}};
"""
    # Output font C header file
    with open(f'{filename}.c', 'w') as f:
        f.write(output)

    output_preview(font, filename, font_width, font_height)

if __name__ == '__main__':
    # Command-line arguments
    parser = argparse.ArgumentParser(
        description='Generate text font for STM32xx-EVAL\'s LCD driver')

    parser.add_argument('-f', '--font',
                        type=str,
                        help='Font type [filename]',
                        required=True)
    parser.add_argument('-s', '--size',
                        type=int,
                        help='Font size in pixels [int]',
                        default=16,
                        required=False)
    parser.add_argument('-i', '--index',
                        type=str,
                        help='Typeface index',
                        required=False)
    parser.add_argument('-n', '--name',
                        type=str,
                        help='Custom font name [str]',
                        required=False)
    parser.add_argument('-c', '--charset',
                        type=str,
                        help='Custom charset from file [filename]',
                        required=False)
    args = parser.parse_args()

    if args.charset:
        with open(args.charset) as f:
            CHAR_SET = f.read().splitlines()[0]

    # create font type
    font_type = args.font
    font_height = args.size
    typeface_index = int(args.index) if args.index else 0

    myfont = ImageFont.truetype(font_type, size=font_height, index=typeface_index)
    font_width, font_height = get_max_size(myfont)

    if args.name:
        font_name = args.name
    else:
        font_name = myfont.font.family

    # generate the C file data
    font_data = generate_font_data(myfont, font_width, font_height)
    font_data = textwrap.indent(font_data, ' ' * 4)

    # output everything
    output_files(font=myfont,
                 font_width=font_width,
                 font_height=font_height,
                 font_data=font_data,
                 font_name=font_name)
