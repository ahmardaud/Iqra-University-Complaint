import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'complaints.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Complaints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            student_id TEXT,
            student_email TEXT,
            student_phone TEXT,
            department TEXT NOT NULL,
            program TEXT,
            category TEXT NOT NULL,
            priority TEXT DEFAULT 'Medium',
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            desired_resolution TEXT,
            status TEXT DEFAULT 'Pending',
            admin_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Admin settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    # Seed default admin if not exists
    cursor.execute('SELECT * FROM admin_users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO admin_users (username, password) VALUES (?, ?)', ('admin', 'iqra2026'))
    
    # Seed sample complaints if empty
    cursor.execute('SELECT COUNT(*) as count FROM complaints')
    if cursor.fetchone()['count'] == 0:
        sample_data = [
            (
                'IUC-20260001', 'Ali Hassan', 'IU-2023-CS-045', 'ali.hassan@iqra.edu.pk', '0300-1234567',
                'Computer Science', 'Undergraduate (BS)', 'Academic Issues', 'High',
                'Grade dispute in Data Structures final exam',
                'My final exam grade appears to be incorrect. I scored well in all sections but my GPA reflects a much lower score. I have my answer sheet photos for reference.',
                'Re-evaluation of my final exam paper.', 'In Review', 'Forwarded to the academic controller for review.',
                datetime.now().isoformat(), datetime.now().isoformat()
            ),
            (
                'IUC-20260002', 'Sara Malik', 'IU-2022-MBA-012', 'sara.malik@iqra.edu.pk', '0321-9876543',
                'MBA', 'Postgraduate (MS/MBA)', 'Financial / Fee Related', 'High',
                'Scholarship deduction not applied to fee challan',
                'I was awarded a 50% merit scholarship at the start of this semester but the fee challan I received does not reflect any deduction.',
                'Correction of fee challan with scholarship deduction applied.', 'Pending', '',
                datetime.now().isoformat(), datetime.now().isoformat()
            ),
            (
                'IUC-20260003', 'Usman Iqbal', 'IU-2021-EE-007', 'usman.iqbal@iqra.edu.pk', '0333-5554433',
                'Electrical Engineering', 'Undergraduate (BS)', 'Facilities & Infrastructure', 'Medium',
                'Engineering lab equipment not functional',
                'Lab 3 oscilloscopes have been non-functional for three weeks. This is affecting our practical work.',
                'Repair or replacement of faulty oscilloscopes.', 'Resolved', 'Lab equipment serviced. 4 new oscilloscopes installed.',
                datetime.now().isoformat(), datetime.now().isoformat()
            )
        ]
        cursor.executemany('''
            INSERT INTO complaints (
                ticket_id, student_name, student_id, student_email, student_phone,
                department, program, category, priority, title, description,
                desired_resolution, status, admin_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)
        
    conn.commit()
    conn.close()

# Routes

@app.route('/')
def index():
    return send_from_directory('.', 'main.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    total = cursor.execute('SELECT COUNT(*) FROM complaints').fetchone()[0]
    pending = cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'").fetchone()[0]
    in_review = cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Review'").fetchone()[0]
    resolved = cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'").fetchone()[0]
    rejected = cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Rejected'").fetchone()[0]
    
    by_cat = cursor.execute('''
        SELECT category, COUNT(*) as count FROM complaints GROUP BY category ORDER BY count DESC
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'stats': {
            'total': total,
            'pending': pending,
            'inReview': in_review,
            'resolved': resolved,
            'rejected': rejected,
            'byCategory': [{'category': row['category'], 'count': row['count']} for row in by_cat]
        }
    })

@app.route('/api/complaints', methods=['POST'])
def submit_complaint():
    data = request.json or {}
    
    required = ['student_name', 'department', 'category', 'title', 'description']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'Field {field} is required'}), 400
            
    conn = get_db()
    cursor = conn.cursor()
    
    count = cursor.execute('SELECT COUNT(*) FROM complaints').fetchone()[0] + 1
    ticket_id = f"IUC-{datetime.now().year}{count:04d}"
    
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO complaints (
            ticket_id, student_name, student_id, student_email, student_phone,
            department, program, category, priority, title, description,
            desired_resolution, status, admin_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?)
    ''', (
        ticket_id,
        data.get('student_name'),
        data.get('student_id', ''),
        data.get('student_email', ''),
        data.get('student_phone', ''),
        data.get('department'),
        data.get('program', ''),
        data.get('category'),
        data.get('priority', 'Medium'),
        data.get('title'),
        data.get('description'),
        data.get('desired_resolution', ''),
        now,
        now
    ))
    
    conn.commit()
    complaint_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'success': True,
        'ticket_id': ticket_id,
        'id': complaint_id,
        'message': 'Complaint submitted successfully!'
    })

@app.route('/api/track/<ticket_id>', methods=['GET'])
def track_complaint(ticket_id):
    conn = get_db()
    cursor = conn.cursor()
    
    row = cursor.execute('SELECT * FROM complaints WHERE UPPER(ticket_id) = UPPER(?)', (ticket_id,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({'success': False, 'error': 'Ticket ID not found'}), 404
        
    return jsonify({
        'success': True,
        'complaint': dict(row)
    })

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute('SELECT * FROM admin_users WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    
    if row:
        return jsonify({'success': True, 'token': 'valid-admin-session'})
    else:
        return jsonify({'success': False, 'error': 'Invalid username or password'}), 401

@app.route('/api/admin/complaints', methods=['GET'])
def get_admin_complaints():
    status = request.args.get('status')
    category = request.args.get('category')
    search = request.args.get('search')
    
    query = 'SELECT * FROM complaints WHERE 1=1'
    params = []
    
    if status and status != 'All':
        query += ' AND status = ?'
        params.append(status)
        
    if category and category != 'All':
        query += ' AND category = ?'
        params.append(category)
        
    if search:
        query += ' AND (student_name LIKE ? OR title LIKE ? OR ticket_id LIKE ? OR student_email LIKE ?)'
        pattern = f'%{search}%'
        params.extend([pattern, pattern, pattern, pattern])
        
    query += ' ORDER BY id DESC'
    
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    
    return jsonify({
        'success': True,
        'complaints': [dict(r) for r in rows]
    })

@app.route('/api/admin/complaints/<int:complaint_id>', methods=['PUT'])
def update_complaint(complaint_id):
    data = request.json or {}
    status = data.get('status')
    priority = data.get('priority')
    admin_notes = data.get('admin_notes', '')
    now = datetime.now().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE complaints
        SET status = ?, priority = ?, admin_notes = ?, updated_at = ?
        WHERE id = ?
    ''', (status, priority, admin_notes, now, complaint_id))
    
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    if affected > 0:
        return jsonify({'success': True, 'message': 'Updated successfully'})
    return jsonify({'success': False, 'error': 'Complaint not found'}), 404

@app.route('/api/admin/complaints/<int:complaint_id>', methods=['DELETE'])
def delete_complaint(complaint_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM complaints WHERE id = ?', (complaint_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    if affected > 0:
        return jsonify({'success': True, 'message': 'Deleted successfully'})
    return jsonify({'success': False, 'error': 'Complaint not found'}), 404

@app.route('/api/admin/change-password', methods=['POST'])
def change_password():
    data = request.json or {}
    curr_pass = data.get('current_password')
    new_pass = data.get('new_password')
    
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute('SELECT * FROM admin_users WHERE username = ? AND password = ?', ('admin', curr_pass)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Current password incorrect'}), 400
        
    cursor.execute('UPDATE admin_users SET password = ? WHERE username = ?', (new_pass, 'admin'))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Password updated successfully'})

if __name__ == '__main__':
    init_db()
    print("==================================================")
    print("Iqra University Backend Server Running!")
    print(f"SQLite Database location: {DB_PATH}")
    print("Open Website: http://localhost:5000")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
