import os
import io
import time
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import fitz  # PyMuPDF
from tinydb import TinyDB, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, 'BOX_OFFICE.jpeg')
OUTPUT_PDF_A4 = os.path.join(BASE_DIR, 'BOX_OFFICE_Passes_A4_Printable.pdf')
OUTPUT_PDF_STRIP = os.path.join(BASE_DIR, 'BOX_OFFICE_Passes.pdf')
PREVIEW_SAMPLE = os.path.join(BASE_DIR, 'sample_box_office_pass.png')

TOTAL_PASSES = 1000
SERIES_PREFIX = 'CARNIVAL'

def get_font_path():
    candidates = [
        r'C:\Windows\Fonts\arialbd.ttf',
        r'C:\Windows\Fonts\segoeuib.ttf',
        r'C:\Windows\Fonts\calibrib.ttf'
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

def create_box_office_pass_image(template_img, serial_id, font_path, code128_class, writer):
    """
    Renders a single Box Office carnival pass on the template.
    Template size: 3000 x 900
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)

    center_x = 2460

    # 1. Header: 'BOX OFFICE'
    font_title = ImageFont.truetype(font_path, 88)
    title_text = 'BOX OFFICE'
    bb_t = draw.textbbox((0, 0), title_text, font=font_title)
    wt, ht = bb_t[2] - bb_t[0], bb_t[3] - bb_t[1]
    xt = center_x - wt // 2
    yt = 420 - ht // 2
    draw.text((xt, yt), title_text, fill=(20, 15, 30), font=font_title)

    # 2. Serial Number: 'Serial no. CARNIVAL0001'
    font_serial = ImageFont.truetype(font_path, 64)
    serial_text = f'Serial no. {serial_id}'
    bb_s = draw.textbbox((0, 0), serial_text, font=font_serial)
    ws, hs = bb_s[2] - bb_s[0], bb_s[3] - bb_s[1]
    xs = center_x - ws // 2
    ys = 545 - hs // 2
    draw.text((xs, ys), serial_text, fill=(160, 95, 10), font=font_serial)

    # 3. Barcode with serial_id (Code 128)
    bc = code128_class(serial_id, writer=writer)
    fp = io.BytesIO()
    bc.write(fp, options={
        'module_width': 0.40,
        'module_height': 14.0,
        'quiet_zone': 2.0,
        'font_size': 0,
        'text_distance': 0,
        'write_text': False
    })
    fp.seek(0)
    bc_img = Image.open(fp).convert('RGB')

    # White box with gold border for barcode
    box_w = 760
    box_h = 150
    box_x1 = center_x - box_w // 2
    box_y1 = 665
    box_x2 = box_x1 + box_w
    box_y2 = box_y1 + box_h
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(255, 255, 255), outline=(190, 150, 80), width=3)

    bc_target_w = 660
    bc_target_h = 120
    bc_resized = bc_img.resize((bc_target_w, bc_target_h), Image.Resampling.NEAREST)

    bc_x = box_x1 + (box_w - bc_target_w) // 2
    bc_y = box_y1 + (box_h - bc_target_h) // 2
    pass_img.paste(bc_resized, (bc_x, bc_y))

    return pass_img

def generate_passes():
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found at: {TEMPLATE_PATH}")

    template_img = Image.open(TEMPLATE_PATH).convert('RGB')
    font_path = get_font_path()
    code128_class = barcode.get_barcode_class('code128')
    writer = ImageWriter()

    print(f"Generating {TOTAL_PASSES} Box Office passes ({SERIES_PREFIX}0001 to {SERIES_PREFIX}{TOTAL_PASSES:04d})...")
    start_time = time.time()

    # 1. Save sample preview image
    sample_first = create_box_office_pass_image(template_img, f"{SERIES_PREFIX}0001", font_path, code128_class, writer)
    sample_first.save(PREVIEW_SAMPLE)
    print(f"Preview image saved: {PREVIEW_SAMPLE}")

    # 2. Generate A4 Printable PDF (3 passes per A4 portrait page)
    doc_a4 = fitz.open()
    a4_w, a4_h = 595.28, 841.89  # A4 in points (72 dpi)
    pass_w = 555.0
    pass_h = pass_w * (900.0 / 3000.0)  # 166.5 pt
    margin_x = (a4_w - pass_w) / 2.0
    spacing_y = 60.0
    start_y = (a4_h - (3 * pass_h + 2 * spacing_y)) / 2.0

    current_page = None

    for i in range(1, TOTAL_PASSES + 1):
        serial_id = f"{SERIES_PREFIX}{i:04d}"
        slot_idx = (i - 1) % 3

        if slot_idx == 0:
            current_page = doc_a4.new_page(width=a4_w, height=a4_h)

        pass_img = create_box_office_pass_image(template_img, serial_id, font_path, code128_class, writer)
        buf = io.BytesIO()
        pass_img.save(buf, format='JPEG', quality=88)

        slot_y = start_y + slot_idx * (pass_h + spacing_y)
        rect_slot = fitz.Rect(margin_x, slot_y, margin_x + pass_w, slot_y + pass_h)
        current_page.insert_image(rect_slot, stream=buf.getvalue())

        border_rect = fitz.Rect(margin_x - 0.5, slot_y - 0.5, margin_x + pass_w + 0.5, slot_y + pass_h + 0.5)
        current_page.draw_rect(border_rect, color=(0.85, 0.8, 0.7), width=0.5)

        if i % 100 == 0 or i == TOTAL_PASSES:
            print(f"Rendered {i}/{TOTAL_PASSES} passes into A4 printable document...")

    doc_a4.save(OUTPUT_PDF_A4, deflate=True)
    doc_a4.close()
    elapsed = time.time() - start_time
    a4_size_mb = os.path.getsize(OUTPUT_PDF_A4) / (1024 * 1024)
    total_pages = (TOTAL_PASSES + 2) // 3
    print(f"Successfully generated {OUTPUT_PDF_A4} ({total_pages} A4 pages, {a4_size_mb:.2f} MB in {elapsed:.1f}s)")

if __name__ == '__main__':
    generate_passes()
