import os
import shutil
import csv
import io
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

    # Volunteer accounts
    user = users_table.get((User.username == username) & (User.password == password))
    if user:
        db.close()
        return jsonify({
            'success': True,
            'role': user.get('role', 'volunteer'),
            'username': user.get('username'),
            'name': user.get('name'),
            'token': f"vol-{user.get('username')}-token"
        })

    # Quick volunteer sign-in with custom name & passcode 'pass' or 'gate123'
    if volunteer_name and password in ('pass', 'gate123', 'volunteer123', '1234'):
        db.close()
        return jsonify({
            'success': True,
            'role': 'volunteer',
            'username': volunteer_name.lower().replace(' ', '_'),
            'name': volunteer_name,
            'token': f"vol-{datetime.now().timestamp()}"
        })

    db.close()
    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

@app.route('/api/scan', methods=['POST'])
def scan_barcode():
    data = request.json or {}
    raw_barcode = data.get('barcode', '').strip()
    volunteer = data.get('volunteer', 'Volunteer').strip() or 'Volunteer'

    if not raw_barcode:
        return jsonify({'success': False, 'message': 'Barcode cannot be empty'}), 400

    barcode = raw_barcode.upper()
    db = get_db()
    students_table = db.table('students')
    logs_table = db.table('logs')
    Student = Query()

    student = students_table.get(Student.barcode == barcode)

    # If not found directly, try case-insensitive or stripped search
    if not student:
        for s in students_table.all():
            if s.get('barcode', '').strip().upper() == barcode:
                student = s
                break

    now = datetime.now()
    ts_iso = now.isoformat()
    formatted_date = now.strftime('%d %b %Y')
    formatted_time = now.strftime('%I:%M:%S %p')

    if not student:
        # Log invalid attempt
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
            'message': f'Barcode [{barcode}] is NOT registered!'
        })

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

    colleges = {'DYPIMED': {}, 'DYPCOEI': {}, 'DYPTC': {}}
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
            if not (name_match or barcode_match or roll_match):
                continue
        results.append(s)

    # Sort: Entered first, then by college, then by name
    results.sort(key=lambda x: (0 if x.get('status') == 'ENTERED' else 1, x.get('college', ''), x.get('name', '')))
    return jsonify({'count': len(results), 'students': results[:200]})

@app.route('/api/manual-checkin', methods=['POST'])
def manual_checkin():
    data = request.json or {}
    barcode = data.get('barcode', '').strip().upper()
    volunteer = data.get('volunteer', 'Admin Override').strip()

    db = get_db()
    students_table = db.table('students')
    logs_table = db.table('logs')
    Student = Query()

    student = students_table.get(Student.barcode == barcode)
    if not student:
        db.close()
        return jsonify({'success': False, 'message': 'Student not found'}), 404

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
    barcode = data.get('barcode', '').strip().upper()

    db = get_db()
    students_table = db.table('students')
    Student = Query()

    student = students_table.get(Student.barcode == barcode)
    if not student:
        db.close()
        return jsonify({'success': False, 'message': 'Student not found'}), 404

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

@app.route('/api/admin/change-password', methods=['POST'])
def change_password():
    data = request.json or {}
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    target_user = data.get('target_user', 'admin').strip().lower()

    if not current_password:
        return jsonify({'success': False, 'message': 'Please provide the current Administrator password.'}), 400

    if not new_password:
        return jsonify({'success': False, 'message': 'Please enter a new password.'}), 400

    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'New password must be at least 4 characters long.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New password and confirmation do not match.'}), 400

    db = get_db()
    actual_admin_password = get_admin_password(db)

    if current_password != actual_admin_password:
        db.close()
        return jsonify({'success': False, 'message': 'Authentication failed: Incorrect current Administrator password!'}), 403

    users_table = db.table('users')
    User = Query()

    existing = users_table.get(User.username == target_user)
    if existing:
        users_table.update({'password': new_password}, User.username == target_user)
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
            'name': u.get('name'),
            'role': u.get('role')
        })
    db.close()

    usernames = [u['username'] for u in users]
    defaults = [
        {'username': 'admin', 'name': 'Administrator', 'role': 'admin'},
        {'username': 'gate1', 'name': 'Gate 1 Volunteer', 'role': 'volunteer'},
        {'username': 'gate2', 'name': 'Gate 2 Volunteer', 'role': 'volunteer'},
        {'username': 'volunteer', 'name': 'Main Volunteer', 'role': 'volunteer'}
    ]
    for d in defaults:
        if d['username'] not in usernames:
            users.append(d)

    return jsonify({'success': True, 'users': users})

@app.route('/api/export-csv')
def export_csv():
    db = get_db()
    students_table = db.table('students')
    students = students_table.all()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Barcode', 'Candidate Name', 'College', 'Division', 'Roll No', 'Entry Status', 'Entry Date', 'Entry Time', 'Processed By'])

    for s in students:
        writer.writerow([
            s.get('barcode', ''),
            s.get('name', ''),
            s.get('college', ''),
            s.get('division', ''),
            s.get('roll_no', ''),
            s.get('status', 'PENDING'),
            s.get('entry_date', '') or '-',
            s.get('entry_time', '') or '-',
            s.get('volunteer', '') or '-'
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=Grand_Freshers_Carnival_Attendance.csv"}
    )

if __name__ == '__main__':
    # Initialize database on start
    init_database()
    print("Starting Grand Freshers Carnival Scanner Webapp on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=False)
