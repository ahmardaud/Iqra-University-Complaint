const path = require('path');
const express = require('express');
const cors = require('cors');
const sqlite3 = require('sqlite3').verbose();

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(__dirname));

const DB_PATH = path.join(__dirname, 'complaints.db');

function getDb() {
    return new sqlite3.Database(DB_PATH);
}

function initDb() {
    const db = getDb();
    db.serialize(() => {
        // Complaints table
        db.run(`
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
        `);

        // Admin settings table
        db.run(`
            CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
        `);

        // Seed admin if not existing
        db.get('SELECT * FROM admin_users WHERE username = ?', ['admin'], (err, row) => {
            if (!row) {
                db.run('INSERT INTO admin_users (username, password) VALUES (?, ?)', ['admin', 'iqra2026']);
            }
        });

        // Seed sample complaints if empty
        db.get('SELECT COUNT(*) as count FROM complaints', [], (err, row) => {
            if (row && row.count === 0) {
                const now = new Date().toISOString();
                const sampleData = [
                    [
                        'IUC-20260001', 'Ali Hassan', 'IU-2023-CS-045', 'ali.hassan@iqra.edu.pk', '0300-1234567',
                        'Computer Science', 'Undergraduate (BS)', 'Academic Issues', 'High',
                        'Grade dispute in Data Structures final exam',
                        'My final exam grade appears to be incorrect. I scored well in all sections but my GPA reflects a much lower score.',
                        'Re-evaluation of my final exam paper.', 'In Review', 'Forwarded to the academic controller for review.',
                        now, now
                    ],
                    [
                        'IUC-20260002', 'Sara Malik', 'IU-2022-MBA-012', 'sara.malik@iqra.edu.pk', '0321-9876543',
                        'MBA', 'Postgraduate (MS/MBA)', 'Financial / Fee Related', 'High',
                        'Scholarship deduction not applied to fee challan',
                        'I was awarded a 50% merit scholarship at the start of this semester but the fee challan does not reflect deduction.',
                        'Correction of fee challan with scholarship deduction applied.', 'Pending', '',
                        now, now
                    ],
                    [
                        'IUC-20260003', 'Usman Iqbal', 'IU-2021-EE-007', 'usman.iqbal@iqra.edu.pk', '0333-5554433',
                        'Electrical Engineering', 'Undergraduate (BS)', 'Facilities & Infrastructure', 'Medium',
                        'Engineering lab equipment not functional',
                        'Lab 3 oscilloscopes have been non-functional for three weeks. This is affecting our practical work.',
                        'Repair or replacement of faulty oscilloscopes.', 'Resolved', 'Lab equipment serviced. 4 new oscilloscopes installed.',
                        now, now
                    ]
                ];

                const stmt = db.prepare(`
                    INSERT INTO complaints (
                        ticket_id, student_name, student_id, student_email, student_phone,
                        department, program, category, priority, title, description,
                        desired_resolution, status, admin_notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                `);
                sampleData.forEach(r => stmt.run(r));
                stmt.finalize();
            }
        });
    });
    db.close();
}

// Routes
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'main.html'));
});

app.get('/api/stats', (req, res) => {
    const db = getDb();
    db.all("SELECT status, category FROM complaints", [], (err, rows) => {
        db.close();
        if (err) return res.status(500).json({ success: false, error: err.message });

        const total = rows.length;
        const pending = rows.filter(r => r.status === 'Pending').length;
        const inReview = rows.filter(r => r.status === 'In Review').length;
        const resolved = rows.filter(r => r.status === 'Resolved').length;
        const rejected = rows.filter(r => r.status === 'Rejected').length;

        const catMap = {};
        rows.forEach(r => { catMap[r.category] = (catMap[r.category] || 0) + 1; });
        const byCategory = Object.entries(catMap).map(([category, count]) => ({ category, count }));

        res.json({
            success: true,
            stats: { total, pending, inReview, resolved, rejected, byCategory }
        });
    });
});

app.post('/api/complaints', (req, res) => {
    const data = req.body || {};
    const required = ['student_name', 'department', 'category', 'title', 'description'];
    for (const field of required) {
        if (!data[field]) {
            return res.status(400).json({ success: false, error: `Field ${field} is required` });
        }
    }

    const db = getDb();
    db.get('SELECT COUNT(*) as c FROM complaints', [], (err, row) => {
        if (err) { db.close(); return res.status(500).json({ success: false, error: err.message }); }
        
        const count = (row ? row.c : 0) + 1;
        const ticketId = `IUC-${new Date().getFullYear()}${String(count).padStart(4, '0')}`;
        const now = new Date().toISOString();

        db.run(`
            INSERT INTO complaints (
                ticket_id, student_name, student_id, student_email, student_phone,
                department, program, category, priority, title, description,
                desired_resolution, status, admin_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?)
        `, [
            ticketId,
            data.student_name,
            data.student_id || '',
            data.student_email || '',
            data.student_phone || '',
            data.department,
            data.program || '',
            data.category,
            data.priority || 'Medium',
            data.title,
            data.description,
            data.desired_resolution || '',
            now,
            now
        ], function(err2) {
            db.close();
            if (err2) return res.status(500).json({ success: false, error: err2.message });

            res.json({
                success: true,
                ticket_id: ticketId,
                id: this.lastID,
                message: 'Complaint submitted successfully!'
            });
        });
    });
});

app.get('/api/track/:ticket_id', (req, res) => {
    const db = getDb();
    db.get('SELECT * FROM complaints WHERE UPPER(ticket_id) = UPPER(?)', [req.params.ticket_id], (err, row) => {
        db.close();
        if (err || !row) {
            return res.status(404).json({ success: false, error: 'Ticket ID not found' });
        }
        res.json({ success: true, complaint: row });
    });
});

app.post('/api/admin/login', (req, res) => {
    const { username, password } = req.body || {};
    const db = getDb();
    db.get('SELECT * FROM admin_users WHERE username = ? AND password = ?', [username, password], (err, row) => {
        db.close();
        if (row) {
            res.json({ success: true, token: 'valid-admin-session' });
        } else {
            res.status(401).json({ success: false, error: 'Invalid username or password' });
        }
    });
});

app.get('/api/admin/complaints', (req, res) => {
    const { status, category, search } = req.query;
    let query = 'SELECT * FROM complaints WHERE 1=1';
    const params = [];

    if (status && status !== 'All') {
        query += ' AND status = ?';
        params.push(status);
    }
    if (category && category !== 'All') {
        query += ' AND category = ?';
        params.push(category);
    }
    if (search) {
        query += ' AND (student_name LIKE ? OR title LIKE ? OR ticket_id LIKE ? OR student_email LIKE ?)';
        const pattern = `%${search}%`;
        params.push(pattern, pattern, pattern, pattern);
    }
    query += ' ORDER BY id DESC';

    const db = getDb();
    db.all(query, params, (err, rows) => {
        db.close();
        if (err) return res.status(500).json({ success: false, error: err.message });
        res.json({ success: true, complaints: rows });
    });
});

app.put('/api/admin/complaints/:id', (req, res) => {
    const { status, priority, admin_notes } = req.body || {};
    const now = new Date().toISOString();

    const db = getDb();
    db.run(`
        UPDATE complaints
        SET status = ?, priority = ?, admin_notes = ?, updated_at = ?
        WHERE id = ?
    `, [status, priority, admin_notes || '', now, req.params.id], function(err) {
        db.close();
        if (err || this.changes === 0) {
            return res.status(404).json({ success: false, error: 'Complaint not found' });
        }
        res.json({ success: true, message: 'Updated successfully' });
    });
});

app.delete('/api/admin/complaints/:id', (req, res) => {
    const db = getDb();
    db.run('DELETE FROM complaints WHERE id = ?', [req.params.id], function(err) {
        db.close();
        if (err || this.changes === 0) {
            return res.status(404).json({ success: false, error: 'Complaint not found' });
        }
        res.json({ success: true, message: 'Deleted successfully' });
    });
});

app.post('/api/admin/change-password', (req, res) => {
    const { current_password, new_password } = req.body || {};
    const db = getDb();
    db.get('SELECT * FROM admin_users WHERE username = ? AND password = ?', ['admin', current_password], (err, row) => {
        if (!row) {
            db.close();
            return res.status(400).json({ success: false, error: 'Current password incorrect' });
        }
        db.run('UPDATE admin_users SET password = ? WHERE username = ?', [new_password, 'admin'], (err2) => {
            db.close();
            res.json({ success: true, message: 'Password updated successfully' });
        });
    });
});

const PORT = 5000;
initDb();
app.listen(PORT, '0.0.0.0', () => {
    console.log('==================================================');
    console.log('Iqra University JS Backend Server Running!');
    console.log(`SQLite Database location: ${DB_PATH}`);
    console.log(`Open Website: http://localhost:${PORT}`);
    console.log('==================================================');
});
