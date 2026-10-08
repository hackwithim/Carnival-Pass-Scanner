import os
import io
import csv
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import fitz  # PyMuPDF

def get_dypcoei_students():
    """
    Extracts active DYPCOEI students directly from data.csv,
    strictly skipping removed or blank rows.
    """
    students = []
    source_file = 'data.csv'
    print(f"Reading students directly from: {source_file}...")

    with open(source_file, mode='r', encoding='utf-8-sig', errors='replace') as f:
        reader = list(csv.reader(f))

    in_dypcoei = False

    for idx, row in enumerate(reader):
        line_str = ' '.join(row)
        
        # Detect section start
        if 'DYPCOEI' in line_str:
            in_dypcoei = True
            continue

        if not in_dypcoei:
            continue

        # Non-empty row check
        name = row[0].strip() if len(row) > 0 else ''
        course = row[1].strip() if len(row) > 1 else ''
        sid = ''

        # Search for valid student ID
        for c in row[2:]:
            val = c.strip()
            if val:
                sid = val
                break

        if name and sid and name not in ('DYPIMED', 'DYPCOEI'):
            students.append({
                'row_index': idx + 1,
                'name': name.upper(),
                'course': course,
                'id': sid
            })

    print(f"Total active DYPCOEI students extracted: {len(students)}")
    return students

def create_pass_image(template_img, name, student_id, font_path, code128_class, writer):
    """
    Renders a single DYPCOEI festival pass.
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)

    center_x = 2412
    max_name_width = 1000

    # Dynamic font sizing for student name to avoid overflow
    font_size_name = 110
    font_name = ImageFont.truetype(font_path, font_size_name)
    bb = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)
    while (bb[2] - bb[0]) > max_name_width and font_size_name > 50:
        font_size_name -= 4
        font_name = ImageFont.truetype(font_path, font_size_name)
        bb = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)

    font_id = ImageFont.truetype(font_path, 130)

    # Position calculations
    bb_n = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)
    wn, hn = bb_n[2] - bb_n[0], bb_n[3] - bb_n[1]
    xn = center_x - wn // 2
    yn = 405 - hn // 2

    bb_i = draw.textbbox((0, 0), student_id, font=font_id, stroke_width=2)
    wi, hi = bb_i[2] - bb_i[0], bb_i[3] - bb_i[1]
    xi = center_x - wi // 2
    yi = 575 - hi // 2

    # Draw Name & ID
    draw.text((xn, yn), name, fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_name)
    draw.text((xi, yi), student_id, fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_id)

    # Generate barcode (Code 128)
    bc_opts = {
        'module_width': 0.45,
        'module_height': 15.0,
        'quiet_zone': 2.0,
        'font_size': 0,
        'text_distance': 0,
        'write_text': False
    }
    bc = code128_class(student_id, writer=writer)
    fp = io.BytesIO()
    bc.write(fp, options=bc_opts)
    fp.seek(0)
    bc_img = Image.open(fp).convert('RGB')

    # White box in template: [2007, 692, 2817, 852] (w=810, h=160)
    box_x1, box_y1, box_x2, box_y2 = 2007, 692, 2817, 852
    box_w = box_x2 - box_x1
    box_h = box_y2 - box_y1
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(255, 255, 255))

    bc_target_w = 660
    bc_target_h = 130
    bc_resized = bc_img.resize((bc_target_w, bc_target_h), Image.Resampling.NEAREST)

    bc_x = box_x1 + (box_w - bc_target_w) // 2
    bc_y = box_y1 + (box_h - bc_target_h) // 2

    pass_img.paste(bc_resized, (bc_x, bc_y))
    return pass_img

def main():
    template_path = 'DYPCOEI_Template.jpeg'
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    template_img = Image.open(template_path).convert('RGB')
    font_path = r'C:\Windows\Fonts\arialbd.ttf'
    if not os.path.exists(font_path):
        font_path = r'C:\Windows\Fonts\segoeuib.ttf'

    code128_class = barcode.get_barcode_class('code128')
    writer = ImageWriter()

    # 1. Extract DYPCOEI active students
    students = get_dypcoei_students()
    if not students:
        print("No DYPCOEI students found!")
        return

    # 2. Sample pass
    sample_first = students[0]
    sample_img = create_pass_image(template_img, sample_first['name'], sample_first['id'], font_path, code128_class, writer)
    sample_img.save('sample_pass_dypcoei.png')
    print(f"Sample pass saved: sample_pass_dypcoei.png for {sample_first['name']} ({sample_first['id']})")

    # 3. Generate Single Multi-page PDF (1 pass per page, 10x3 inch strip format)
    pdf_single_path = 'DYPCOEI_Passes.pdf'
    print(f"Generating {pdf_single_path} for {len(students)} students...")

    doc_single = fitz.open()
    strip_w, strip_h = 720, 216
    rect_single = fitz.Rect(0, 0, strip_w, strip_h)

    for i, s in enumerate(students):
        pass_img = create_pass_image(template_img, s['name'], s['id'], font_path, code128_class, writer)
        page = doc_single.new_page(width=strip_w, height=strip_h)
        buf = io.BytesIO()
        pass_img.save(buf, format='JPEG', quality=90)
        page.insert_image(rect_single, stream=buf.getvalue())

        if (i + 1) % 50 == 0 or (i + 1) == len(students):
            print(f"Processed {i + 1}/{len(students)} passes...")

    doc_single.save(pdf_single_path, deflate=True)
    doc_single.close()
    print(f"Successfully generated {pdf_single_path} (Pages: {len(students)}, Size: {os.path.getsize(pdf_single_path) / (1024*1024):.2f} MB)")

    # 4. Generate A4 Printable PDF (3 passes per A4 portrait page with cutting guides)
    pdf_a4_path = 'DYPCOEI_Passes_A4_Printable.pdf'
    print(f"Generating {pdf_a4_path} (3 passes per A4 page)...")

    doc_a4 = fitz.open()
    a4_w, a4_h = 595.28, 841.89
    pass_w = 555.0
    pass_h = pass_w * (900.0 / 3000.0)  # 166.5 pt
    margin_x = (a4_w - pass_w) / 2.0
    spacing_y = 60.0
    start_y = (a4_h - (3 * pass_h + 2 * spacing_y)) / 2.0

    current_page = None
    for i, s in enumerate(students):
        slot_idx = i % 3
        if slot_idx == 0:
            current_page = doc_a4.new_page(width=a4_w, height=a4_h)

        pass_img = create_pass_image(template_img, s['name'], s['id'], font_path, code128_class, writer)
        buf = io.BytesIO()
        pass_img.save(buf, format='JPEG', quality=90)

        slot_y = start_y + slot_idx * (pass_h + spacing_y)
        rect_slot = fitz.Rect(margin_x, slot_y, margin_x + pass_w, slot_y + pass_h)
        current_page.insert_image(rect_slot, stream=buf.getvalue())

        border_rect = fitz.Rect(margin_x - 0.5, slot_y - 0.5, margin_x + pass_w + 0.5, slot_y + pass_h + 0.5)
        current_page.draw_rect(border_rect, color=(0.8, 0.8, 0.8), width=0.5)

    doc_a4.save(pdf_a4_path, deflate=True)
    doc_a4.close()
    total_a4_pages = (len(students) + 2) // 3
    print(f"Successfully generated {pdf_a4_path} (Pages: {total_a4_pages}, Size: {os.path.getsize(pdf_a4_path) / (1024*1024):.2f} MB)")

    # 5. Render A4 Page 1 preview
    doc_preview = fitz.open(pdf_a4_path)
    page_preview = doc_preview[0]
    pix = page_preview.get_pixmap(dpi=150)
    pix.save('sample_a4_dypcoei_page1.png')
    doc_preview.close()
    print("A4 preview image updated: sample_a4_dypcoei_page1.png")

if __name__ == '__main__':
    main()
