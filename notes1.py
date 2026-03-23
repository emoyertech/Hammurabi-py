import os, json, shutil, base64, datetime
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for, Response, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

app = Flask(__name__)
app.secret_key = "fortress_v21_final_master_key"

# --- SYSTEM DIRECTORIES ---
BASE_DIR = Path.home() / ".fortress_v21"
VAULT_ROOT = BASE_DIR / "vault"
USER_DB = BASE_DIR / "users.json"
LOGO_URL = "https://cdn-icons-png.flaticon.com"

def setup():
    for d in [BASE_DIR, VAULT_ROOT]: d.mkdir(parents=True, exist_ok=True)
    if not USER_DB.exists(): USER_DB.write_text(json.dumps({}))

# --- HELPERS ---
def get_db(): return json.loads(USER_DB.read_text())
def save_db(data): USER_DB.write_text(json.dumps(data))

def get_fernet(password, salt_b64):
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)

def get_storage_stats(user_vault):
    total_size = sum(f.stat().st_size for f in user_vault.rglob('*') if f.is_file())
    limit = 1024 * 1024 * 500  # 500MB Limit
    percent = min(100, (total_size / limit) * 100)
    return f"{total_size / (1024*1024):.1f}MB / 500MB", percent

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --bg: #0d1117; --side: #161b22; --accent: #58a6ff; --text: #c9d1d9; --border: #30363d; --card-bg: rgba(255, 255, 255, 0.03); }
        body.light-theme { --bg: #f5f5f5; --side: #ffffff; --accent: #005a9e; --text: #24292f; --border: #d0d7de; --card-bg: #fff; }
        body.matrix-theme { --bg: #000; --side: #001100; --accent: #00ff41; --text: #00ff41; --border: #003300; --card-bg: #000; }
        body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; overflow: hidden; }
        
        #sidebar { width: 260px; background: var(--side); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
        .nav-item { padding: 12px 20px; cursor: pointer; color: #8b949e; border-radius: 6px; margin: 2px 10px; display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .nav-item:hover { background: rgba(255,255,255,0.05); color: var(--text); }
        .pinned-section { border-top: 1px solid var(--border); margin-top: 10px; padding-top: 10px; }

        #main { flex: 1; padding: 30px; overflow-y: auto; }
        .file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 20px; }
        .file-list-mode { display: flex; flex-direction: column; gap: 8px; }
        
        .preview-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; transition: 0.2s; cursor: pointer; position: relative; }
        .preview-card:hover { border-color: var(--accent); transform: translateY(-2px); }
        .file-list-mode .preview-card { display: flex; align-items: center; text-align: left; padding: 10px 20px; gap: 20px; }

        #context-menu { position: fixed; z-index: 2000; width: 180px; background: var(--side); border: 1px solid var(--border); border-radius: 8px; display: none; flex-direction: column; padding: 5px 0; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .context-item { padding: 10px 15px; font-size: 13px; cursor: pointer; color: var(--text); }
        .context-item:hover { background: rgba(255,255,255,0.1); color: var(--accent); }

        .progress-container { margin: 20px; font-size: 10px; color: #8b949e; }
        .progress-bar { height: 6px; background: #30363d; border-radius: 3px; margin-top: 5px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent); transition: width 0.3s; }
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:3000; align-items:center; justify-content:center; }
    </style>
</head>
<body class="{{ theme }}">
    <div id="sidebar">
        <div style="padding: 25px; text-align: center;">
            <img src="{{ logo_url }}" style="width:40px; filter: drop-shadow(0 0 5px var(--accent));">
            <h3 style="color:var(--accent); margin-top:10px; font-size: 18px;">🛡️ Fortress</h3>
        </div>
        <div class="nav-item" onclick="changePath('')">🏠 Root Vault</div>
        <div class="nav-item" onclick="search('kind:video')">🎬 Videos</div>
        <div class="nav-item" onclick="search('kind:file')">📄 Files</div>
        
        <div class="pinned-section" id="pinned-folders">
            <small style="margin-left: 20px; color: #555;">PINNED FOLDERS</small>
            <!-- Pinned folders will appear here -->
        </div>

        <div style="flex:1"></div>
        <div class="nav-item" onclick="createFolder()">📁 New Folder</div>
        <div class="nav-item" onclick="createNewFile()">📝 New Text File</div>
        
        <div class="progress-container">
            Vault Storage: <span id="storage-text">{{ storage_text }}</span>
            <div class="progress-bar"><div class="progress-fill" style="width: {{ storage_percent }}%;"></div></div>
        </div>
        <label class="nav-item" style="background:var(--accent); color:white; justify-content:center; font-weight:600;">➕ UPLOAD<input type="file" multiple onchange="upload(this)" style="display:none;"></label>
        <a href="/logout" class="nav-item" style="justify-content:center; border-top:1px solid var(--border);">Logout</a>
    </div>

    <div id="main">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
            <div>
                <h2 id="path-display" style="margin:0; font-size:24px;">/ Root</h2>
                <button onclick="goBack()" style="background:transparent; color:var(--accent); border:none; padding:0; cursor:pointer; font-size:12px;">← Back to previous</button>
            </div>
            <div style="display:flex; gap:15px; align-items:center;">
                <input type="text" placeholder="🔍 Global Search..." oninput="search(this.value)" style="background:var(--side); color:var(--text); border:1px solid var(--border); padding:10px 15px; border-radius:20px; width:250px;">
                <div style="background:var(--side); padding:5px; border-radius:8px; border:1px solid var(--border);">
                    <button onclick="setView('grid')" id="btn-grid" style="border:none; padding:5px 12px; border-radius:5px; cursor:pointer; background:var(--accent); color:white;">⣿</button>
                    <button onclick="setView('list')" id="btn-list" style="border:none; padding:5px 12px; border-radius:5px; cursor:pointer; background:transparent; color:var(--text);">≡</button>
                </div>
            </div>
        </div>
        <div id="file-list" class="file-grid"></div>
    </div>

    <!-- CONTEXT MENU -->
    <div id="context-menu">
        <div class="context-item" id="ctx-open">📂 Open</div>
        <div class="context-item" id="ctx-edit" style="display:none;">✏️ Edit Text</div>
        <div class="context-item" id="ctx-pin">📌 Pin to Sidebar</div>
        <div class="context-item" id="ctx-copy">📋 Copy Name</div>
        <div style="height:1px; background:var(--border); margin:5px 0;"></div>
        <div class="context-item danger" style="color:#ff4d4d;" id="ctx-delete">🗑️ Delete</div>
    </div>

    <!-- VIDEO MODAL -->
    <div id="video-modal" class="modal">
        <button onclick="closeVideo()" style="position:absolute; top:30px; right:30px; background:transparent; color:white; border:2px solid white; border-radius:50%; width:40px; height:40px; cursor:pointer;">✕</button>
        <video id="player" controls style="max-width:90%; max-height:85%; border-radius:8px;"></video>
    </div>

    <!-- EDITOR MODAL -->
    <div id="editor-modal" class="modal">
        <div style="background:var(--side); width:80%; height:80%; border-radius:12px; display:flex; flex-direction:column; padding:25px; border:1px solid var(--border);">
            <input id="editor-filename" type="text" placeholder="filename.txt" style="background:transparent; border:none; border-bottom:1px solid var(--border); color:var(--accent); font-size:20px; padding:10px; margin-bottom:20px; outline:none;">
            <textarea id="editor-content" style="flex:1; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:20px; font-family:monospace; font-size: 14px; resize:none; outline:none;"></textarea>
            <div style="display:flex; justify-content:flex-end; gap:15px; margin-top:20px;">
                <button onclick="closeEditor()" style="background:transparent; color:#888; border:none; cursor:pointer;">Discard</button>
                <button onclick="saveTextFile()" style="background:var(--accent); color:white; border:none; padding:12px 30px; border-radius:8px; font-weight:600; cursor:pointer;">Save Changes</button>
            </div>
        </div>
    </div>

    <script>
        let currentPath = "";
        let allItems = [];
        let selectedItem = null;

        async function loadFiles() {
            const res = await fetch(`/api/files?path=${currentPath}`);
            const data = await res.json();
            allItems = data.items;
            document.getElementById('path-display').innerText = currentPath ? `/ ${currentPath}` : "/ Root";
            render(allItems);
            renderPinned(data.pins);
        }

        function render(items) {
            const list = document.getElementById('file-list');
            list.innerHTML = items.map(f => {
                let isVideo = ['mp4', 'mov', 'mkv', 'avi'].includes(f.ext);
                let icon = f.is_dir ? "📁" : (isVideo ? "🎬" : "📄");
                return `
                    <div class="preview-card" data-name="${f.name}" onclick="handleAction('${f.name}', ${f.is_dir}, ${isVideo}, '${f.full_path}')">
                        <div style="font-size:40px;">${icon}</div>
                        <div style="flex:1; overflow:hidden;">
                            <div style="font-weight:600; font-size:14px; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">${f.name}</div>
                            <div style="font-size:10px; color:#8b949e; margin-top:4px;">${f.is_dir ? 'Folder' : f.ext.toUpperCase()}</div>
                        </div>
                    </div>`;
            }).join('');
        }

        function renderPinned(pins) {
            const div = document.getElementById('pinned-folders');
            div.innerHTML = '<small style="margin-left: 20px; color: #555;">PINNED FOLDERS</small>' + 
                pins.map(p => `<div class="nav-item" onclick="changePath('${p.path}')">📌 ${p.name}</div>`).join('');
        }

        function handleAction(name, isDir, isVideo, fullPath) {
            if (isDir) changePath(fullPath);
            else if (isVideo) play(fullPath);
            else download(fullPath);
        }

        function changePath(p) { currentPath = p; loadFiles(); }
        function goBack() { currentPath = currentPath.split('/').slice(0,-1).join('/'); loadFiles(); }
        
        async function search(term) {
            if(!term) return loadFiles();
            const res = await fetch(`/api/files?search=${term}`);
            const data = await res.json();
            document.getElementById('path-display').innerText = term.startsWith('kind:') ? term.split(':')[1].toUpperCase() : "🔍 Search Results";
            render(data.items);
        }

        // FOLDER & FILE CREATION
        async function createFolder() {
            const name = prompt("Folder Name:");
            if(!name) return;
            const res = await fetch('/api/create-folder', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name, path: currentPath })
            });
            if(res.ok) {
                const data = await res.json();
                changePath(data.new_path);
            }
        }

        function createNewFile() {
            document.getElementById('editor-modal').style.display = 'flex';
            document.getElementById('editor-filename').value = "new_note.txt";
            document.getElementById('editor-filename').readOnly = false;
            document.getElementById('editor-content').value = "";
        }

        async function saveTextFile() {
            const name = document.getElementById('editor-filename').value;
            const content = document.getElementById('editor-content').value;
            await fetch('/api/save-text', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name, content, path: currentPath })
            });
            closeEditor();
            loadFiles();
        }

        function closeEditor() { document.getElementById('editor-modal').style.display = 'none'; }

        // CONTEXT MENU LOGIC
        window.oncontextmenu = (e) => {
            const card = e.target.closest('.preview-card');
            if(!card) return;
            e.preventDefault();
            selectedItem = allItems.find(i => i.name === card.dataset.name);
            const menu = document.getElementById('context-menu');
            document.getElementById('ctx-edit').style.display = selectedItem.ext === 'txt' ? 'block' : 'none';
            document.getElementById('ctx-pin').style.display = selectedItem.is_dir ? 'block' : 'none';
            menu.style.display = 'flex';
            menu.style.top = e.clientY + 'px';
            menu.style.left = e.clientX + 'px';
        };

        document.getElementById('ctx-edit').onclick = async () => {
            const res = await fetch(`/api/get-text/${selectedItem.full_path}`);
            const data = await res.json();
            document.getElementById('editor-modal').style.display = 'flex';
            document.getElementById('editor-filename').value = selectedItem.name;
            document.getElementById('editor-filename').readOnly = true;
            document.getElementById('editor-content').value = data.content;
        };

        document.getElementById('ctx-pin').onclick = async () => {
            await fetch('/api/toggle-pin', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: selectedItem.name, path: selectedItem.full_path })
            });
            loadFiles();
        };

        async function upload(input) {
            const fd = new FormData();
            for(let f of input.files) fd.append('files[]', f);
            await fetch(`/api/upload?path=${currentPath}`, {method:'POST', body:fd});
            loadFiles();
        }

        function play(p) {
            const player = document.getElementById('player');
            player.src = `/api/download/${p}`;
            document.getElementById('video-modal').style.display = 'flex';
            player.play();
        }
        function closeVideo() { document.getElementById('video-modal').style.display='none'; document.getElementById('player').pause(); document.getElementById('player').src=""; }
        function download(p) { location.href = `/api/download/${p}`; }
        function setView(m) { document.getElementById('file-list').className = m === 'list' ? 'file-list-mode' : 'file-grid'; }
        
        loadFiles();
    </script>
</body>
</html>
"""

# --- API ROUTES ---

@app.route('/')
def index():
    if not session.get('user'): return redirect(url_for('login'))
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    db = get_db()
    txt, pct = get_storage_stats(user_vault)
    return render_template_string(HTML_TEMPLATE, logo_url=LOGO_URL, theme=db.get(session['user'], {}).get('theme',''), storage_text=txt, storage_percent=pct)

@app.route('/api/files')
def list_files():
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    sub_path = request.args.get('path', '')
    search_term = request.args.get('search', '').lower()
    items = []
    
    if search_term == 'kind:video':
        for f in user_vault.rglob('*'):
            if f.suffix[1:].lower() in ['mp4','mov','mkv','avi']:
                items.append({"name": f.name, "is_dir": False, "ext": f.suffix[1:].lower(), "full_path": f.relative_to(user_vault).as_posix()})
    elif search_term == 'kind:file':
        for f in user_vault.rglob('*'):
            if f.is_file() and f.suffix[1:].lower() not in ['mp4','mov','mkv','avi'] and f.name != "history.json":
                items.append({"name": f.name, "is_dir": False, "ext": f.suffix[1:].lower(), "full_path": f.relative_to(user_vault).as_posix()})
    elif search_term:
        for f in user_vault.rglob('*'):
            if search_term in f.name.lower() and f.name != "history.json":
                items.append({"name": f.name, "is_dir": f.is_dir(), "ext": f.suffix[1:].lower(), "full_path": f.relative_to(user_vault).as_posix()})
    else:
        target = user_vault / sub_path
        for f in target.iterdir():
            if f.name != "history.json":
                items.append({"name": f.name, "is_dir": f.is_dir(), "ext": f.suffix[1:].lower(), "full_path": (Path(sub_path) / f.name).as_posix() if sub_path else f.name})
    
    db = get_db()
    return jsonify({"items": sorted(items, key=lambda x: (not x['is_dir'], x['name'])), "pins": db[session['user']].get('pins', [])})

@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    data = request.json
    new_path = Path(data.get('path', '')) / secure_filename(data['name'])
    (user_vault / new_path).mkdir(parents=True, exist_ok=True)
    return jsonify({"status": "ok", "new_path": new_path.as_posix()})

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

@app.route('/api/get-text/<path:filename>')
def get_text(filename):
    user_vault = VAULT_ROOT / secure_filename(session['user'])
    db = get_db()
    fernet = get_fernet(session['password'], db[session['user']]['salt'])
    content = fernet.decrypt((user_vault / filename).read_bytes()).decode()
    return jsonify({"content": content})

@app.route('/api/toggle-pin', methods=['POST'])
def toggle_pin():
    db = get_db()
    pins = db[session['user']].get('pins', [])
    data = request.json
    if any(p['path'] == data['path'] for p in pins):
        pins = [p for p in pins if p['path'] != data['path']]
    else:
        pins.append({"name": data['name'], "path": data['path']})
    db[session['user']]['pins'] = pins
    save_db(db)
    return jsonify({"status": "ok"})

# --- Keep existing /login, /logout, /upload, and /download from previous snippets ---

if __name__ == '__main__':
    setup()
    app.run(debug=True, port=5000)
