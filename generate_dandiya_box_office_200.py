import os
import sys
import io
import shutil
from PIL import Image, ImageDraw, ImageFont
import qrcode
import barcode
from barcode.writer import ImageWriter
import fitz  # PyMuPDF
from tinydb import TinyDB, Query

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DANDIYAA_DIR = os.path.join(BASE_DIR, 'dandiyaa')
TEMPLATE_PATH = os.path.join(DANDIYAA_DIR, 'Pass_designs', 'BOX OFFICE PASS DANDIYA.jpg.jpeg')
PASSES_ARCHIVE_DIR = os.path.join(BASE_DIR, 'passes', 'dandiyaa')

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

def create_pass_qr_styled(template_img, pass_name, code_value, font_path):
    """
    Renders high-res Dandiya Box Office pass (3000x900) with a prominent 'PASS X' title,
    crisp QR code on the right, and 'SCAN FOR ENTRY / BOX OFFICE PASS' label.
    NO text 'DandiyaXXX' is written anywhere on the pass.
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)
    center_x = 2419

    # 1. Attendee Name (e.g. PASS 1) - centered vertically in the upper stub
    font_name = ImageFont.truetype(font_path, 130)
    bb_n = draw.textbbox((0, 0), pass_name.upper(), font=font_name, stroke_width=2)
    wn, hn = bb_n[2] - bb_n[0], bb_n[3] - bb_n[1]
    xn = center_x - wn // 2
    yn = 490 - hn // 2
    draw.text((xn, yn), pass_name.upper(), fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_name)

    # 2. QR Code inside the white box (encodes code_value invisibly in the QR pattern)
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(code_value)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    qr_h = 135
    qr_w = int(qr_img.width * (qr_h / qr_img.height))
    qr_resized = qr_img.resize((qr_w, qr_h), Image.Resampling.LANCZOS)

    box_x1 = 2125
    box_y = 754
    box_w = 580

    # Paste QR Code on right
    qr_x = box_x1 + box_w - qr_w - 20
    qr_y = box_y - qr_h // 2
    pass_img.paste(qr_resized, (qr_x, qr_y))

    # Badge text on left side of white box (NO DandiyaXXX text)
    font_lbl1 = ImageFont.truetype(font_path, 36)
    font_lbl2 = ImageFont.truetype(font_path, 32)
    draw.text((box_x1 + 35, box_y - 42), 'SCAN FOR ENTRY', fill=(20, 20, 30), font=font_lbl1)
    draw.text((box_x1 + 35, box_y + 8), 'BOX OFFICE PASS', fill=(100, 100, 110), font=font_lbl2)

    return pass_img

def create_pass_dual(template_img, pass_name, code_value, font_path, code128_class, writer):
    """
    Renders pass with BOTH 2D QR Code and 1D Code-128 Barcode side-by-side.
    NO text 'DandiyaXXX' is written on the pass.
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)
    center_x = 2419

    # 1. Name only (centered)
    font_name = ImageFont.truetype(font_path, 130)
    bb_n = draw.textbbox((0, 0), pass_name.upper(), font=font_name, stroke_width=2)
    wn, hn = bb_n[2] - bb_n[0], bb_n[3] - bb_n[1]
    draw.text((center_x - wn // 2, 490 - hn // 2), pass_name.upper(), fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_name)

    # QR Code on left
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(code_value)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    qr_h = 125
    qr_w = int(qr_img.width * (qr_h / qr_img.height))
    qr_resized = qr_img.resize((qr_w, qr_h), Image.Resampling.LANCZOS)

    # Barcode on right (no text printed underneath)
    bc = code128_class(code_value, writer=writer)
    fp = io.BytesIO()
    bc.write(fp, options={'module_width': 0.35, 'module_height': 12.0, 'quiet_zone': 1.0, 'font_size': 0, 'text_distance': 0, 'write_text': False})
    fp.seek(0)
    bc_img = Image.open(fp)
    bc_h = 120
    bc_w = min(410, int(bc_img.width * (bc_h / bc_img.height)))
    bc_resized = bc_img.resize((bc_w, bc_h), Image.Resampling.LANCZOS)

    box_x1 = 2125
    box_y = 754
    img_qr_x = box_x1 + 10
    img_qr_y = box_y - qr_h // 2
    pass_img.paste(qr_resized, (img_qr_x, img_qr_y))

    img_bc_x = box_x1 + qr_w + 35
    img_bc_y = box_y - bc_h // 2
    pass_img.paste(bc_resized, (img_bc_x, img_bc_y))

    return pass_img

def create_pass_barcode(template_img, pass_name, code_value, font_path, code128_class, writer):
    """
    Renders pass with standard full-width Code 128 barcode matching existing passes.
    NO text 'DandiyaXXX' is written on the pass.
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)
    center_x = 2419

    font_name = ImageFont.truetype(font_path, 130)
    bb_n = draw.textbbox((0, 0), pass_name.upper(), font=font_name, stroke_width=2)
    wn, hn = bb_n[2] - bb_n[0], bb_n[3] - bb_n[1]
    draw.text((center_x - wn // 2, 490 - hn // 2), pass_name.upper(), fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_name)

    bc = code128_class(code_value, writer=writer)
    fp = io.BytesIO()
    bc.write(fp, options={'module_width': 0.40, 'module_height': 14.0, 'quiet_zone': 2.0, 'font_size': 0, 'text_distance': 0, 'write_text': False})
    fp.seek(0)
    bc_img = Image.open(fp)

    box_w, box_h = 580, 135
    bw, bh = bc_img.size
    scale = min(box_w / bw, box_h / bh)
    new_bw, new_bh = max(1, int(bw * scale)), max(1, int(bh * scale))
    bc_resized = bc_img.resize((new_bw, new_bh), Image.Resampling.LANCZOS)

    paste_x = center_x - new_bw // 2
    paste_y = 754 - new_bh // 2
    pass_img.paste(bc_resized, (paste_x, paste_y))

    return pass_img

def build_pdf_documents(pass_images, pdf_a4_path, pdf_strip_path):
    """
    Builds both A4 Printable PDF (3 per page) and Single Strip PDF.
    """
    # 1. A4 Printable PDF
    doc_a4 = fitz.open()
    a4_w, a4_h = 595.28, 841.89  # pt
    pass_w = 555.0
    pass_h = pass_w * (900.0 / 3000.0)  # 166.5 pt
    margin_x = (a4_w - pass_w) / 2.0
    spacing_y = 60.0
    start_y = (a4_h - (3 * pass_h + 2 * spacing_y)) / 2.0

    current_page = None
    for i, img_bytes in enumerate(pass_images):
        slot_idx = i % 3
        if slot_idx == 0:
            current_page = doc_a4.new_page(width=a4_w, height=a4_h)

        slot_y = start_y + slot_idx * (pass_h + spacing_y)
        rect_slot = fitz.Rect(margin_x, slot_y, margin_x + pass_w, slot_y + pass_h)
        current_page.insert_image(rect_slot, stream=img_bytes)

        # Light cutting guideline
        border_rect = fitz.Rect(margin_x - 0.5, slot_y - 0.5, margin_x + pass_w + 0.5, slot_y + pass_h + 0.5)
        current_page.draw_rect(border_rect, color=(0.8, 0.8, 0.8), width=0.5)

    doc_a4.save(pdf_a4_path, deflate=True)
    doc_a4.close()

    # 2. Multi-Page Strip PDF
    doc_single = fitz.open()
    strip_w, strip_h = 720, 216
    rect_single = fitz.Rect(0, 0, strip_w, strip_h)

    for img_bytes in pass_images:
        page = doc_single.new_page(width=strip_w, height=strip_h)
        page.insert_image(rect_single, stream=img_bytes)

    doc_single.save(pdf_strip_path, deflate=True)
    doc_single.close()

def sync_records_to_databases(records):
    """
    Syncs the 200 Box Office passes into both dandiyaa/database.json and root database.json.
    Preserves existing status if passes already scanned.
    """
    db_paths = [
        os.path.join(DANDIYAA_DIR, 'database.json'),
        os.path.join(BASE_DIR, 'database.json')
    ]

    for path in db_paths:
        if not os.path.exists(path):
            continue
        db = TinyDB(path)
        students_table = db.table('students')
        existing = {str(s.get('barcode')).upper(): s for s in students_table.all()}

        new_items = []
        for r in records:
            b_up = r['barcode'].upper()
            if b_up not in existing:
                new_items.append(r)

        if new_items:
            students_table.insert_multiple(new_items)
            print(f"[DB Sync] Added {len(new_items)} new passes to {os.path.basename(os.path.dirname(path)) or 'root'}/{os.path.basename(path)}")
        else:
            print(f"[DB Sync] All {len(records)} passes already present in {path}")
        db.close()

def main():
    print("==================================================")
    print("RAAS DANDIYA & GARBA NIGHT 2026 — BOX OFFICE (200 PASSES)")
    print("Sequence: Pass 1 to Pass 200 (No 'DandiyaXXX' visible text)")
    print("==================================================")

    font_path = get_font_path()
    template_img = Image.open(TEMPLATE_PATH).convert('RGB')
    code128_class = barcode.get_barcode_class('code128')
    writer = ImageWriter()

    records = []
    for i in range(1, 201):
        p_name = f"Pass {i}"
        c_val = f"Dandiya{i:03d}"
        records.append({
            'name': p_name,
            'barcode': c_val,
            'college': 'BOX OFFICE',
            'division': 'BOX OFFICE',
            'roll_no': c_val,
            'status': 'PENDING',
            'entry_timestamp': None,
            'entry_date': None,
            'entry_time': None,
            'volunteer': None
        })

    # Render Pass Images
    print(f"\n[1/3] Rendering 200 passes with QR code (without visible 'DandiyaXXX' text)...")
    qr_images = []
    dual_images = []
    bc_images = []

    for idx, r in enumerate(records):
        # QR Code styled
        p_img_qr = create_pass_qr_styled(template_img, r['name'], r['barcode'], font_path)
        buf_qr = io.BytesIO()
        p_img_qr.save(buf_qr, format='JPEG', quality=90)
        qr_images.append(buf_qr.getvalue())

        # Dual QR + Barcode
        p_img_dual = create_pass_dual(template_img, r['name'], r['barcode'], font_path, code128_class, writer)
        buf_dual = io.BytesIO()
        p_img_dual.save(buf_dual, format='JPEG', quality=90)
        dual_images.append(buf_dual.getvalue())

        # Barcode only
        p_img_bc = create_pass_barcode(template_img, r['name'], r['barcode'], font_path, code128_class, writer)
        buf_bc = io.BytesIO()
        p_img_bc.save(buf_bc, format='JPEG', quality=90)
        bc_images.append(buf_bc.getvalue())

        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/200 passes...")

    # Save sample previews
    sample_qr = create_pass_qr_styled(template_img, 'Pass 1', 'Dandiya001', font_path)
    sample_qr.save(os.path.join(DANDIYAA_DIR, 'sample_box_office_qr.png'))
    sample_dual = create_pass_dual(template_img, 'Pass 1', 'Dandiya001', font_path, code128_class, writer)
    sample_dual.save(os.path.join(DANDIYAA_DIR, 'sample_box_office_dual.png'))
    sample_bc = create_pass_barcode(template_img, 'Pass 1', 'Dandiya001', font_path, code128_class, writer)
    sample_bc.save(os.path.join(DANDIYAA_DIR, 'sample_box_office_barcode.png'))

    # Build PDFs
    print(f"\n[2/3] Generating all-in-one PDF files...")
    # 1. Primary QR Code All-In-One PDF
    primary_pdf_a4 = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Passes_AllInOne.pdf')
    primary_pdf_strip = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Strip_Passes.pdf')
    build_pdf_documents(qr_images, primary_pdf_a4, primary_pdf_strip)
    print(f"  [OK] Generated Primary All-In-One PDF: {primary_pdf_a4} ({os.path.getsize(primary_pdf_a4)/(1024*1024):.2f} MB)")

    # 2. Dual QR + Barcode PDF
    dual_pdf_a4 = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Dual_A4.pdf')
    dual_pdf_strip = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Dual_Strip.pdf')
    build_pdf_documents(dual_images, dual_pdf_a4, dual_pdf_strip)
    print(f"  [OK] Generated Dual QR+Barcode PDF: {dual_pdf_a4} ({os.path.getsize(dual_pdf_a4)/(1024*1024):.2f} MB)")

    # 3. Barcode Only PDF
    bc_pdf_a4 = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Barcode_A4.pdf')
    bc_pdf_strip = os.path.join(DANDIYAA_DIR, 'BOX_OFFICE_Dandiya001_200_Barcode_Strip.pdf')
    build_pdf_documents(bc_images, bc_pdf_a4, bc_pdf_strip)
    print(f"  [OK] Generated Barcode Only PDF: {bc_pdf_a4} ({os.path.getsize(bc_pdf_a4)/(1024*1024):.2f} MB)")

    # Copy to passes/dandiyaa archive directory
    os.makedirs(PASSES_ARCHIVE_DIR, exist_ok=True)
    for p in [primary_pdf_a4, primary_pdf_strip, dual_pdf_a4, bc_pdf_a4]:
        shutil.copy2(p, os.path.join(PASSES_ARCHIVE_DIR, os.path.basename(p)))
    print(f"  [OK] Archived passes to {PASSES_ARCHIVE_DIR}")

    # Database sync
    print(f"\n[3/3] Synchronizing 200 passes with access control database...")
    sync_records_to_databases(records)

    print("\n==================================================")
    print("ALL 200 BOX OFFICE PASSES UPDATED SUCCESSFULLY (NO 'DANDIYAXXX' TEXT)!")
    print("==================================================")

if __name__ == '__main__':
    main()
