import os
import time
import uuid
from collections import Counter
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, send_file

from ics_core import apply_changes_to_ics, fold_ics_lines, parse_events, unfold_ics_lines


APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "ICS-Editor_Logo.png"
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "7200"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "32")) * 1024 * 1024

sessions = {}


PAGE = r"""
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ICS Editor</title>
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="apple-touch-icon" href="/favicon.png">
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0f14;
      --panel: #121821;
      --panel-2: #18202b;
      --panel-3: #202a37;
      --text: #edf2f7;
      --muted: #9aa7b5;
      --border: #2b3645;
      --primary: #4f8cff;
      --primary-strong: #2f6ee8;
      --danger: #ff5d6c;
      --ok: #2ed3a2;
      --shadow: 0 24px 80px rgba(0, 0, 0, .35);
    }

    [data-theme="light"] {
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-2: #eef3f8;
      --panel-3: #e4ebf3;
      --text: #17202a;
      --muted: #627084;
      --border: #d4dce7;
      --primary: #2563eb;
      --primary-strong: #1d4ed8;
      --danger: #dc2626;
      --ok: #0f9f77;
      --shadow: 0 24px 80px rgba(27, 39, 56, .14);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top left, rgba(79, 140, 255, .16), transparent 32rem), var(--bg);
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button, input, select {
      font: inherit;
    }

    .app {
      width: min(1280px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 18px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }

    .logo {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      box-shadow: var(--shadow);
      background: var(--panel);
      object-fit: cover;
    }

    h1 {
      margin: 0;
      font-size: 26px;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .subtitle {
      margin-top: 4px;
      color: var(--muted);
    }

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .btn {
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      padding: 10px 14px;
      border-radius: 8px;
      cursor: pointer;
      min-height: 40px;
    }

    .btn:hover {
      border-color: var(--primary);
    }

    .btn.primary {
      border-color: var(--primary);
      background: var(--primary);
      color: white;
      font-weight: 700;
    }

    .btn.primary:hover {
      background: var(--primary-strong);
    }

    .btn:disabled {
      opacity: .45;
      cursor: not-allowed;
      border-color: var(--border);
    }

    .panel {
      background: color-mix(in srgb, var(--panel) 94%, transparent);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: var(--shadow);
    }

    .upload {
      display: grid;
      grid-template-columns: 1.25fr .75fr;
      gap: 18px;
      padding: 18px;
      margin-bottom: 18px;
    }

    .dropzone {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border: 1px dashed color-mix(in srgb, var(--primary) 55%, var(--border));
      background: var(--panel-2);
      border-radius: 10px;
      padding: 18px;
      min-height: 112px;
    }

    .dropzone.dragover {
      border-color: var(--primary);
      background: color-mix(in srgb, var(--primary) 16%, var(--panel-2));
    }

    .dropzone input {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
    }

    .drop-title {
      font-size: 18px;
      font-weight: 750;
      margin-bottom: 4px;
    }

    .muted {
      color: var(--muted);
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
    }

    .side {
      display: grid;
      gap: 12px;
    }

    .server-file {
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }

    .server-file label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 8px;
      text-transform: uppercase;
    }

    .server-row {
      display: flex;
      gap: 8px;
    }

    .stat {
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }

    .stat .number {
      font-size: 26px;
      font-weight: 800;
    }

    .toolbar {
      display: flex;
      gap: 12px;
      justify-content: space-between;
      align-items: center;
      padding: 14px;
      border-bottom: 1px solid var(--border);
    }

    .search {
      width: min(420px, 100%);
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 12px;
      outline: none;
    }

    .search:focus {
      border-color: var(--primary);
    }

    .table-wrap {
      overflow: auto;
      max-height: calc(100vh - 340px);
      min-height: 280px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th, td {
      padding: 11px 14px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--panel-3);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      text-align: left;
    }

    td.summary {
      font-weight: 650;
      overflow-wrap: anywhere;
    }

    .count {
      width: 90px;
      text-align: center;
    }

    .select-col {
      width: 58px;
      text-align: center;
    }

    .action-col {
      width: 170px;
    }

    .rename-col {
      width: 32%;
    }

    select, .rename-input {
      width: 100%;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 8px;
      padding: 9px 10px;
      outline: none;
    }

    .rename-input:disabled {
      opacity: .45;
    }

    .status {
      min-height: 20px;
      color: var(--muted);
    }

    .status.ok { color: var(--ok); }
    .status.error { color: var(--danger); }

    .empty {
      padding: 42px 18px;
      text-align: center;
      color: var(--muted);
    }

    @media (max-width: 840px) {
      .topbar, .toolbar {
        align-items: stretch;
        flex-direction: column;
      }

      .actions {
        justify-content: flex-start;
      }

      .upload {
        grid-template-columns: 1fr;
      }

      .rename-col {
        width: 260px;
      }

      .table-wrap {
        max-height: none;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <section class="topbar">
      <div class="brand">
        <img class="logo" src="/logo.png" alt="">
        <div>
          <h1>ICS Editor</h1>
          <div class="subtitle">ICS-Dateien direkt im Browser bearbeiten.</div>
        </div>
      </div>
      <div class="actions">
        <button id="themeBtn" class="btn" type="button">Light Mode</button>
        <button id="downloadBtn" class="btn primary" type="button" disabled>Neue ICS herunterladen</button>
      </div>
    </section>

    <section class="panel upload">
      <label id="dropzone" class="dropzone">
        <input id="fileInput" type="file" accept=".ics,.ical,text/calendar">
        <div>
          <div class="drop-title">ICS-Datei auswählen oder hier ablegen</div>
          <div id="fileLabel" class="muted">Noch keine Datei geladen.</div>
        </div>
        <button class="btn primary" type="button">Datei öffnen</button>
      </label>

      <div class="side">
        <div class="server-file">
          <label for="serverFileSelect">Datei aus /data</label>
          <div class="server-row">
            <select id="serverFileSelect">
              <option value="">Keine ICS-Datei gefunden</option>
            </select>
            <button id="serverLoadBtn" class="btn" type="button" disabled>Laden</button>
          </div>
        </div>
        <div class="stats">
          <div class="stat">
            <div id="eventCount" class="number">0</div>
            <div class="muted">Termine</div>
          </div>
          <div class="stat">
            <div id="summaryCount" class="number">0</div>
            <div class="muted">Einträge</div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="toolbar">
        <input id="filterInput" class="search" type="search" placeholder="Termine filtern">
        <div class="actions">
          <button id="selectAllBtn" class="btn" type="button" disabled>Alle auswählen</button>
          <button id="selectNoneBtn" class="btn" type="button" disabled>Auswahl aufheben</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="select-col"></th>
              <th>Termin</th>
              <th class="count">Anzahl</th>
              <th class="action-col">Aktion</th>
              <th class="rename-col">Neuer Name</th>
            </tr>
          </thead>
          <tbody id="tableBody">
            <tr><td class="empty" colspan="5">Lade eine ICS-Datei, um die Termine zu sehen.</td></tr>
          </tbody>
        </table>
      </div>
      <div class="toolbar">
        <div id="status" class="status"></div>
        <button id="downloadBtnBottom" class="btn primary" type="button" disabled>Neue ICS herunterladen</button>
      </div>
    </section>
  </main>

  <script>
    const state = {
      token: null,
      filename: null,
      summaries: []
    };

    const els = {
      fileInput: document.getElementById('fileInput'),
      fileLabel: document.getElementById('fileLabel'),
      dropzone: document.getElementById('dropzone'),
      tableBody: document.getElementById('tableBody'),
      filterInput: document.getElementById('filterInput'),
      eventCount: document.getElementById('eventCount'),
      summaryCount: document.getElementById('summaryCount'),
      status: document.getElementById('status'),
      downloadBtn: document.getElementById('downloadBtn'),
      downloadBtnBottom: document.getElementById('downloadBtnBottom'),
      selectAllBtn: document.getElementById('selectAllBtn'),
      selectNoneBtn: document.getElementById('selectNoneBtn'),
      themeBtn: document.getElementById('themeBtn'),
      serverFileSelect: document.getElementById('serverFileSelect'),
      serverLoadBtn: document.getElementById('serverLoadBtn')
    };

    function setStatus(message, type = '') {
      els.status.textContent = message;
      els.status.className = `status ${type}`.trim();
    }

    function setTheme(theme) {
      document.documentElement.dataset.theme = theme;
      localStorage.setItem('ics-editor-theme', theme);
      els.themeBtn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }

    setTheme(localStorage.getItem('ics-editor-theme') || 'dark');
    els.themeBtn.addEventListener('click', () => {
      setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    });

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    function applyAnalyzeResult(data) {
      state.token = data.token;
      state.filename = data.filename;
      state.summaries = data.summaries;
      els.fileLabel.textContent = data.filename;
      els.eventCount.textContent = data.event_count;
      els.summaryCount.textContent = data.summaries.length;
      els.downloadBtn.disabled = false;
      els.downloadBtnBottom.disabled = false;
      els.selectAllBtn.disabled = false;
      els.selectNoneBtn.disabled = false;
      renderRows();
      setStatus('Datei geladen.', 'ok');
    }

    async function uploadFile(file) {
      if (!file) return;

      const form = new FormData();
      form.append('file', file);
      setStatus('Datei wird geladen...');

      const response = await fetch('/api/analyze', { method: 'POST', body: form });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Die Datei konnte nicht geladen werden.');
      }

      applyAnalyzeResult(data);
    }

    async function loadServerFiles() {
      const response = await fetch('/api/files');
      const data = await response.json();
      const files = data.files || [];

      if (!files.length) {
        els.serverFileSelect.innerHTML = '<option value="">Keine ICS-Datei gefunden</option>';
        els.serverLoadBtn.disabled = true;
        return;
      }

      els.serverFileSelect.innerHTML = files
        .map(file => `<option value="${escapeHtml(file)}">${escapeHtml(file)}</option>`)
        .join('');
      els.serverLoadBtn.disabled = false;
    }

    async function loadSelectedServerFile() {
      const path = els.serverFileSelect.value;
      if (!path) return;

      setStatus('Datei aus /data wird geladen...');
      const response = await fetch('/api/open-server', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await response.json();

      if (!response.ok) {
        setStatus(data.error || 'Die Datei konnte nicht geladen werden.', 'error');
        return;
      }

      applyAnalyzeResult(data);
    }

    function rowTemplate(item, index) {
      const label = item.summary || '(ohne Titel)';
      return `
        <tr data-summary="${escapeHtml(item.summary.toLowerCase())}">
          <td class="select-col"><input type="checkbox" class="row-check" data-index="${index}"></td>
          <td class="summary">${escapeHtml(label)}</td>
          <td class="count">${item.count}</td>
          <td class="action-col">
            <select class="row-action" data-index="${index}">
              <option value="keep">Behalten</option>
              <option value="delete">Löschen</option>
              <option value="rename">Umbenennen</option>
            </select>
          </td>
          <td class="rename-col"><input class="rename-input" data-index="${index}" type="text" placeholder="Neuer Terminname" disabled></td>
        </tr>
      `;
    }

    function renderRows() {
      const filter = els.filterInput.value.trim().toLowerCase();
      const visible = state.summaries
        .map((item, index) => ({ ...item, index }))
        .filter(item => !filter || item.summary.toLowerCase().includes(filter));

      if (!visible.length) {
        els.tableBody.innerHTML = '<tr><td class="empty" colspan="5">Keine passenden Termine gefunden.</td></tr>';
        return;
      }

      els.tableBody.innerHTML = visible.map(item => rowTemplate(item, item.index)).join('');
    }

    els.tableBody.addEventListener('change', (event) => {
      if (event.target.classList.contains('row-action')) {
        const index = event.target.dataset.index;
        const row = event.target.closest('tr');
        const renameInput = row.querySelector('.rename-input');
        const checkbox = row.querySelector('.row-check');
        renameInput.disabled = event.target.value !== 'rename';
        if (event.target.value !== 'keep') checkbox.checked = true;
      }
    });

    els.filterInput.addEventListener('input', renderRows);

    els.selectAllBtn.addEventListener('click', () => {
      document.querySelectorAll('.row-check').forEach(input => input.checked = true);
    });

    els.selectNoneBtn.addEventListener('click', () => {
      document.querySelectorAll('.row-check').forEach(input => input.checked = false);
    });

    async function downloadEditedIcs() {
      if (!state.token) return;

      const actions = [];
      for (const checkbox of document.querySelectorAll('.row-check')) {
        if (!checkbox.checked) continue;
        const index = checkbox.dataset.index;
        const action = document.querySelector(`.row-action[data-index="${index}"]`).value;
        const rename = document.querySelector(`.rename-input[data-index="${index}"]`).value.trim();
        const summary = state.summaries[Number(index)].summary;

        if (action === 'rename' && !rename) {
          setStatus(`Für "${summary || '(ohne Titel)'}" fehlt der neue Name.`, 'error');
          return;
        }

        actions.push({ summary, action, rename });
      }

      if (!actions.length) {
        setStatus('Es wurde kein Termin ausgewählt.', 'error');
        return;
      }

      setStatus('Neue ICS wird erstellt...');
      const response = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: state.token, actions })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setStatus(data.error || 'Die neue ICS konnte nicht erstellt werden.', 'error');
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      link.href = url;
      link.download = match ? match[1] : `bearbeitet_${state.filename || 'termine.ics'}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setStatus('Neue ICS wurde erstellt.', 'ok');
    }

    els.downloadBtn.addEventListener('click', downloadEditedIcs);
    els.downloadBtnBottom.addEventListener('click', downloadEditedIcs);
    els.serverLoadBtn.addEventListener('click', loadSelectedServerFile);

    els.fileInput.addEventListener('change', async (event) => {
      try {
        await uploadFile(event.target.files[0]);
      } catch (error) {
        setStatus(error.message, 'error');
      }
    });

    for (const eventName of ['dragenter', 'dragover']) {
      els.dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropzone.classList.add('dragover');
      });
    }

    for (const eventName of ['dragleave', 'drop']) {
      els.dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropzone.classList.remove('dragover');
      });
    }

    els.dropzone.addEventListener('drop', async (event) => {
      try {
        await uploadFile(event.dataTransfer.files[0]);
      } catch (error) {
        setStatus(error.message, 'error');
      }
    });

    loadServerFiles().catch(() => {});
  </script>
</body>
</html>
"""


def cleanup_sessions():
    cutoff = time.time() - SESSION_TTL_SECONDS
    for token in list(sessions.keys()):
        if sessions[token]["created_at"] < cutoff:
            del sessions[token]


def edited_filename(filename: str) -> str:
    name = os.path.basename(filename) or "termine.ics"
    stem, ext = os.path.splitext(name)
    return f"{stem}_bearbeitet{ext or '.ics'}"


def analyze_raw(raw: str, filename: str):
    unfolded = unfold_ics_lines(raw)
    events, _ = parse_events(unfolded)

    if not events:
        return None, "In dieser Datei wurden keine VEVENT-Termine gefunden."

    counts = Counter(ev.summary_value for ev in events)
    summaries = [
        {"summary": summary, "count": count}
        for summary, count in sorted(counts.items(), key=lambda item: item[0].lower())
    ]

    token = uuid.uuid4().hex
    sessions[token] = {
        "created_at": time.time(),
        "filename": filename,
        "unfolded": unfolded,
        "events": events,
    }

    return {
        "token": token,
        "filename": filename,
        "event_count": len(events),
        "summaries": summaries,
    }, None


def configured_ics_dir() -> Path:
    return Path(os.environ.get("ICS_DIR", "/data")).resolve()


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/logo.png")
def logo():
    if LOGO_PATH.exists():
        return send_file(LOGO_PATH, mimetype="image/png")
    return Response(status=404)


@app.get("/favicon.png")
def favicon():
    if LOGO_PATH.exists():
        return send_file(LOGO_PATH, mimetype="image/png")
    return Response(status=404)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/files")
def files():
    root = configured_ics_dir()
    if not root.exists():
        return jsonify({"files": []})

    found = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".ics", ".ical"}:
            found.append(path.relative_to(root).as_posix())
        if len(found) >= 500:
            break

    return jsonify({"files": sorted(found, key=str.lower)})


@app.post("/api/open-server")
def open_server_file():
    cleanup_sessions()

    payload = request.get_json(silent=True) or {}
    rel_path = payload.get("path") or ""
    root = configured_ics_dir()
    target = (root / rel_path).resolve()

    if root not in target.parents and target != root:
        return jsonify({"error": "Ungültiger Dateipfad."}), 400

    if not target.is_file() or target.suffix.lower() not in {".ics", ".ical"}:
        return jsonify({"error": "Die Datei wurde nicht gefunden."}), 404

    raw = target.read_text(encoding="utf-8", errors="replace")
    result, error = analyze_raw(raw, target.name)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result)


@app.post("/api/analyze")
def analyze():
    cleanup_sessions()

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Es wurde keine Datei hochgeladen."}), 400

    raw = uploaded.read().decode("utf-8", errors="replace")
    result, error = analyze_raw(raw, uploaded.filename)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result)


@app.post("/api/export")
def export():
    cleanup_sessions()

    payload = request.get_json(silent=True) or {}
    token = payload.get("token")
    session = sessions.get(token)
    if session is None:
        return jsonify({"error": "Die geladene Datei ist nicht mehr verfügbar. Bitte lade sie erneut."}), 400

    delete_summaries = set()
    rename_map = {}
    for item in payload.get("actions", []):
        summary = item.get("summary", "")
        action = item.get("action")
        if action == "delete":
            delete_summaries.add(summary)
        elif action == "rename":
            new_name = (item.get("rename") or "").strip()
            if not new_name:
                return jsonify({"error": f"Bei '{summary}' fehlt der neue Name."}), 400
            rename_map[summary] = new_name

    new_unfolded = apply_changes_to_ics(
        session["unfolded"],
        session["events"],
        delete_summaries,
        rename_map
    )
    new_ics = fold_ics_lines(new_unfolded)
    filename = edited_filename(session["filename"])

    return Response(
        new_ics,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", os.environ.get("NOVNC_PORT", "8080")))
    app.run(host="0.0.0.0", port=port)
