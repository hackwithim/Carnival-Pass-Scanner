import os
import shutil
import csv
import io
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, send_file
from tinydb import TinyDB, Query
from db_loader import init_database, DB_PATH, BASE_DIR

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = 'grand-freshers-carnival-2k26-secret-key'

# Ensure database exists
if not os.path.exists(DB_PATH):
    init_database()

def get_db():
    return TinyDB(DB_PATH)


def get_user_record(db, username):
    users_table = db.table('users')
    User = Query()
    return users_table.get(User.username == username)


def get_admin_password(db):
    rec = get_user_record(db, 'admin')
    if rec and rec.get('password'):
        return rec['password']
    return 'admin123'


def resolve_student_record(students_table, raw_input):
    """
    Intelligently resolves a student or pass record matching the input.
    Supports:
    1. Direct barcode match (e.g. 'CARNIVAL0001', '26413', 'A11101')
    2. Box Office serial syntax (e.g. 'CARNIVAL 1', '0001', '1', 'BO 42', 'CARNIVAL-100')
    3. Exact roll number match
    4. Clean symbol/whitespace-stripped match
    Prioritizes PENDING records when duplicate numbers exist.
    """
    raw_str = (raw_input or '').strip()
    if not raw_str:
        return None, ''

    raw_upper = raw_str.upper()
    clean_upper = re.sub(r'[\s\-_#]+', '', raw_upper)
    all_records = students_table.all()

    # 1. Exact match on barcode
    direct_matches = [
        s for s in all_records
        if (s.get('barcode') or '').strip().upper() in (raw_upper, clean_upper)
    ]
    if direct_matches:
        pending = [m for m in direct_matches if m.get('status') != 'ENTERED']
        return (pending[0] if pending else direct_matches[0]), direct_matches[0].get('barcode', raw_upper)

    # 2. Box Office syntax expansion
    bo_candidates = []
    m_carnival = re.match(r'^CARNIVAL[^\d]*(\d+)$', clean_upper)
    if m_carnival:
        bo_candidates.append(f"CARNIVAL{int(m_carnival.group(1)):04d}")

    m_bo = re.match(r'^(?:BO|BOX|BOXOFFICE)[^\d]*(\d+)$', clean_upper)
    if m_bo:
        bo_candidates.append(f"CARNIVAL{int(m_bo.group(1)):04d}")

    # Pure numeric input if 1 to 4 digits (e.g. '1', '0001', '150')
    if clean_upper.isdigit():
        num = int(clean_upper)
        if 1 <= num <= 1000:
            bo_candidates.append(f"CARNIVAL{num:04d}")

    for cand in bo_candidates:
        bo_matches = [
            s for s in all_records
            if (s.get('barcode') or '').strip().upper() == cand
        ]
        if bo_matches:
            pending = [m for m in bo_matches if m.get('status') != 'ENTERED']
            return (pending[0] if pending else bo_matches[0]), cand

    # 3. Roll number match
    roll_matches = [
        s for s in all_records
        if (s.get('roll_no') or '').strip().upper() in (raw_upper, clean_upper)
    ]
    if roll_matches:
        pending = [m for m in roll_matches if m.get('status') != 'ENTERED']
        return (pending[0] if pending else roll_matches[0]), roll_matches[0].get('barcode', raw_upper)

    # 4. Clean barcode stripped fallback
    stripped_matches = [
        s for s in all_records
        if re.sub(r'[\s\-_#]+', '', (s.get('barcode') or '').upper()) == clean_upper
    ]
    if stripped_matches:
        pending = [m for m in stripped_matches if m.get('status') != 'ENTERED']
        return (pending[0] if pending else stripped_matches[0]), stripped_matches[0].get('barcode', raw_upper)

    return None, raw_upper


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    volunteer_name = data.get('volunteer_name', '').strip()

    db = get_db()
    users_table = db.table('users')
    User = Query()

    # Admin login check
    if username == 'admin':
        admin_pass = get_admin_password(db)
        if password == admin_pass:
            db.close()
            return jsonify({
                'success': True,
                'role': 'admin',
                'username': 'admin',
                'name': 'Administrator',
                'token': 'admin-session-token'
            })
        else:
            db.close()
            return jsonify({'success': False, 'message': 'Invalid administrator password'}), 401

    # Volunteer accounts check by username or display name
    check_name = (username or volunteer_name).strip().lower()
    matched_user = None
    for u in users_table.all():
        u_user = u.get('username', '').strip().lower()
        u_name = u.get('name', '').strip().lower()
        if (check_name == u_user or check_name == u_name) and u.get('password') == password:
            matched_user = u
            break

    if matched_user:
        db.close()
        return jsonify({
            'success': True,
            'role': matched_user.get('role', 'volunteer'),
            'username': matched_user.get('username'),
            'name': matched_user.get('name', matched_user.get('username').title()),
            'token': f"vol-{matched_user.get('username')}-token"
        })

    db.close()
    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

import threading
import time

scan_lock = threading.Lock()
volunteer_last_scans = {}
recent_barcode_scans = {}
COOLDOWN_SECONDS = 4.0

@app.route('/api/scan', methods=['POST'])
def scan_barcode():
    data = request.json or {}
    raw_barcode = data.get('barcode', '').strip()
    volunteer = data.get('volunteer', 'Volunteer').strip() or 'Volunteer'

    if not raw_barcode:
        return jsonify({'success': False, 'message': 'Barcode cannot be empty'}), 400

    now_ts = time.time()
    client_key = f"{request.remote_addr}_{volunteer.lower()}"

    with scan_lock:
        # Enforce 4-second cooldown per volunteer / gate scanner
        last_vol_time = volunteer_last_scans.get(client_key, 0)
        time_since_last = now_ts - last_vol_time
        if time_since_last < COOLDOWN_SECONDS:
            remaining = round(COOLDOWN_SECONDS - time_since_last, 1)
            return jsonify({
                'success': False,
                'status': 'COOLDOWN_ACTIVE',
                'cooldown_remaining': remaining,
                'message': f'Please wait {remaining}s before scanning another pass. 4-second anti-duplicate delay active.'
            }), 429

        db = get_db()
        students_table = db.table('students')
        logs_table = db.table('logs')

        student, matched_barcode = resolve_student_record(students_table, raw_barcode)
        barcode = matched_barcode or raw_barcode.upper()
        clean_barcode = barcode.replace(' ', '')

        now = datetime.now()
        ts_iso = now.isoformat()
        formatted_date = now.strftime('%d %b %Y')
        formatted_time = now.strftime('%I:%M:%S %p')

        if not student:
            # Update scan time to prevent spamming non-existent barcodes
            volunteer_last_scans[client_key] = now_ts
            logs_table.insert({
                'barcode': barcode,
                'student_name': 'UNKNOWN',
                'college': 'N/A',
                'division': 'N/A',
                'roll_no': 'N/A',
                'status': 'NOT_FOUND',
                'timestamp': ts_iso,
                'date': formatted_date,
                'time': formatted_time,
                'volunteer': volunteer,
                'message': 'Barcode not found in database'
            })
            db.close()
            return jsonify({
                'success': False,
                'status': 'NOT_FOUND',
                'barcode': barcode,
                'cooldown_seconds': 4,
                'message': f'Barcode [{barcode}] is NOT registered!'
            })

        # Record successful scan timestamp for cooldown
        volunteer_last_scans[client_key] = now_ts
        recent_barcode_scans[barcode] = now_ts
        recent_barcode_scans[clean_barcode] = now_ts

        # SECOND ENTRY CHECK - Strictly deny duplicate entry!
        if student.get('status') == 'ENTERED':
            prev_date = student.get('entry_date', '')
            prev_time = student.get('entry_time', '')
            prev_vol = student.get('volunteer', 'Previous Volunteer')

            logs_table.insert({
                'barcode': barcode,
                'student_name': student.get('name'),
                'college': student.get('college'),
                'division': student.get('division'),
                'roll_no': student.get('roll_no'),
                'status': 'DUPLICATE_DENIED',
                'timestamp': ts_iso,
                'date': formatted_date,
                'time': formatted_time,
                'volunteer': volunteer,
                'message': f'Second entry denied. Already checked in at {prev_time} on {prev_date} by {prev_vol}'
            })
            db.close()
            return jsonify({
                'success': False,
                'status': 'DUPLICATE_DENIED',
                'message': 'SECOND ENTRY DENIED! This pass has already been used.',
                'student': student,
                'cooldown_seconds': 4,
                'first_entry': {
                    'date': prev_date,
                    'time': prev_time,
                    'volunteer': prev_vol
                }
            })

        # ACCESS GRANTED: First time entry
        students_table.update({
            'status': 'ENTERED',
            'entry_timestamp': ts_iso,
            'entry_date': formatted_date,
            'entry_time': formatted_time,
            'volunteer': volunteer
        }, doc_ids=[student.doc_id])

        student['status'] = 'ENTERED'
        student['entry_timestamp'] = ts_iso
        student['entry_date'] = formatted_date
        student['entry_time'] = formatted_time
        student['volunteer'] = volunteer

        logs_table.insert({
            'barcode': barcode,
            'student_name': student.get('name'),
            'college': student.get('college'),
            'division': student.get('division'),
            'roll_no': student.get('roll_no'),
            'status': 'GRANTED',
            'timestamp': ts_iso,
            'date': formatted_date,
            'time': formatted_time,
            'volunteer': volunteer,
            'message': 'Access Granted'
        })

        db.close()
        return jsonify({
            'success': True,
            'status': 'GRANTED',
            'message': 'ENTRY GRANTED! Welcome to Grand Freshers Carnival 2K26',
            'cooldown_seconds': 4,
            'student': student
        })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    students_table = db.table('students')
    logs_table = db.table('logs')

    all_students = students_table.all()
    total = len(all_students)
    entered = sum(1 for s in all_students if s.get('status') == 'ENTERED')
    pending = total - entered
    overall_pct = round((entered / total * 100), 1) if total > 0 else 0

    colleges = {'DYPIMED': {}, 'DYPCOEI': {}, 'DYPTC': {}, 'DYPSOA': {}, 'BOX OFFICE': {}}
    for c in colleges.keys():
        c_students = [s for s in all_students if s.get('college') == c]
        c_total = len(c_students)
        c_entered = sum(1 for s in c_students if s.get('status') == 'ENTERED')
        colleges[c] = {
            'total': c_total,
            'entered': c_entered,
            'pending': c_total - c_entered,
            'percentage': round((c_entered / c_total * 100), 1) if c_total > 0 else 0
        }

    # Fetch last 30 logs in reverse chronological order
    all_logs = logs_table.all()
    recent_logs = sorted(all_logs, key=lambda x: x.get('timestamp', ''), reverse=True)[:30]

    db.close()
    return jsonify({
        'total': total,
        'entered': entered,
        'pending': pending,
        'percentage': overall_pct,
        'colleges': colleges,
        'recent_logs': recent_logs
    })


@app.route('/api/students', methods=['GET'])
def get_students():
    college_filter = request.args.get('college', 'ALL').strip()
    status_filter = request.args.get('status', 'ALL').strip()
    search = request.args.get('search', '').strip().lower()

    db = get_db()
    students_table = db.table('students')
    all_students = students_table.all()
    db.close()

    results = []
    for s in all_students:
        if college_filter != 'ALL' and s.get('college') != college_filter:
            continue
        if status_filter != 'ALL' and s.get('status') != status_filter:
            continue
        if search:
            name_match = search in s.get('name', '').lower()
            barcode_match = search in s.get('barcode', '').lower()
            roll_match = search in s.get('roll_no', '').lower()
            college_match = search in s.get('college', '').lower()
            division_match = search in s.get('division', '').lower()
            if not (name_match or barcode_match or roll_match or college_match or division_match):
                continue
        results.append(s)

    # Sort: Entered first (newest check-in first), then by college, then by name
    def sort_students(s):
        is_entered = 0 if s.get('status') == 'ENTERED' else 1
        ts = s.get('entry_timestamp') or ''
        if is_entered == 0 and ts:
            try:
                epoch = datetime.fromisoformat(ts).timestamp()
            except Exception:
                epoch = 0
            return (0, -epoch, s.get('college', ''), s.get('name', ''))
        return (1, 0, s.get('college', ''), s.get('name', ''))

    results.sort(key=sort_students)
    return jsonify({'count': len(results), 'students': results[:200]})

@app.route('/api/manual-checkin', methods=['POST'])
def manual_checkin():
    data = request.json or {}
    raw_barcode = data.get('barcode', '').strip()
    volunteer = data.get('volunteer', 'Admin Override').strip()

    db = get_db()
    students_table = db.table('students')
    logs_table = db.table('logs')

    student, matched_barcode = resolve_student_record(students_table, raw_barcode)
    if not student:
        db.close()
        return jsonify({'success': False, 'message': 'Student or pass not found'}), 404

    barcode = matched_barcode or student.get('barcode', raw_barcode.upper())
    now = datetime.now()
    ts_iso = now.isoformat()
    formatted_date = now.strftime('%d %b %Y')
    formatted_time = now.strftime('%I:%M:%S %p')

    students_table.update({
        'status': 'ENTERED',
        'entry_timestamp': ts_iso,
        'entry_date': formatted_date,
        'entry_time': formatted_time,
        'volunteer': volunteer
    }, doc_ids=[student.doc_id])

    logs_table.insert({
        'barcode': barcode,
        'student_name': student.get('name'),
        'college': student.get('college'),
        'division': student.get('division'),
        'roll_no': student.get('roll_no'),
        'status': 'GRANTED',
        'timestamp': ts_iso,
        'date': formatted_date,
        'time': formatted_time,
        'volunteer': volunteer,
        'message': 'Manual Check-in via Admin'
    })

    db.close()
    return jsonify({'success': True, 'message': f"Checked in {student.get('name')} successfully!"})

@app.route('/api/undo-checkin', methods=['POST'])
def undo_checkin():
    data = request.json or {}
    raw_barcode = data.get('barcode', '').strip()

    db = get_db()
    students_table = db.table('students')

    student, _ = resolve_student_record(students_table, raw_barcode)
    if not student:
        db.close()
        return jsonify({'success': False, 'message': 'Student or pass not found'}), 404

    students_table.update({
        'status': 'PENDING',
        'entry_timestamp': None,
        'entry_date': None,
        'entry_time': None,
        'volunteer': None
    }, doc_ids=[student.doc_id])

    db.close()
    return jsonify({'success': True, 'message': f"Reset check-in status for {student.get('name')}"})

@app.route('/api/reset', methods=['POST'])
def reset_entries():
    data = request.json or {}
    target_college = data.get('college', 'ALL').strip().upper()
    admin_password = data.get('admin_password', '').strip()

    db = get_db()
    current_admin_password = get_admin_password(db)

    if admin_password != current_admin_password:
        db.close()
        return jsonify({'success': False, 'message': 'Unauthorized: Incorrect Admin Password!'}), 403

    students_table = db.table('students')
    logs_table = db.table('logs')
    Student = Query()

    # Automatically create snapshot backup before resetting to allow recovery
    try:
        backup_dir = os.path.join(BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2(DB_PATH, os.path.join(backup_dir, f'backup_pre_reset_{backup_ts}.json'))
        shutil.copy2(DB_PATH, os.path.join(backup_dir, 'latest_reset_backup.json'))
    except Exception as e:
        app.logger.warning(f"Failed to create pre-reset auto-backup: {e}")

    if target_college == 'ALL':
        students_table.update({
            'status': 'PENDING',
            'entry_timestamp': None,
            'entry_date': None,
            'entry_time': None,
            'volunteer': None
        })
        msg = "All entries across ALL colleges have been reset to PENDING!"
    else:
        students_table.update({
            'status': 'PENDING',
            'entry_timestamp': None,
            'entry_date': None,
            'entry_time': None,
            'volunteer': None
        }, Student.college == target_college)
        msg = f"All entries for {target_college} have been reset to PENDING!"

    logs_table.insert({
        'barcode': 'SYSTEM',
        'student_name': 'SYSTEM_RESET',
        'college': target_college,
        'status': 'RESET',
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime('%d %b %Y'),
        'time': datetime.now().strftime('%I:%M:%S %p'),
        'volunteer': 'Admin',
        'message': msg
    })

    db.close()
    return jsonify({'success': True, 'message': msg})

@app.route('/api/export-csv', methods=['GET'])
def export_csv():
    db = get_db()
    students_table = db.table('students')
    all_students = students_table.all()
    db.close()

    def sort_entry(s):
        is_entered = 0 if s.get('status') == 'ENTERED' else 1
        ts = s.get('entry_timestamp') or ''
        if is_entered == 0 and ts:
            try:
                epoch = datetime.fromisoformat(ts).timestamp()
            except Exception:
                epoch = 0
            return (0, -epoch, s.get('college', ''), s.get('name', ''))
        return (1, 0, s.get('college', ''), s.get('name', ''))

    sorted_students = sorted(all_students, key=sort_entry)

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    writer.writerow([
        'Barcode',
        'Attendee Name',
        'Category / College',
        'Division',
        'Roll No / Serial',
        'Entry Status',
        'Entry Date',
        'Entry Time',
        'Entry Timestamp (ISO)',
        'Processed By (Volunteer / Gate)'
    ])

    for s in sorted_students:
        writer.writerow([
            s.get('barcode', ''),
            s.get('name', ''),
            s.get('college', ''),
            s.get('division', ''),
            s.get('roll_no', ''),
            s.get('status', 'PENDING'),
            s.get('entry_date') or '',
            s.get('entry_time') or '',
            s.get('entry_timestamp') or '',
            s.get('volunteer') or ''
        ])

    csv_data = output.getvalue()
    filename = f"Carnival_2K26_Attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/admin/change-password', methods=['POST'])
def change_password():
    data = request.json or {}
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    target_user = data.get('target_user', 'admin').strip().lower()

    if not new_password:
        return jsonify({'success': False, 'message': 'Please enter a new password.'}), 400

    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'New password must be at least 4 characters long.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New password and confirmation do not match.'}), 400

    db = get_db()
    actual_admin_password = get_admin_password(db)

    # When updating the administrator account itself, verify current admin password
    if target_user == 'admin':
        if not current_password:
            db.close()
            return jsonify({'success': False, 'message': 'Please enter current Administrator password.'}), 400
        if current_password != actual_admin_password:
            db.close()
            return jsonify({'success': False, 'message': 'Authentication failed: Incorrect current Administrator password!'}), 403

    users_table = db.table('users')
    User = Query()

    existing = users_table.get(User.username == target_user)
    if existing:
        users_table.update({'password': new_password}, doc_ids=[existing.doc_id])
    else:
        role = 'admin' if target_user == 'admin' else 'volunteer'
        name = 'Super Admin' if target_user == 'admin' else target_user.title()
        users_table.insert({
            'username': target_user,
            'password': new_password,
            'name': name,
            'role': role
        })

    db.close()
    target_label = "Administrator" if target_user == 'admin' else f"Volunteer '{target_user}'"
    return jsonify({
        'success': True,
        'message': f"Password for {target_label} has been successfully updated!"
    })

@app.route('/api/admin/users', methods=['GET'])
def get_admin_users():
    db = get_db()
    users_table = db.table('users')
    users = []
    for u in users_table.all():
        users.append({
            'username': u.get('username'),
            'name': u.get('name', u.get('username', '').title()),
            'role': u.get('role', 'volunteer')
        })
    db.close()

    usernames = [u['username'] for u in users]
    defaults = [
        {'username': 'admin', 'name': 'Administrator', 'role': 'admin'}
    ]
    for d in defaults:
        if d['username'] not in usernames:
            users.append(d)

    return jsonify({'success': True, 'users': users})


@app.route('/api/admin/volunteers', methods=['GET'])
def get_admin_volunteers():
    db = get_db()
    users_table = db.table('users')
    volunteers = []
    for u in users_table.all():
        volunteers.append({
            'username': u.get('username'),
            'name': u.get('name', u.get('username', '').title()),
            'role': u.get('role', 'volunteer')
        })
    db.close()
    return jsonify({'success': True, 'volunteers': volunteers})


@app.route('/api/admin/volunteers/add', methods=['POST'])
def add_admin_volunteer():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
    if not password:
        return jsonify({'success': False, 'message': 'Password is required'}), 400
    if len(password) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters long'}), 400
    if not name:
        name = username.title()

    db = get_db()
    users_table = db.table('users')
    User = Query()

    existing = users_table.get(User.username == username)
    if existing:
        db.close()
        return jsonify({'success': False, 'message': f"Username '{username}' already exists. Choose another username."}), 400

    users_table.insert({
        'username': username,
        'name': name,
        'password': password,
        'role': 'volunteer'
    })
    db.close()
    return jsonify({
        'success': True,
        'message': f"Volunteer '{name}' (@{username}) added successfully!"
    })


@app.route('/api/admin/volunteers/delete', methods=['POST'])
def delete_admin_volunteer():
    data = request.json or {}
    username = data.get('username', '').strip().lower()

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
    if username == 'admin':
        return jsonify({'success': False, 'message': 'Cannot delete administrator account!'}), 400

    db = get_db()
    users_table = db.table('users')
    User = Query()

    existing = users_table.get(User.username == username)
    if not existing:
        db.close()
        return jsonify({'success': False, 'message': f"Volunteer '{username}' not found."}), 404

    users_table.remove(User.username == username)
    db.close()
    return jsonify({
        'success': True,
        'message': f"Volunteer '{username}' has been removed successfully!"
    })


@app.route('/api/admin/volunteers/update-password', methods=['POST'])
def update_admin_volunteer_password():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    new_password = data.get('new_password', '').strip()

    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
    if not new_password:
        return jsonify({'success': False, 'message': 'New password is required'}), 400
    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters long'}), 400

    db = get_db()
    users_table = db.table('users')
    User = Query()

    existing = users_table.get(User.username == username)
    if not existing:
        # If default volunteer not yet explicitly in DB, add it
        name = username.title()
        role = 'admin' if username == 'admin' else 'volunteer'
        users_table.insert({
            'username': username,
            'name': name,
            'password': new_password,
            'role': role
        })
    else:
        users_table.update({'password': new_password}, User.username == username)

    db.close()
    return jsonify({
        'success': True,
        'message': f"Password for '{username}' updated successfully!"
    })

if __name__ == '__main__':
    # Initialize database on start
    init_database()
    print("Starting Grand Freshers Carnival Scanner Webapp on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=False)
