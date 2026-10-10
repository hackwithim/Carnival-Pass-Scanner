import os
import io
import csv
import shutil
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import fitz  # PyMuPDF
from tinydb import TinyDB, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Day2_Passes')
PASSES_COPY_DIR = os.path.join(BASE_DIR, 'passes', 'Day2_Passes')

# Ensure DYPSOA template is linked to the user-provided template
dypsoa_template = os.path.join(BASE_DIR, 'DYPSOA_template.jpeg')
if not os.path.exists(dypsoa_template):
    dypsoa_template = os.path.join(BASE_DIR, 'DYPSOA_Template.jpeg')

# Sync to templates directory if present
templates_dir_soa = os.path.join(BASE_DIR, 'templates', 'DYPSOA_Template.jpeg')
if os.path.exists(dypsoa_template) and os.path.exists(os.path.join(BASE_DIR, 'templates')):
    shutil.copy2(dypsoa_template, templates_dir_soa)

TEMPLATES = {
    'DYPIMED': os.path.join(BASE_DIR, 'DYPIMED_Template.jpeg'),
    'DYPTC': os.path.join(BASE_DIR, 'DYPTC_Template.jpeg'),
    'DYPCOEI': os.path.join(BASE_DIR, 'DYPCOEI_Template.jpeg'),
    'DYPSOA': dypsoa_template
}

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

def create_pass_image(template_img, name, student_id, font_path, code128_class, writer):
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
    bc_img = Image.open(fp)

    # White box target: center=(2412, 765), max size=(824, 170)
    box_w = 824
    box_h = 170
    box_center_x = 2412
    box_center_y = 765

    bw, bh = bc_img.size
    scale = min(box_w / bw, box_h / bh)
    new_bw = max(1, int(bw * scale))
    new_bh = max(1, int(bh * scale))
    bc_resized = bc_img.resize((new_bw, new_bh), Image.Resampling.LANCZOS)

    paste_x = box_center_x - new_bw // 2
    paste_y = box_center_y - new_bh // 2
    pass_img.paste(bc_resized, (paste_x, paste_y))

    return pass_img

def load_day2_records():
    """
    Parses DAY2.csv and returns raw student records categorized by college.
    """
    day2_csv = os.path.join(BASE_DIR, 'DAY2.csv')
    with open(day2_csv, mode='r', encoding='utf-8-sig', errors='replace') as f:
        rows = list(csv.reader(f))

    current_col = 'UNKNOWN'
    records = []

    for idx, r in enumerate(rows):
        line = ' '.join(r).upper()
        for col in ['DYPIMED', 'DYPTC', 'DYPCOEI', 'DYPSOA']:
            if col in line and len([x for x in r if x.strip()]) <= 2:
                current_col = col

        if len(r) < 4:
            continue

        name = r[1].strip()
        div = r[2].strip()
        sid = r[3].strip()

        # Skip headers / separators
        if not name or not sid:
            continue
        if name.upper() in ('POLYTECHNIC', 'BOX OFFICE'):
            continue

        records.append({
            'college': current_col,
            'row_idx': idx + 1,
            'name': name.upper(),
            'division': div,
            'id': sid,
            'barcode': sid.replace(' ', '').upper()
        })

    return records

def get_already_generated_students(db_path):
    """
    Finds students who already have passes generated from Day 1.
    """
    db = TinyDB(db_path)
    day1_students = db.table('students').all()
    db.close()

    # Known students from Day 1 whose passes are in DYPCOEI_Passes.pdf, etc.
    # Map by (college, barcode) and (college, exact_name)
    already_gen = {}
    for s in day1_students:
        c = s.get('college')
        bc = s.get('barcode', '').strip().upper()
        nm = s.get('name', '').strip().upper()
        if c and bc:
            already_gen[(c, bc)] = s
        if c and nm and len(nm) > 5:
            already_gen[(c, nm)] = s

    return already_gen

def generate_passes_for_college(college, students, template_path, font_path, code128_class, writer):
    if not students:
        print(f"[{college}] No new passes to generate.")
        return

    college_dir = os.path.join(OUTPUT_DIR, college)
    os.makedirs(college_dir, exist_ok=True)
    passes_copy_sub = os.path.join(PASSES_COPY_DIR, college)
    os.makedirs(passes_copy_sub, exist_ok=True)

    template_img = Image.open(template_path).convert('RGB')

    # 1. Multi-page Strip PDF (10x3 inch, 720x216 pt)
    pdf_single_path = os.path.join(college_dir, f"{college}_Passes.pdf")
    print(f"[{college}] Generating {pdf_single_path} for {len(students)} students...")

    doc_single = fitz.open()
    strip_w, strip_h = 720, 216
    rect_single = fitz.Rect(0, 0, strip_w, strip_h)

    for i, s in enumerate(students):
        pass_img = create_pass_image(template_img, s['name'], s['id'], font_path, code128_class, writer)
        page = doc_single.new_page(width=strip_w, height=strip_h)
        buf = io.BytesIO()
        pass_img.save(buf, format='JPEG', quality=90)
        page.insert_image(rect_single, stream=buf.getvalue())

    doc_single.save(pdf_single_path, deflate=True)
    doc_single.close()
    shutil.copy2(pdf_single_path, os.path.join(passes_copy_sub, f"{college}_Passes.pdf"))
    print(f"[{college}] Strip PDF complete ({len(students)} passes).")

    # 2. Printable A4 PDF (3 passes per page)
    pdf_a4_path = os.path.join(college_dir, f"{college}_Passes_A4_Printable.pdf")
    print(f"[{college}] Generating {pdf_a4_path} (A4 3-passes-per-page)...")

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
    shutil.copy2(pdf_a4_path, os.path.join(passes_copy_sub, f"{college}_Passes_A4_Printable.pdf"))
    print(f"[{college}] Printable A4 PDF complete ({(len(students) + 2) // 3} pages).")

def sync_centralized_database(day2_records):
    """
    Updates database.json with DAY2 records:
    - If student already existed, enhances name if more complete, preserves entry status.
    - If student is new, inserts them with status PENDING.
    """
    db_path = os.path.join(BASE_DIR, 'database.json')
    db = TinyDB(db_path)
    students_table = db.table('students')

    existing_students = students_table.all()
    # Index existing by (college, barcode) and (college, roll_no)
    existing_map = {}
    for s in existing_students:
        c = s.get('college')
        bc = s.get('barcode', '').strip().upper()
        if c and bc:
            existing_map[(c, bc)] = s

    inserted_count = 0
    updated_count = 0

    new_inserts = []
    for r in day2_records:
        key = (r['college'], r['barcode'])
        if key in existing_map:
            ex = existing_map[key]
            # Update name if Day 2 has longer/full name
            if len(r['name']) > len(ex.get('name', '')):
                students_table.update({'name': r['name']}, doc_ids=[ex.doc_id])
                updated_count += 1
        else:
            new_record = {
                'barcode': r['id'].strip().upper(),
                'name': r['name'].strip().upper(),
                'college': r['college'],
                'division': r['division'],
                'roll_no': r['id'].strip(),
                'status': 'PENDING',
                'entry_timestamp': None,
                'entry_date': None,
                'entry_time': None,
                'volunteer': None
            }
            new_inserts.append(new_record)
            existing_map[key] = new_record
            inserted_count += 1

    if new_inserts:
        students_table.insert_multiple(new_inserts)

    db.close()
    print(f"Centralized Database Synced: {inserted_count} new students added, {updated_count} existing students updated.")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PASSES_COPY_DIR, exist_ok=True)

    font_path = get_font_path()
    code128_class = barcode.get_barcode_class('code128')
    writer = ImageWriter()

    print("=== STEP 1: PARSING DAY2.CSV ===")
    day2_records = load_day2_records()
    print(f"Total student records in DAY2.csv: {len(day2_records)}")

    print("\n=== STEP 2: CHECKING ALREADY GENERATED PASSES ===")
    db_path = os.path.join(BASE_DIR, 'database.json')
    already_gen = get_already_generated_students(db_path)

    to_generate_by_college = {'DYPIMED': [], 'DYPTC': [], 'DYPCOEI': [], 'DYPSOA': []}
    skipped_by_college = {'DYPIMED': [], 'DYPTC': [], 'DYPCOEI': [], 'DYPSOA': []}

    for r in day2_records:
        col = r['college']
        bc = r['barcode']
        # Check if already generated in Day 1 for this exact college and barcode
        if (col, bc) in already_gen:
            ex = already_gen[(col, bc)]
            # If the student name in Day 1 is similar (e.g. Abhijeet vs ABHIJEET ADINATH SANAP)
            d1_name = ex.get('name', '').upper()
            d2_name = r['name'].upper()
            # If same student or same ID
            if d1_name in d2_name or d2_name in d1_name or d1_name == d2_name:
                skipped_by_college[col].append(r)
                continue

        to_generate_by_college[col].append(r)

    print("\n=== PASS GENERATION BREAKDOWN ===")
    for col in ['DYPIMED', 'DYPTC', 'DYPCOEI', 'DYPSOA']:
        print(f"  {col}: {len(to_generate_by_college[col])} to generate, {len(skipped_by_college[col])} already generated (skipped)")

    print("\n=== STEP 3: GENERATING COLLEGE-WISE PASSES ===")
    for col in ['DYPIMED', 'DYPTC', 'DYPCOEI', 'DYPSOA']:
        template_file = TEMPLATES[col]
        students = to_generate_by_college[col]
        generate_passes_for_college(col, students, template_file, font_path, code128_class, writer)

    print("\n=== STEP 4: SYNCING CENTRALIZED DATABASE ===")
    sync_centralized_database(day2_records)

    print("\n=== ALL PROCESSES COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    main()
