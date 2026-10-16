import os
import sys
import io
import csv
import shutil
from PIL import Image, ImageDraw, ImageFont
import openpyxl
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
DESIGNS_DIR = os.path.join(DANDIYAA_DIR, 'Pass_designs')
SHEET_PATH = os.path.join(DANDIYAA_DIR, 'Sheet.xlsx')

TEMPLATES = {
    'BOX OFFICE': os.path.join(DESIGNS_DIR, 'BOX OFFICE PASS DANDIYA.jpg.jpeg'),
    'DYPCOEI': os.path.join(DESIGNS_DIR, 'DYPCOEI PASS DANDIYA.jpg.jpeg'),
    'DYPIMED': os.path.join(DESIGNS_DIR, 'DYPIMED PASS DANDIYA.jpg.jpeg'),
    'DYPSOA': os.path.join(DESIGNS_DIR, 'DYPSOA PASS DANDIYA.jpg.jpeg'),
    'DYPTC': os.path.join(DESIGNS_DIR, 'DYPTC PASS DANDIYA.jpg.jpeg'),
}

NEW_STUDENTS = [
    {
        'sr_no': 1,
        'name': 'SHIVANI MANE',
        'class_year': 'SY MCA',
        'department': 'MCA',
        'college': 'DYPIMED',
        'roll_no': '26615',
        'transaction_id': 'T2610091712073685732410',
        'paid_to': 'DYPTC Student Welfare',
        'date': '09 oct 2026',
        'amount': 200,
        'template': 'DYPIMED'
    },
    {
        'sr_no': 2,
        'name': 'NAMRATA PAWAR',
        'class_year': 'SE CS',
        'department': 'CS',
        'college': 'DYPTC',
        'roll_no': '23415',
        'transaction_id': '110874199711',
        'paid_to': 'DYPTC Student Welfare',
        'date': '09 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 3,
        'name': 'PRACHI NARKHEDE',
        'class_year': 'TE CE',
        'department': 'CE',
        'college': 'DYPTC',
        'roll_no': '33415',
        'transaction_id': 'T2610081238314638474697',
        'paid_to': 'DYPTC Student Welfare',
        'date': '08 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 4,
        'name': 'KRUSHNA SUKUMARAN',
        'class_year': 'TE CE',
        'department': 'CE',
        'college': 'DYPTC',
        'roll_no': '33416',
        'transaction_id': '628109231864',
        'paid_to': 'DYPTC Student Welfare',
        'date': '08 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 5,
        'name': 'VIKI KAMBLE',
        'class_year': 'TE CE',
        'department': 'CE',
        'college': 'DYPTC',
        'roll_no': '33417',
        'transaction_id': '628164996383',
        'paid_to': 'DYPTC Student Welfare',
        'date': '08 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 6,
        'name': 'JIMISHA CHOUDHRI',
        'class_year': 'TE CE',
        'department': 'CE',
        'college': 'DYPTC',
        'roll_no': '33418',
        'transaction_id': '01a11a52-6057-7500-8892-739b6abd2ecd UTR ID: 628189834757',
        'paid_to': 'DYPTC Student Welfare',
        'date': '08 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 7,
        'name': 'SIDDHI SHETE',
        'class_year': 'FE',
        'department': 'FE',
        'college': 'DYPTC',
        'roll_no': '11915',
        'transaction_id': '664549650757',
        'paid_to': 'DYPTC Student Welfare',
        'date': '06 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 8,
        'name': 'SAMYAK SUKHADEVE',
        'class_year': 'FE',
        'department': 'FE',
        'college': 'DYPTC',
        'roll_no': '11916',
        'transaction_id': 'T2610061042197530716659',
        'paid_to': 'DYPTC Student Welfare',
        'date': '06 oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 9,
        'name': 'MAYURI THAKARE',
        'class_year': 'FE',
        'department': 'FE',
        'college': 'DYPTC',
        'roll_no': '11917',
        'transaction_id': 'Paid in Cash to DYPTC Account Section',
        'paid_to': 'Faculty Paid cash in account section and taken received sign',
        'date': 'N/A',
        'amount': 400,
        'template': 'DYPTC'
    },
    {
        'sr_no': 10,
        'name': 'PRACHI JADHAV',
        'class_year': 'BE CE',
        'department': 'CE',
        'college': 'DYPTC',
        'roll_no': '43415',
        'transaction_id': '130991795213',
        'paid_to': 'Mangesh Dhole',
        'date': '09 Oct 2026',
        'amount': 400,
        'template': 'DYPTC'
    }
]

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

def render_pass(template_img, name, student_id, font_path, code128_class, writer):
    """
    Renders high-res Dandiya pass (3000x900).
    Cleanly centers Name, Roll/Student ID, and Code-128 Barcode on the stub.
    """
    pass_img = template_img.copy()
    draw = ImageDraw.Draw(pass_img)
    center_x = 2419
    max_name_width = 800

    # Dynamic font sizing for student name
    font_size_name = 100
    font_name = ImageFont.truetype(font_path, font_size_name)
    bb = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)
    while (bb[2] - bb[0]) > max_name_width and font_size_name > 30:
        font_size_name -= 3
        font_name = ImageFont.truetype(font_path, font_size_name)
        bb = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)

    # Dynamic font sizing for student ID
    font_id = ImageFont.truetype(font_path, 120)

    # Coordinates
    bb_n = draw.textbbox((0, 0), name, font=font_name, stroke_width=2)
    wn, hn = bb_n[2] - bb_n[0], bb_n[3] - bb_n[1]
    xn = center_x - wn // 2
    yn = 405 - hn // 2

    bb_i = draw.textbbox((0, 0), student_id, font=font_id, stroke_width=2)
    wi, hi = bb_i[2] - bb_i[0], bb_i[3] - bb_i[1]
    xi = center_x - wi // 2
    yi = 560 - hi // 2

    # Draw Name & ID with crisp white stroke
    draw.text((xn, yn), name, fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_name)
    draw.text((xi, yi), student_id, fill=(255, 255, 255), stroke_width=2, stroke_fill=(255, 255, 255), font=font_id)

    # Barcode (Code 128)
    bc_opts = {
        'module_width': 0.40,
        'module_height': 14.0,
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

    box_w = 580
    box_h = 135
    box_center_x = 2419
    box_center_y = 754

    bw, bh = bc_img.size
    scale = min(box_w / bw, box_h / bh)
    new_bw = max(1, int(bw * scale))
    new_bh = max(1, int(bh * scale))
    bc_resized = bc_img.resize((new_bw, new_bh), Image.Resampling.LANCZOS)

    paste_x = box_center_x - new_bw // 2
    paste_y = box_center_y - new_bh // 2
    pass_img.paste(bc_resized, (paste_x, paste_y))

    return pass_img

def build_pdf_documents(pass_images, output_a4_path, output_strip_path):
    """
    Builds both A4 Printable PDF (3 passes/page) and Multi-Page Strip PDF.
    """
    # 1. A4 Printable
    doc_a4 = fitz.open()
    a4_w, a4_h = 595.28, 841.89  # points
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

        border_rect = fitz.Rect(margin_x - 0.5, slot_y - 0.5, margin_x + pass_w + 0.5, slot_y + pass_h + 0.5)
        current_page.draw_rect(border_rect, color=(0.8, 0.8, 0.8), width=0.5)

    doc_a4.save(output_a4_path, deflate=True)
    doc_a4.close()

    # 2. Multi-Page Strip PDF (720 x 216 pt)
    doc_strip = fitz.open()
    strip_w, strip_h = 720, 216
    rect_single = fitz.Rect(0, 0, strip_w, strip_h)

    for img_bytes in pass_images:
        p = doc_strip.new_page(width=strip_w, height=strip_h)
        p.insert_image(rect_single, stream=img_bytes)

    doc_strip.save(output_strip_path, deflate=True)
    doc_strip.close()

def update_sheet(sheet_path, students):
    """
    Inserts students into dandiyaa/Sheet.xlsx under their respective sections:
    - Shivani Mane under DYPIMED
    - Engineering students under DYPTC
    """
    if not os.path.exists(sheet_path):
        print(f"[Sheet] Warning: {sheet_path} not found.")
        return

    wb = openpyxl.load_workbook(sheet_path)
    ws = wb['Sheet1']

    # Locate section rows
    sec_rows = {}
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).strip() in ['DYPIMED', 'DYPCOEI', 'DYPTC', 'DYPSOA', 'BOX OFFICE']:
            sec_rows[str(v).strip()] = r

    print("[Sheet] Current section header rows:", sec_rows)

    # 1. Shivani Mane into DYPIMED section (before DYPCOEI)
    # DYPCOEI is at sec_rows['DYPCOEI']
    dypcoei_row = sec_rows.get('DYPCOEI', 213)
    # Check if Shivani already in sheet
    already_shivani = False
    for r in range(1, ws.max_row + 1):
        if str(ws.cell(r, 4).value or '').strip() == '26615':
            already_shivani = True
            break

    if not already_shivani:
        ws.insert_rows(dypcoei_row, 1)
        ws.cell(row=dypcoei_row, column=1, value=None)
        ws.cell(row=dypcoei_row, column=2, value='SHIVANI MANE')
        ws.cell(row=dypcoei_row, column=3, value='SY MCA')
        ws.cell(row=dypcoei_row, column=4, value='26615')
        print(f"[Sheet] Inserted SHIVANI MANE under DYPIMED at row {dypcoei_row}")

        # Re-scan section rows after insertion
        sec_rows = {}
        for r in range(1, ws.max_row + 1):
            v = ws.cell(r, 1).value
            if v and str(v).strip() in ['DYPIMED', 'DYPCOEI', 'DYPTC', 'DYPSOA', 'BOX OFFICE']:
                sec_rows[str(v).strip()] = r

    # 2. DYPTC students into DYPTC section (before DYPSOA)
    dypsoa_row = sec_rows.get('DYPSOA', 1121)
    dyptc_students = [s for s in students if s['college'] == 'DYPTC']
    
    # Filter out any already present
    to_insert_dyptc = []
    for s in dyptc_students:
        exists = False
        for r in range(1, ws.max_row + 1):
            if str(ws.cell(r, 4).value or '').strip() == str(s['roll_no']).strip():
                exists = True
                break
        if not exists:
            to_insert_dyptc.append(s)

    if to_insert_dyptc:
        ws.insert_rows(dypsoa_row, len(to_insert_dyptc))
        for i, s in enumerate(to_insert_dyptc):
            curr_r = dypsoa_row + i
            ws.cell(row=curr_r, column=1, value=None)
            ws.cell(row=curr_r, column=2, value=s['name'])
            ws.cell(row=curr_r, column=3, value=s['class_year'])
            ws.cell(row=curr_r, column=4, value=s['roll_no'])
        print(f"[Sheet] Inserted {len(to_insert_dyptc)} students under DYPTC at rows {dypsoa_row} to {dypsoa_row + len(to_insert_dyptc) - 1}")

    wb.save(sheet_path)
    print(f"[Sheet] Successfully saved updated {sheet_path}")

def sync_database(db_path, students):
    """
    Syncs the new students into TinyDB database.json.
    """
    if not os.path.exists(db_path):
        print(f"[DB] {db_path} does not exist, skipping.")
        return 0

    db = TinyDB(db_path)
    students_table = db.table('students')
    all_students = students_table.all()

    existing_keys = set((s.get('college', '').strip().upper(), str(s.get('barcode', '')).strip().upper()) for s in all_students)
    inserted = 0

    for s in students:
        key = (s['college'].strip().upper(), str(s['roll_no']).strip().upper())
        if key not in existing_keys:
            record = {
                'barcode': str(s['roll_no']).strip().upper(),
                'name': s['name'].strip().upper(),
                'college': s['college'].strip().upper(),
                'division': s['class_year'].strip().upper(),
                'roll_no': str(s['roll_no']).strip(),
                'status': 'PENDING',
                'entry_timestamp': None,
                'entry_date': None,
                'entry_time': None,
                'volunteer': None
            }
            students_table.insert(record)
            existing_keys.add(key)
            inserted += 1

        # Also add cross-college fallback record for gate volunteer flexibility
        # For Shivani Mane (DYPIMED -> DYPTC)
        if s['name'] == 'SHIVANI MANE':
            sec_key = ('DYPTC', str(s['roll_no']).strip().upper())
            if sec_key not in existing_keys:
                students_table.insert({
                    'barcode': str(s['roll_no']).strip().upper(),
                    'name': s['name'].strip().upper(),
                    'college': 'DYPTC',
                    'division': 'SY MCA',
                    'roll_no': str(s['roll_no']).strip(),
                    'status': 'PENDING',
                    'entry_timestamp': None,
                    'entry_date': None,
                    'entry_time': None,
                    'volunteer': None
                })
                existing_keys.add(sec_key)
                inserted += 1

        # For Prachi Jadhav (DYPTC -> DYPCOEI fallback if scanned under DYPCOEI)
        if s['name'] == 'PRACHI JADHAV':
            sec_key = ('DYPCOEI', str(s['roll_no']).strip().upper())
            if sec_key not in existing_keys:
                students_table.insert({
                    'barcode': str(s['roll_no']).strip().upper(),
                    'name': s['name'].strip().upper(),
                    'college': 'DYPCOEI',
                    'division': 'BE CE',
                    'roll_no': str(s['roll_no']).strip(),
                    'status': 'PENDING',
                    'entry_timestamp': None,
                    'entry_date': None,
                    'entry_time': None,
                    'volunteer': None
                })
                existing_keys.add(sec_key)
                inserted += 1

    db.close()
    print(f"[DB] {os.path.basename(os.path.dirname(db_path)) or 'root'}/{os.path.basename(db_path)}: Inserted {inserted} records.")
    return inserted

def main():
    print("=" * 70)
    print("DANDIYA PASS GENERATION & DATABASE INTEGRATION FOR 10 DEPARTMENT STUDENTS")
    print("=" * 70)

    font_path = get_font_path()
    c128_class = barcode.get_barcode_class('code128')
    writer = ImageWriter()

    # 1. Update Sheet.xlsx in dandiyaa
    update_sheet(SHEET_PATH, NEW_STUDENTS)

    # 2. Sync to both TinyDB databases
    sync_database(os.path.join(DANDIYAA_DIR, 'database.json'), NEW_STUDENTS)
    sync_database(os.path.join(BASE_DIR, 'database.json'), NEW_STUDENTS)

    # 3. Export CSV files
    csv_root = os.path.join(BASE_DIR, 'New_10_Department_Students.csv')
    csv_dandiya = os.path.join(DANDIYAA_DIR, 'New_10_Department_Students.csv')
    for cp in [csv_root, csv_dandiya]:
        with open(cp, 'w', newline='', encoding='utf-8') as f:
            cw = csv.writer(f)
            cw.writerow(['SrNo', 'Student Name', 'Class & Year', 'Department', 'College', 'Assigned Roll No', 'Barcode', 'Transaction ID', 'Paid To / Date', 'Amount'])
            for s in NEW_STUDENTS:
                paid_info = f"{s['paid_to']} ({s['date']})"
                cw.writerow([s['sr_no'], s['name'], s['class_year'], s['department'], s['college'], s['roll_no'], s['roll_no'], s['transaction_id'], paid_info, s['amount']])
    print(f"[CSV] Created CSV at {csv_root} and {csv_dandiya}")

    # 4. Generate Individual Passes
    out_dir = os.path.join(BASE_DIR, 'passes', 'dandiyaa_10_new_department_passes')
    os.makedirs(out_dir, exist_ok=True)

    loaded_templates = {}
    for col, path in TEMPLATES.items():
        loaded_templates[col] = Image.open(path).convert('RGB')

    pass_images = []
    print("\n--- Generating Passes for 10 Students ---")
    for s in NEW_STUDENTS:
        tmpl_col = s['template']
        t_img = loaded_templates[tmpl_col]
        p_img = render_pass(t_img, s['name'], s['roll_no'], font_path, c128_class, writer)

        # Save individual PNG
        safe_name = s['name'].replace(' ', '_')
        fn = f"{s['sr_no']:02d}_{safe_name}_{s['college']}_{s['roll_no']}.png"
        p_img.save(os.path.join(out_dir, fn))

        buf = io.BytesIO()
        p_img.save(buf, format='JPEG', quality=92)
        pass_images.append(buf.getvalue())
        print(f"  [{s['sr_no']}/10] {s['name']:<20} | {s['class_year']:<8} | {s['college']:<8} | Roll: {s['roll_no']} -> {fn}")

        # Bonus: For Shivani Mane, also save a DYPTC version
        if s['name'] == 'SHIVANI MANE':
            p_img_tc = render_pass(loaded_templates['DYPTC'], s['name'], s['roll_no'], font_path, c128_class, writer)
            fn_tc = f"{s['sr_no']:02d}_{safe_name}_DYPTC_Bonus_{s['roll_no']}.png"
            p_img_tc.save(os.path.join(out_dir, fn_tc))

        # Bonus: For Prachi Jadhav, also save a DYPCOEI version
        if s['name'] == 'PRACHI JADHAV':
            p_img_coei = render_pass(loaded_templates['DYPCOEI'], s['name'], s['roll_no'], font_path, c128_class, writer)
            fn_coei = f"{s['sr_no']:02d}_{safe_name}_DYPCOEI_Bonus_{s['roll_no']}.png"
            p_img_coei.save(os.path.join(out_dir, fn_coei))

    # 5. Build Standalone 10-Pass PDF Documents
    pdf_a4 = os.path.join(BASE_DIR, 'Dandiya_10_New_Department_Passes_A4_Printable.pdf')
    pdf_strip = os.path.join(BASE_DIR, 'Dandiya_10_New_Department_Passes_Strip.pdf')
    build_pdf_documents(pass_images, pdf_a4, pdf_strip)

    # Copy to dandiyaa/ directory as well
    shutil.copy2(pdf_a4, os.path.join(DANDIYAA_DIR, 'Dandiya_10_New_Department_Passes_A4_Printable.pdf'))
    shutil.copy2(pdf_strip, os.path.join(DANDIYAA_DIR, 'Dandiya_10_New_Department_Passes_Strip.pdf'))

    print(f"\n[PDF] Standalone A4 Printable PDF: {pdf_a4} (4 pages, 3 passes/page)")
    print(f"[PDF] Standalone Multi-Page Strip PDF: {pdf_strip} (10 pages)")
    print(f"[Images] Saved all PNG passes to: {out_dir}")

    # 6. Regenerate Complete College Master Passes for DYPIMED and DYPTC
    print("\n--- Updating Complete College Master Passes (DYPIMED & DYPTC) ---")
    import generate_dandiya_passes
    recs_by_col = generate_dandiya_passes.load_sheet_records()
    
    for col in ['DYPIMED', 'DYPTC']:
        students = recs_by_col.get(col, [])
        print(f"[Master] Generating updated {col} passes ({len(students)} total students)...")
        res = generate_dandiya_passes.generate_college_passes(col, students, font_path, c128_class, writer)
        print(f"  -> Updated: {res['a4_pdf']} ({res['a4_pages']} pages, {res['count']} passes)")

    print("\n" + "=" * 70)
    print("ALL 10 NEW DEPARTMENT STUDENTS PROCESSED AND PASSES GENERATED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    main()
