import os
import shutil
import csv
from tinydb import TinyDB, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if os.environ.get('VERCEL'):
    DB_PATH = '/tmp/database.json'
    bundled_db = os.path.join(BASE_DIR, 'database.json')
    if not os.path.exists(DB_PATH) and os.path.exists(bundled_db):
        shutil.copy2(bundled_db, DB_PATH)
else:
    DB_PATH = os.path.join(BASE_DIR, 'database.json')


def init_database(force_reload=False):
    """
    Initializes TinyDB with students from data.csv and DYPTC.csv.
    If database.json already exists and has records, preserves status unless force_reload=True.
    """
    db = TinyDB(DB_PATH)
    students_table = db.table('students')
    logs_table = db.table('logs')
    users_table = db.table('users')

    # Seed users if empty
    if len(users_table) == 0:
        users_table.insert_multiple([
            {'username': 'admin', 'password': 'admin123', 'name': 'Super Admin', 'role': 'admin'},
            {'username': 'gate1', 'password': 'gate123', 'name': 'Gate 1 Volunteer', 'role': 'volunteer'},
            {'username': 'gate2', 'password': 'gate123', 'name': 'Gate 2 Volunteer', 'role': 'volunteer'},
            {'username': 'volunteer', 'password': 'pass', 'name': 'Main Volunteer', 'role': 'volunteer'},
        ])
        print("Initialized default users: admin/admin123, gate1/gate123, volunteer/pass")

    existing_count = len(students_table)
    if existing_count > 0 and not force_reload:
        print(f"Database already populated with {existing_count} students. Preserving existing records.")
        db.close()
        return

    # If force reload, preserve entry statuses if any
    status_cache = {}
    if force_reload:
        for s in students_table.all():
            if s.get('status') == 'ENTERED':
                status_cache[s['barcode']] = {
                    'status': s.get('status'),
                    'entry_timestamp': s.get('entry_timestamp'),
                    'entry_date': s.get('entry_date'),
                    'entry_time': s.get('entry_time'),
                    'volunteer': s.get('volunteer')
                }
        students_table.truncate()

    new_students = []

    # 1. Load DYPIMED & DYPCOEI from data.csv
    if os.path.exists('data.csv'):
        with open('data.csv', mode='r', encoding='utf-8-sig', errors='replace') as f:
            rows = list(csv.reader(f))

        current_college = None
        for idx, row in enumerate(rows):
            line_str = ' '.join(row)
            if 'DYPIMED' in line_str:
                current_college = 'DYPIMED'
                continue
            elif 'DYPCOEI' in line_str:
                current_college = 'DYPCOEI'
                continue

            name = row[0].strip() if len(row) > 0 else ''
            div = row[1].strip() if len(row) > 1 else ''
            sid = ''
            for c in row[2:]:
                if c.strip():
                    sid = c.strip()
                    break

            if name and sid and name not in ('DYPIMED', 'DYPCOEI'):
                cached = status_cache.get(sid, {})
                new_students.append({
                    'barcode': sid,
                    'name': name.upper(),
                    'college': current_college,
                    'division': div,
                    'roll_no': sid,
                    'status': cached.get('status', 'PENDING'),
                    'entry_timestamp': cached.get('entry_timestamp'),
                    'entry_date': cached.get('entry_date'),
                    'entry_time': cached.get('entry_time'),
                    'volunteer': cached.get('volunteer')
                })

    # 2. Load DYPTC from DYPTC.csv
    if os.path.exists('DYPTC.csv'):
        with open('DYPTC.csv', mode='r', encoding='utf-8-sig', errors='replace') as f:
            rows = list(csv.reader(f))

        for idx, row in enumerate(rows):
            if idx < 5 or len(row) < 4:
                continue
            sr, div, roll, name = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
            if not (name and roll and div) or 'TOTAL' in name.upper():
                continue

            barcode = f"{div}{roll}".upper()
            cached = status_cache.get(barcode, {})
            new_students.append({
                'barcode': barcode,
                'name': name.upper(),
                'college': 'DYPTC',
                'division': div,
                'roll_no': roll,
                'status': cached.get('status', 'PENDING'),
                'entry_timestamp': cached.get('entry_timestamp'),
                'entry_date': cached.get('entry_date'),
                'entry_time': cached.get('entry_time'),
                'volunteer': cached.get('volunteer')
            })

    if new_students:
        students_table.insert_multiple(new_students)
        print(f"Successfully populated {len(new_students)} students into NoSQL database!")

    db.close()

if __name__ == '__main__':
    init_database(force_reload=True)
