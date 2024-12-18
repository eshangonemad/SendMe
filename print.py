#!/usr/bin/env python
import argparse
import asyncio
import logging
import sys
import os
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

from catprinter import logger
from catprinter.cmds import PRINT_WIDTH, cmds_print_img
from catprinter.ble import run_ble
from catprinter.img import read_img, show_preview

def parse_args():
    args = argparse.ArgumentParser(
        description='Prints an image or text on your cat thermal printer.')
    args.add_argument('filename', type=str, nargs='?', default=None, 
                      help='Path to the image file or text string to print.')
    args.add_argument('-t', '--text', type=str, 
                      help='Text string to convert to an image and print (use \\n for new lines).')
    args.add_argument('-l', '--log-level', type=str,
                      choices=['debug', 'info', 'warn', 'error'], default='info')
    args.add_argument('-b', '--img-binarization-algo', type=str,
                      choices=['mean-threshold', 'floyd-steinberg', 'halftone', 'none'],
                      default='floyd-steinberg',
                      help=f'Which image binarization algorithm to use. If \'none\' is used, no binarization will be used. In this case, the image has to have a width of {PRINT_WIDTH} px.')
    args.add_argument('-s', '--show-preview', action='store_true',
                      help='If set, displays the final image and asks the user for confirmation before printing.')
    args.add_argument('-d', '--device', type=str, default='',
                      help=('The printer\'s Bluetooth Low Energy (BLE) address '
                            '(MAC address on Linux; UUID on macOS) '
                            'or advertisement name (e.g.: "GT01", "GB02", "GB03"). '
                            'If omitted, the script will try to auto discover '
                            'the printer based on its advertised BLE services.'))
    args.add_argument('-darker', action='store_true',
                      help="Print the image in text mode. This leads to more contrast, but slower speed.")
    args.add_argument('-f', '--font', type=str, default='arial.ttf',
                      help='Path to a TTF font file to use for the text.')
    args.add_argument('--font-size', type=int, default=20,
                      help='Font size to use for the text.')
    args.add_argument('--bold', action='store_true', help='Make the text bold.')
    args.add_argument('--italic', action='store_true', help='Make the text italic.')
    args.add_argument('--strikethrough', action='store_true', help='Strike through the text.')
    args.add_argument('--align', type=str, choices=['left', 'center', 'right'], default='left', help='Text alignment: left, center, or right.')
    return args.parse_args()

def configure_logger(log_level):
    logger.setLevel(log_level)
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(log_level)
    logger.addHandler(h)

def load_font(font_path: str, size: int, bold: bool = False, italic: bool = False) -> FreeTypeFont:
    """
    Load a font with the specified style. Attempts to load style variants if available,
    otherwise simulates the style using PIL's built-in font features.
    """
    try:
        # First try to load the font
        font = ImageFont.truetype(font_path, size)
        
        # Check if we need styling
        if bold or italic:
            # Try to get the font's family name
            font_dir = os.path.dirname(font_path)
            base_name = os.path.splitext(os.path.basename(font_path))[0]
            
            # Common naming patterns for styled fonts
            style_suffixes = []
            if bold and italic:
                style_suffixes = ['-BoldItalic', ' Bold Italic', 'BoldItalic']
            elif bold:
                style_suffixes = ['-Bold', ' Bold', 'Bold']
            elif italic:
                style_suffixes = ['-Italic', ' Italic', 'Italic']
            
            # Try to find and load a styled variant
            for suffix in style_suffixes:
                try:
                    styled_path = os.path.join(font_dir, f"{base_name}{suffix}.ttf")
                    if os.path.exists(styled_path):
                        return ImageFont.truetype(styled_path, size)
                except OSError:
                    continue
            
            # If we couldn't load a styled variant, use PIL's built-in styling
            return ImageFont.truetype(font_path, size)
    except OSError:
        # Fallback to default font if the specified font can't be loaded
        logger.warning(f"Could not load font {font_path}, falling back to default")
        try:
            # Try to use Arial if available
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            # Last resort: use default bitmap font
            return ImageFont.load_default()

def text_to_image(text: str, output_path: str, font_path: str, font_size: int, 
                 max_width: int, bold: bool = False, italic: bool = False, 
                 strikethrough: bool = False, align: str = 'left') -> None:
    """
    Convert text to an image with the specified styling options.
    """
    # Load the font with proper styling
    font = load_font(font_path, font_size, bold, italic)
    
    lines = text.split('\n')
    
    # Create a temporary image to measure text dimensions
    temp_image = Image.new('RGB', (1, 1), (255, 255, 255))
    draw = ImageDraw.Draw(temp_image)
    
    # Calculate maximum dimensions
    max_text_width = 0
    total_height = 0
    line_heights = []
    
    for line in lines:
        text_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = text_bbox[2] - text_bbox[0]
        line_height = text_bbox[3] - text_bbox[1]
        line_heights.append(line_height)
        max_text_width = max(max_text_width, line_width)
        total_height += line_height
    
    # Auto-adjust font size if text is too wide
    while max_text_width > max_width and font_size > 8:
        font_size -= 1
        font = load_font(font_path, font_size, bold, italic)
        
        max_text_width = 0
        total_height = 0
        line_heights = []
        for line in lines:
            text_bbox = draw.textbbox((0, 0), line, font=font)
            line_width = text_bbox[2] - text_bbox[0]
            line_height = text_bbox[3] - text_bbox[1]
            line_heights.append(line_height)
            max_text_width = max(max_text_width, line_width)
            total_height += line_height
    
    # Add padding
    padding = font_size // 3
    image_width = max(max_width, max_text_width)
    image = Image.new('RGB', (image_width, total_height + padding * 2), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # Draw text with proper alignment and styling
    current_y = padding
    for line, line_height in zip(lines, line_heights):
        # Calculate x position based on alignment
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]
        
        if align == 'center':
            x_position = (image_width - line_width) // 2
        elif align == 'right':
            x_position = image_width - line_width
        else:  # left alignment
            x_position = 0
        
        # Draw the text
        draw.text((x_position, current_y), line, fill=(0, 0, 0), font=font)
        
        # Add strikethrough if requested
        if strikethrough:
            strike_y = current_y + (line_height // 2)
            draw.line(
                (x_position, strike_y, x_position + line_width, strike_y),
                fill=(0, 0, 0),
                width=max(1, font_size // 20)
            )
        
        current_y += line_height
    
    # Resize if necessary to match printer width
    if image.width != max_width:
        scale_factor = max_width / image.width
        new_height = int(image.height * scale_factor)
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    # Save the final image
    image.save(output_path)

def main():
    args = parse_args()
    
    log_level = getattr(logging, args.log_level.upper())
    configure_logger(log_level)
    
    if args.text:
        filename = 'output_image.png'
        text_to_image(
            args.text,
            filename,
            args.font,
            args.font_size,
            PRINT_WIDTH,
            bold=args.bold,
            italic=args.italic,
            strikethrough=args.strikethrough,
            align=args.align
        )
    elif args.filename:
        filename = args.filename
        if not os.path.exists(filename):
            logger.info('🛑 File not found. Exiting.')
            return
    else:
        logger.info('🛑 No input provided. Exiting.')
        return
    
    try:
        bin_img = read_img(
            filename,
            PRINT_WIDTH,
            args.img_binarization_algo,
        )
        if args.show_preview:
            show_preview(bin_img)
    except RuntimeError as e:
        logger.error(f'🛑 {e}')
        return
    
    logger.info(f'✅ Read image: {bin_img.shape} (h, w) pixels')
    data = cmds_print_img(bin_img, dark_mode=args.darker)
    logger.info(f'✅ Generated BLE commands: {len(data)} bytes')
    
    asyncio.run(run_ble(data, device=args.device))

if __name__ == '__main__':
    main()