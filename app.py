import os
import sqlite3
import pandas as pd
from flask import Flask, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import uuid
from functools import wraps

app = Flask(__name__)
app.secret_key = 'excel-filter-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}
app.config['DB_FILE'] = 'database.db'
app.config['ADMIN_USERNAME'] = 'admin'
app.config['ADMIN_PASSWORD'] = 'admin123'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_db():
    conn = sqlite3.connect(app.config['DB_FILE'])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS excel_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE NOT NULL,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        columns TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active'
    )''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    conn = sqlite3.connect(app.config['DB_FILE'])
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/files')
def list_files():
    conn = get_db()
    files = conn.execute('SELECT * FROM excel_files WHERE status = ? ORDER BY upload_time DESC', ('active',)).fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'files': [dict(row) for row in files]
    })

@app.route('/api/admin/files')
def admin_list_files():
    conn = get_db()
    files = conn.execute('SELECT * FROM excel_files ORDER BY upload_time DESC').fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'files': [dict(row) for row in files]
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    
    if file and allowed_file(file.filename):
        original_name = secure_filename(file.filename)
        file_id = str(uuid.uuid4().hex[:8])
        filename = f"{file_id}_{original_name}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            df = pd.read_excel(filepath)
            columns = ','.join(df.columns.tolist())
            row_count = len(df)
            
            conn = get_db()
            conn.execute('INSERT INTO excel_files (file_id, filename, original_name, columns, row_count) VALUES (?, ?, ?, ?, ?)',
                        (file_id, filename, original_name, columns, row_count))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'filename': original_name,
                'columns': df.columns.tolist(),
                'row_count': row_count
            })
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'success': False, 'error': f'读取文件失败: {str(e)}'})
    
    return jsonify({'success': False, 'error': '不支持的文件格式'})

@app.route('/filter', methods=['POST'])
def filter_data():
    data = request.json
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'success': False, 'error': '请选择文件'})
    
    conn = get_db()
    file_info = conn.execute('SELECT * FROM excel_files WHERE file_id = ?', (file_id,)).fetchone()
    conn.close()
    
    if not file_info:
        return jsonify({'success': False, 'error': '文件不存在'})
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': '文件已被删除'})
    
    try:
        df = pd.read_excel(filepath)
        filters = data.get('filters', [])
        
        for f in filters:
            column = f.get('column')
            operator = f.get('operator')
            value = f.get('value')
            
            if column not in df.columns:
                continue
            
            if operator == 'equals':
                df = df[df[column] == value]
            elif operator == 'not_equals':
                df = df[df[column] != value]
            elif operator == 'contains':
                df = df[df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == 'not_contains':
                df = df[~df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == 'gt':
                df = df[pd.to_numeric(df[column], errors='coerce') > float(value)]
            elif operator == 'lt':
                df = df[pd.to_numeric(df[column], errors='coerce') < float(value)]
            elif operator == 'gte':
                df = df[pd.to_numeric(df[column], errors='coerce') >= float(value)]
            elif operator == 'lte':
                df = df[pd.to_numeric(df[column], errors='coerce') <= float(value)]
            elif operator == 'empty':
                df = df[df[column].isna() | (df[column] == '')]
            elif operator == 'not_empty':
                df = df[df[column].notna() & (df[column] != '')]
        
        result = df.head(1000).to_dict('records')
        return jsonify({
            'success': True,
            'data': result,
            'total_count': len(df),
            'display_count': len(result)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'筛选失败: {str(e)}'})

@app.route('/export', methods=['POST'])
def export_data():
    data = request.json
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'success': False, 'error': '请选择文件'})
    
    conn = get_db()
    file_info = conn.execute('SELECT * FROM excel_files WHERE file_id = ?', (file_id,)).fetchone()
    conn.close()
    
    if not file_info:
        return jsonify({'success': False, 'error': '文件不存在'})
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': '文件已被删除'})
    
    try:
        df = pd.read_excel(filepath)
        filters = data.get('filters', [])
        
        for f in filters:
            column = f.get('column')
            operator = f.get('operator')
            value = f.get('value')
            
            if column not in df.columns:
                continue
            
            if operator == 'equals':
                df = df[df[column] == value]
            elif operator == 'not_equals':
                df = df[df[column] != value]
            elif operator == 'contains':
                df = df[df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == 'not_contains':
                df = df[~df[column].astype(str).str.contains(str(value), na=False)]
            elif operator == 'gt':
                df = df[pd.to_numeric(df[column], errors='coerce') > float(value)]
            elif operator == 'lt':
                df = df[pd.to_numeric(df[column], errors='coerce') < float(value)]
            elif operator == 'gte':
                df = df[pd.to_numeric(df[column], errors='coerce') >= float(value)]
            elif operator == 'lte':
                df = df[pd.to_numeric(df[column], errors='coerce') <= float(value)]
            elif operator == 'empty':
                df = df[df[column].isna() | (df[column] == '')]
            elif operator == 'not_empty':
                df = df[df[column].notna() & (df[column] != '')]
        
        export_filename = f"filtered_{uuid.uuid4().hex[:8]}.xlsx"
        export_path = os.path.join(app.config['UPLOAD_FOLDER'], export_filename)
        df.to_excel(export_path, index=False)
        
        return jsonify({
            'success': True,
            'download_url': f"/download/{export_filename}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'导出失败: {str(e)}'})

@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return "文件不存在", 404

@app.route('/admin/login')
def admin_login():
    if session.get('logged_in'):
        return redirect(url_for('admin'))
    with open('templates/admin_login.html', 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
        session['logged_in'] = True
        return redirect(url_for('admin'))
    
    html = '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>管理员登录</title>
<style>
body{font-family:sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;}
.card{background:white;padding:40px;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,0.3);text-align:center;}
.error{background:#fef0f0;color:#f56c6c;padding:12px;border-radius:8px;margin-bottom:20px;}
input{padding:12px;width:100%;margin-bottom:15px;border:1px solid #ddd;border-radius:8px;box-sizing:border-box;}
button{width:100%;padding:12px;background:#667eea;color:white;border:none;border-radius:8px;cursor:pointer;}
</style>
</head>
<body>
<div class="card">
<h2>管理后台</h2>
<div class="error">用户名或密码错误</div>
<form action="/admin/login" method="post">
<input type="text" name="username" placeholder="用户名" required>
<input type="password" name="password" placeholder="密码" required>
<button>登 录</button>
</form>
<p><a href="/">返回前台</a></p>
</div>
</body>
</html>'''
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin():
    with open('templates/admin.html', 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/admin/delete/<file_id>')
def delete_file(file_id):
    conn = get_db()
    file_info = conn.execute('SELECT * FROM excel_files WHERE file_id = ?', (file_id,)).fetchone()
    
    if file_info:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.execute('UPDATE excel_files SET status = ? WHERE file_id = ?', ('deleted', file_id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
