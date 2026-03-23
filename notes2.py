import os, json, shutil, base64, datetime, cv2
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for, Response, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

app = Flask(__name__)
# Secret key for browser session security
app.secret_key = "fortress_v21_final_master_key"

# --- SYSTEM DIRECTORIES ---
BASE_DIR = Path.home() / ".fortress_v21"
VAULT_ROOT = BASE_DIR / "vault"
TRASH_ROOT = BASE_DIR / "trash"
USER_DB = BASE_DIR / "users.json"
LOGO_URL = "https://cdn-icons-png.flaticon.com"

def setup():
    """Create hidden system folders and database if they don't exist."""
    for d in [BASE_DIR, VAULT_ROOT, TRASH_ROOT]: d.mkdir(parents=True, exist_ok=True)
    if not USER_DB.exists(): USER_DB.write_text(json.dumps({}))

# --- HELPERS ---
def get_db(): return json.loads(USER_DB.read_text())
def save_db(data): USER_DB.write_text(json.dumps(data))

def get_fernet(password, salt_b64):
    """Derive encryption key from user password and their specific salt."""
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)

def get_storage_stats(user_vault):
    """Calculate vault size for the progress bar."""
    total_size = sum(f.stat().st_size for f in user_vault.rglob('*') if f.is_file())
    limit = 1024 * 1024 * 500  # 500MB Limit
    percent = min(100, (total_size / limit) * 100)
    return f"{total_size / (1024*1024):.1f}MB / 500MB", percent

def generate_thumbnail(video_bytes, thumb_path):
    """Snap a frame from a video before it gets encrypted."""
    temp_vid = BASE_DIR / "temp_proc.mp4"
    temp_vid.write_bytes(video_bytes)
    cap = cv2.VideoCapture(str(temp_vid))
    success, frame = cap.read()
    if success:
        thumb = cv2.resize(frame, (150, 150))
        cv2.imwrite(str(thumb_path), thumb)
    cap.release()
    if temp_vid.exists(): temp_vid.unlink()

# --- UI TEMPLATE (HTML/JS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --bg: #0d1117; --side: #161b22; --accent: #58a6ff; --text: #c9d1d9; --border: #30363d; --card-bg: rgba(255, 255, 255, 0.03); }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; overflow: hidden; }
        #sidebar { width: 260px; background: var(--side); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
        .nav-item { padding: 12px 20px; cursor: pointer; color: #8b949e; border-radius: 6px; margin: 2px 10px; display: flex; align-items: center; gap: 10px; font-size: 14px; }
        #main { flex: 1; padding: 30px; overflow-y: auto; }
        .file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 20px; }
        .preview-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; cursor: pointer; position: relative; }
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:3000; align-items:center; justify-content:center; }
    </style>
</head>
<body>
    <div id="sidebar">
        <div style="padding: 25px; text-align: center;"><img src="{{ logo_url }}" style="width:40px;"><h3>Fortress</h3></div>
        <div class="nav-item" onclick="currentPath=''; loadFiles()">🏠 Root Vault</div>
        <div class="nav-item" onclick="showTrash()">🗑️ Trash Bin</div>
        <div style="flex:1"></div>
        <div class="nav-item" onclick="createFolder()">📁 New Folder</div>
        <div class="nav-item" onclick="createNewFile()">📝 New File</div>
        <div id="upload-status" style="padding: 10px 20px; font-size: 11px; color: var(--accent); display:none;">Uploading...</div>
        <label class="nav-item" style="background:var(--accent); color:white; justify-content:center;">➕ UPLOAD<input type="file" multiple onchange="upload(this)" style="display:none;"></label>
        <a href="/logout" class="nav-item">Logout</a>
    </div>
    <div id="main">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
            <h2 id="path-display">/ Root</h2>
            <div id="lock-timer" style="font-size:10px; color:#555;">Auto-locking in 10:00</div>
        </div>
        <div id="file-list" class="file-grid"></div>
    </div>
    <div id="video-modal" class="modal">
        <video id="player" controls style="max-width:90%;"></video>
        <button onclick="closeVideo()" style="position:absolute; top:30px; right:30px; color:white; border:1px solid white; background:none; cursor:pointer;">✕</button>
    </div>
    <div id="editor-modal" class="modal">
        <div style="background:var(--side); width:80%; height:80%; border-radius:12px; display:flex; flex-direction:column; padding:20px;">
            <input id="editor-filename" type="text" placeholder="filename.txt" style="background:transparent; border:none; color:var(--accent); font-size:18px;">
            <textarea id="editor-content" style="flex:1; background:var(--bg); color:var(--text); border-radius:8px; margin-top:10px; padding:15px;"></textarea>
            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:15px;">
                <span id="save-indicator" style="font-size:10px; color:#555; align-self:center;"></span>
                <button onclick="closeEditor()" style="color:#888; background:none; border:none; cursor:pointer;">Close</button>
                <button onclick="saveTextFile()" style="background:var(--accent); color:white; border:none; padding:10px 20px; border-radius:6px; cursor:pointer;">Save</button>
            </div>
        </div>
    </div>
    <script>
        let currentPath = "";
        let idleTime = 0;
        let autoSaveTimer = null;

        // Auto-lock monitor
        setInterval(() => {
            idleTime++;
            if (idleTime >= 600) location.href = '/logout';
            let t = 600 - idleTime;
            document.getElementById('lock-timer').innerText = `Auto-locking in ${Math.floor(t/60)}:${(t%60).toString().padStart(2,'0')}`;
        }, 1000);
        window.onmousemove = window.onkeypress = () => idleTime = 0;

        async function loadFiles() {
            const res = await fetch(`/api/files?path=${currentPath}`);
            const data = await res.json();
            document.getElementById('path-display').innerText = "/" + currentPath;
            render(data.items, data.stats);
        }

        async function showTrash() {
            const res = await fetch('/api/trash');
            const data = await res.json();
            document.getElementById('path-display').innerText = "🗑️ Trash Bin";
            render(data.items, {}, true);
        }

        function render(items, stats = {}, inTrash = false) {
            document.getElementById('file-list').innerHTML = items.map(f => {
                let views = stats[f.full_path] || 0;
                let isVideo = ['mp4', 'mov', 'avi'].includes(f.ext);
                let thumb = isVideo ? `/api/thumb/${f.name}` : null;
                let icon = f.is_dir ? "📁" : (thumb ? `<img src="${thumb}" style="width:100%; border-radius:8px;">` : "📄");
                let click = inTrash ? `restore('${f.name}')` : `handleAction('${f.name}', ${f.is_dir}, ${isVideo}, '${f.full_path}')`;
                return `<div class="preview-card" onclick="${click}">
                    <div style="font-size:40px;">${icon}</div>
                    <div style="font-size:12px; margin-top:10px;">${f.name}</div>
                    ${!inTrash && !f.is_dir ? `<div style="font-size:9px; color:gray;">👁️ ${views} views</div>` : ''}
                    ${!inTrash ? `<button onclick="event.stopPropagation(); deleteFile('${f.full_path}')" style="position:absolute; top:5px; right:5px; background:none; border:none; color:#555;">✕</button>` : ''}
                </div>`;
            }).join('');
        }

        async function handleAction(name, isDir, isVideo, path) {
            if (!isDir) await fetch(`/api/increment-view?path=${path}`, {method:'POST'});
            if (isDir) { currentPath = path; loadFiles(); }
            else if (isVideo) { 
                document.getElementById('video-modal').style.display='flex';
                document.getElementById('player').src=`/api/download/${path}`;
                document.getElementById('player').play();
            } else location.href=`/api/download/${path}`;
        }

        async function upload(input) {
            document.getElementById('upload-status').style.display = 'block';
            const fd = new FormData();
            for(let f of input.files) fd.append('files[]', f);
            await fetch(`/api/upload?path=${currentPath}`, {method:'POST', body:fd});
            document.getElementById('upload-status').style.display = 'none';
            loadFiles();
        }

        function createNewFile() {
            document.getElementById('editor-modal').style.display = 'flex';
            document.getElementById('editor-filename').value = "note_" + Date.now() + ".txt";
            document.getElementById('editor-content').value = "";
            autoSaveTimer = setInterval(() => saveTextFile(true), 60000);
        }

        async function saveTextFile(silent = false) {
            const name = document.getElementById('editor-filename').value;
            const content = document.getElementById('editor-content').value;
            await fetch('/api/save-text', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name, content, path: currentPath })
            });
            if(silent) document.getElementById('save-indicator').innerText = "Last saved: " + new Date().toLocaleTimeString();
            else { closeEditor(); loadFiles(); }
        }

        function closeEditor() { clearInterval(autoSaveTimer); document.getElementById('editor-modal').style.display = 'none'; }
        async function deleteFile(p) { if(confirm("Move to Trash?")) { await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:p})}); loadFiles(); } }
        async function restore(n) { if(confirm("Restore file?")) { await fetch('/api/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n})}); loadFiles(); } }
        function closeVideo() { document.getElementById('video-modal').style.display='none'; document.getElementById('player').pause(); document.getElementById('player').src=""; }
        async function createFolder() {
            const name = prompt("Folder Name:");
            if(name) {
                await fetch('/api/create-folder', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, path:currentPath})});
                loadFiles();
            }
        }
        loadFiles();
    </script>
</body>
</html>
"""

# --- PRIMARY NAVIGATION ROUTES ---

@app.route('/')
def index():
    """Main route to serve the vault. Redirects to login if session is empty."""
    if not session.get('user'): return redirect(url_for('login'))
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    db = get_db()
    txt, pct = get_storage_stats(user_vault)
    return render_template_string(HTML_TEMPLATE, logo_url=LOGO_URL, theme=db.get(session['user'], {}).get('theme',''), storage_text=txt, storage_percent=pct)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login and new registrations via PIN."""
    error = None
    if request.method == 'POST':
        user = request.form.get('user')
        pwd = request.form.get('password')
        pin = request.form.get('pin')
        db = get_db()
        if user in db:
            if check_password_hash(db[user]['hash'], pwd):
                session['user'], session['password'] = user, pwd
                return redirect(url_for('index'))
            error = "Invalid password."
        elif pin:
            salt = base64.b64encode(os.urandom(16)).decode()
            db[user] = {"hash": generate_password_hash(pwd), "salt": salt, "file_stats": {}, "theme": "default"}
            save_db(db)
            (VAULT_ROOT / secure_filename(user)).mkdir(parents=True, exist_ok=True)
            session['user'], session['password'] = user, pwd
            return redirect(url_for('index'))
        else: error = "User not found. Enter PIN to register."
    return render_template_string('''
        <body style="background:#0d1117; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
            <form method="POST" style="background:#161b22; padding:40px; border-radius:12px; border:1px solid #30363d;">
                <h2>🛡️ Fortress Login</h2>
                {% if error %}<p style="color:red; font-size:12px;">{{ error }}</p>{% endif %}
                <input name="user" placeholder="Username" required style="display:block; margin-bottom:10px; padding:10px; width:220px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px;">
                <input name="password" type="password" placeholder="Password" required style="display:block; margin-bottom:10px; padding:10px; width:220px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px;">
                <input name="pin" placeholder="PIN (New Users Only)" style="display:block; margin-bottom:20px; padding:10px; width:220px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px;">
                <button style="width:100%; padding:10px; background:#58a6ff; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:600;">Login / Register</button>
            </form>
        </body>
    ''', error=error)

@app.route('/logout')
def logout():
    """Clear session data and lock the vault."""
    session.clear()
    return redirect(url_for('login'))

# --- API ROUTES ---

@app.route('/api/files')
def list_files():
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    sub_path = request.args.get('path', '')
    target = user_vault / sub_path
    items = []
    if target.exists():
        for f in target.iterdir():
            if f.name == ".thumbs": continue
            items.append({"name": f.name, "is_dir": f.is_dir(), "ext": f.suffix[1:].lower(), "full_path": (Path(sub_path) / f.name).as_posix() if sub_path else f.name})
    db = get_db()
    return jsonify({"items": items, "stats": db[session['user']].get('file_stats', {})})

@app.route('/api/upload', methods=['POST'])
def upload():
    user = secure_filename(session['user'])
    target = (VAULT_ROOT / user) / request.args.get('path', '')
    target.mkdir(parents=True, exist_ok=True)
    thumb_dir = (VAULT_ROOT / user) / ".thumbs"
    thumb_dir.mkdir(exist_ok=True)
    db = get_db()
    fernet = get_fernet(session['password'], db[user]['salt'])
    for f in request.files.getlist('files[]'):
        if f.filename:
            raw = f.read()
            name = secure_filename(f.filename)
            if name.split('.')[-1].lower() in ['mp4','mov','avi']: generate_thumbnail(raw, thumb_dir / f"{name}.jpg")
            (target / name).write_bytes(fernet.encrypt(raw))
    return jsonify({"status": "ok"})

@app.route('/api/thumb/<filename>')
def get_thumb(filename):
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    path = user_vault / ".thumbs" / f"{filename}.jpg"
    return Response(path.read_bytes(), mimetype="image/jpeg") if path.exists() else abort(404)

@app.route('/api/download/<path:filename>')
def download(filename):
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    db = get_db()
    fernet = get_fernet(session['password'], db[session['user']]['salt'])
    data = fernet.decrypt((user_vault / filename).read_bytes())
    ext = filename.split('.')[-1].lower()
    mimetype = "video/mp4" if ext in ['mp4', 'mov'] else "application/octet-stream"
    return Response(data, mimetype=mimetype)

@app.route('/api/increment-view', methods=['POST'])
def inc_view():
    path = request.args.get('path')
    db = get_db()
    stats = db[session['user']].setdefault('file_stats', {})
    stats[path] = stats.get(path, 0) + 1
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/trash')
def list_trash():
    user_trash = TRASH_ROOT / secure_filename(session['user'])
    user_trash.mkdir(exist_ok=True)
    items = [{"name": f.name, "is_dir": f.is_dir(), "ext": f.suffix[1:].lower()} for f in user_trash.iterdir()]
    return jsonify({"items": items})

@app.route('/api/delete', methods=['POST'])
def move_to_trash():
    user = secure_filename(session['user'])
    src = VAULT_ROOT / user / request.json.get('path')
    dest = TRASH_ROOT / user
    dest.mkdir(exist_ok=True)
    if src.exists(): shutil.move(str(src), str(dest / src.name))
    return jsonify({"status": "ok"})

@app.route('/api/restore', methods=['POST'])
def restore():
    user = secure_filename(session['user'])
    name = request.json.get('name')
    src = TRASH_ROOT / user / name
    dest = VAULT_ROOT / user / name
    if src.exists(): shutil.move(str(src), str(dest))
    return jsonify({"status": "ok"})

@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    data = request.json
    (user_vault / data.get('path', '') / secure_filename(data['name'])).mkdir(parents=True, exist_ok=True)
    return jsonify({"status": "ok"})

@app.route('/api/save-text', methods=['POST'])
def save_text():
    user = session['user']
    user_vault = VAULT_ROOT / secure_filename(user)
    data = request.json
    target = user_vault / data.get('path', '') / secure_filename(data['name'])
    db = get_db()
    fernet = get_fernet(session['password'], db[user]['salt'])
    target.write_bytes(fernet.encrypt(data.get('content', '').encode()))
    return jsonify({"status": "ok"})

@app.route('/api/set-theme', methods=['POST'])
def set_theme():
    db = get_db()
    db[session['user']]['theme'] = request.json.get('theme')
    save_db(db)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    setup()
    # Runs locally on http://127.0.0.1:5000
    app.run(debug=True, port=5000)
