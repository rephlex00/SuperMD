"""Lightweight web GUI for editing SuperMD configuration."""

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from pydantic import ValidationError

from .config import SuperMDConfig

_yaml = YAML()
_yaml.preserve_quotes = True

_MULTILINE_KEYS = {"prompt", "title_prompt", "note_title_prompt", "template"}


def _to_plain(data):
    """Convert ruamel CommentedMap/CommentedSeq to plain dicts/lists for JSON."""
    if isinstance(data, dict):
        return {k: _to_plain(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_to_plain(item) for item in data]
    return data


def _update_yaml_doc(doc: CommentedMap, data: dict) -> CommentedMap:
    """Update a ruamel round-trip document in-place from a plain dict.

    Preserves comments and ordering for existing keys. New keys are appended.
    Removed keys are deleted.
    """
    # Remove keys that are no longer in data
    for key in list(doc):
        if key not in data:
            del doc[key]

    for key, value in data.items():
        if key == "defaults" and isinstance(value, dict):
            if key not in doc or not isinstance(doc[key], dict):
                doc[key] = CommentedMap()
            sub = doc[key]
            for sk in list(sub):
                if sk not in value:
                    del sub[sk]
            for sk, sv in value.items():
                sub[sk] = sv
        elif key == "jobs" and isinstance(value, list):
            seq = CommentedSeq()
            for job in value:
                m = CommentedMap()
                for jk, jv in job.items():
                    m[jk] = jv
                seq.append(m)
            doc[key] = seq
        elif key in _MULTILINE_KEYS and isinstance(value, str) and "\n" in value:
            doc[key] = LiteralScalarString(value)
        else:
            doc[key] = value

    return doc


# ---------------------------------------------------------------------------
# HTML SPA
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SuperMD Configuration</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
<style>
:root {
  --pico-font-size: 93.75%;
}
body { padding-bottom: 4rem; }
header.container { display: flex; align-items: center; justify-content: space-between; }
header h1 { margin: 0; font-size: 1.6rem; }
#config-path { font-size: .8rem; color: var(--pico-muted-color); margin: 0; }
.section-title { margin-top: 2rem; margin-bottom: .5rem; border-bottom: 2px solid var(--pico-primary); padding-bottom: .25rem; }
textarea { font-family: monospace; font-size: .85rem; min-height: 6rem; }
.job-card { position: relative; }
.job-card .remove-btn {
  position: absolute; top: .75rem; right: .75rem;
  background: var(--pico-del-color); color: #fff; border: none;
  border-radius: 4px; padding: .25rem .6rem; cursor: pointer; font-size: .8rem;
}
.job-card .remove-btn:hover { opacity: .8; }
#add-job-btn { margin-top: .5rem; }
.save-bar {
  position: fixed; bottom: 0; left: 0; right: 0;
  background: var(--pico-background-color);
  border-top: 1px solid var(--pico-muted-border-color);
  padding: .75rem 1.5rem; display: flex; align-items: center; gap: 1rem;
  z-index: 100;
}
.save-bar button { margin: 0; width: auto; }
#status { font-size: .85rem; }
#status.ok { color: var(--pico-ins-color); }
#status.err { color: var(--pico-del-color); }
details summary { cursor: pointer; font-size: .9rem; color: var(--pico-muted-color); }
.override-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1.5rem; }
.theme-toggle { background: none; border: none; cursor: pointer; font-size: 1.3rem; padding: .25rem; }
</style>
</head>
<body>
<header class="container">
  <div>
    <h1>SuperMD Configuration</h1>
    <p id="config-path">Loading…</p>
  </div>
  <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark mode">🌓</button>
</header>

<main class="container">

  <!-- AI Settings -->
  <h2 class="section-title">AI Settings</h2>
  <label>Model
    <input type="text" id="model" placeholder="gpt-4o-mini">
    <small>LLM model name (e.g. gpt-4o-mini, gemini/gemini-2.5-flash, claude-sonnet-4-6)</small>
  </label>

  <!-- Prompts -->
  <h2 class="section-title">Prompts</h2>
  <label>Transcription Prompt
    <textarea id="prompt" rows="12" placeholder="Page transcription prompt…"></textarea>
    <small>Sent per page image. Use {context} for previous-page continuity.</small>
  </label>
  <label>Title Prompt
    <textarea id="title_prompt" rows="4" placeholder="Title extraction prompt…"></textarea>
    <small>Used for image-to-title extraction.</small>
  </label>
  <label>Note Title Prompt <mark>optional</mark>
    <textarea id="note_title_prompt" rows="4" placeholder="Leave empty to disable title derivation"></textarea>
    <small>If set, a second LLM call generates a title. Use {markdown} placeholder. Leave empty to disable.</small>
  </label>

  <!-- Output Templates -->
  <h2 class="section-title">Output Templates</h2>
  <label>Output Path Template
    <input type="text" id="output_path_template" placeholder="{{file_basename}}">
    <small>Jinja2 template for output subdirectory. Supports {{DATE:format}} tokens.</small>
  </label>
  <label>Output Filename Template
    <input type="text" id="output_filename_template" placeholder="{{file_basename}}.md">
    <small>Jinja2 template for output filename.</small>
  </label>
  <label>Output File Template (Jinja2)
    <textarea id="template" rows="14" placeholder="---\ncreated: {{DATE:YYYY-MM-DD}}\n---\n{{llm_output}}"></textarea>
    <small>Rendered once per input file to produce the final .md output.</small>
  </label>

  <!-- Processing Defaults -->
  <h2 class="section-title">Processing Defaults</h2>
  <div class="grid">
    <label>Log Level
      <select id="defaults.level">
        <option value="DEBUG">DEBUG</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
      </select>
    </label>
    <label>Cooldown (seconds)
      <input type="number" id="defaults.cooldown" step="0.5" min="0" value="5.0">
    </label>
  </div>
  <fieldset>
    <label><input type="checkbox" id="defaults.force" role="switch"> Force reprocessing</label>
    <label><input type="checkbox" id="defaults.progress" role="switch" checked> Show progress bar</label>
  </fieldset>

  <!-- Jobs -->
  <h2 class="section-title">Jobs</h2>
  <div id="jobs-container"></div>
  <button type="button" id="add-job-btn" class="secondary outline">+ Add Job</button>

</main>

<div class="save-bar">
  <button id="save-btn" onclick="saveConfig()">Save Configuration</button>
  <button class="secondary outline" onclick="loadConfig()">Reload</button>
  <span id="status"></span>
</div>

<script>
// --- Theme ---
function toggleTheme() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', html.dataset.theme);
}
(function() {
  const saved = localStorage.getItem('theme');
  if (saved) document.documentElement.dataset.theme = saved;
})();

// --- Auto-grow textareas ---
document.addEventListener('input', e => {
  if (e.target.tagName === 'TEXTAREA') {
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  }
});

// --- Config load/save ---
async function loadConfig() {
  try {
    const [cfgRes, pathRes] = await Promise.all([
      fetch('/api/config'),
      fetch('/api/config/path')
    ]);
    const cfg = await cfgRes.json();
    const pathData = await pathRes.json();
    document.getElementById('config-path').textContent = 'Config: ' + pathData.path;
    populateForm(cfg);
    setStatus('Loaded', 'ok');
  } catch (e) {
    setStatus('Failed to load config: ' + e.message, 'err');
  }
}

function populateForm(cfg) {
  // Simple fields
  document.getElementById('model').value = cfg.model || '';
  document.getElementById('prompt').value = cfg.prompt || '';
  document.getElementById('title_prompt').value = cfg.title_prompt || '';
  document.getElementById('note_title_prompt').value = cfg.note_title_prompt || '';
  document.getElementById('output_path_template').value = cfg.output_path_template || '';
  document.getElementById('output_filename_template').value = cfg.output_filename_template || '';
  document.getElementById('template').value = cfg.template || '';

  // Defaults
  const d = cfg.defaults || {};
  document.getElementById('defaults.force').checked = !!d.force;
  document.getElementById('defaults.progress').checked = d.progress !== false;
  document.getElementById('defaults.level').value = d.level || 'INFO';
  document.getElementById('defaults.cooldown').value = d.cooldown != null ? d.cooldown : 5.0;

  // Jobs
  const container = document.getElementById('jobs-container');
  container.innerHTML = '';
  (cfg.jobs || []).forEach(job => addJobCard(job));

  // Trigger auto-grow
  document.querySelectorAll('textarea').forEach(ta => {
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  });
}

function gatherConfig() {
  const cfg = {};
  cfg.model = document.getElementById('model').value;
  cfg.prompt = document.getElementById('prompt').value;
  cfg.title_prompt = document.getElementById('title_prompt').value;
  const ntp = document.getElementById('note_title_prompt').value.trim();
  cfg.note_title_prompt = ntp || null;
  cfg.output_path_template = document.getElementById('output_path_template').value;
  cfg.output_filename_template = document.getElementById('output_filename_template').value;
  cfg.template = document.getElementById('template').value;

  cfg.defaults = {
    force: document.getElementById('defaults.force').checked,
    progress: document.getElementById('defaults.progress').checked,
    level: document.getElementById('defaults.level').value,
    cooldown: parseFloat(document.getElementById('defaults.cooldown').value) || 0
  };

  cfg.jobs = [];
  document.querySelectorAll('.job-card').forEach(card => {
    const job = {
      name: card.querySelector('.job-name').value,
      input: card.querySelector('.job-input').value,
      output: card.querySelector('.job-output').value,
    };
    // Overrides — only include if the user set a value
    const m = card.querySelector('.job-model').value.trim();
    if (m) job.model = m;
    const f = card.querySelector('.job-force');
    if (f.indeterminate === false && f.dataset.set === '1') job.force = f.checked;
    const p = card.querySelector('.job-progress');
    if (p.indeterminate === false && p.dataset.set === '1') job.progress = p.checked;
    const l = card.querySelector('.job-level').value;
    if (l) job.level = l;
    const c = card.querySelector('.job-cooldown').value.trim();
    if (c !== '') job.cooldown = parseFloat(c);
    cfg.jobs.push(job);
  });

  return cfg;
}

async function saveConfig() {
  const btn = document.getElementById('save-btn');
  btn.setAttribute('aria-busy', 'true');
  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(gatherConfig())
    });
    const data = await res.json();
    if (res.ok) {
      setStatus('Saved successfully', 'ok');
    } else {
      setStatus('Error: ' + (data.error || 'Unknown error'), 'err');
    }
  } catch (e) {
    setStatus('Save failed: ' + e.message, 'err');
  } finally {
    btn.removeAttribute('aria-busy');
  }
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = cls || '';
  if (cls === 'ok') setTimeout(() => { if (el.textContent === msg) el.textContent = ''; }, 3000);
}

// --- Jobs ---
let jobCounter = 0;

function addJobCard(job) {
  job = job || {name: '', input: '', output: ''};
  const container = document.getElementById('jobs-container');
  const id = jobCounter++;
  const card = document.createElement('article');
  card.className = 'job-card';
  card.innerHTML = `
    <button type="button" class="remove-btn" onclick="this.closest('.job-card').remove()">Remove</button>
    <div class="grid">
      <label>Job Name<input type="text" class="job-name" value="${esc(job.name)}"></label>
    </div>
    <div class="grid">
      <label>Input Directory<input type="text" class="job-input" value="${esc(job.input || '')}"></label>
      <label>Output Directory<input type="text" class="job-output" value="${esc(job.output || '')}"></label>
    </div>
    <details>
      <summary>Advanced overrides</summary>
      <div class="override-grid">
        <label>Model override<input type="text" class="job-model" value="${esc(job.model || '')}" placeholder="Inherit global"></label>
        <label>Log Level override
          <select class="job-level">
            <option value="">Inherit global</option>
            <option value="DEBUG" ${job.level==='DEBUG'?'selected':''}>DEBUG</option>
            <option value="INFO" ${job.level==='INFO'?'selected':''}>INFO</option>
            <option value="WARNING" ${job.level==='WARNING'?'selected':''}>WARNING</option>
            <option value="ERROR" ${job.level==='ERROR'?'selected':''}>ERROR</option>
          </select>
        </label>
        <label>Cooldown override<input type="number" class="job-cooldown" step="0.5" min="0" value="${job.cooldown != null ? job.cooldown : ''}" placeholder="Inherit global"></label>
        <div>
          <label><input type="checkbox" class="job-force" role="switch" ${job.force?'checked':''} data-set="${job.force!=null?'1':'0'}" onchange="this.dataset.set='1'"> Force reprocessing</label>
          <label><input type="checkbox" class="job-progress" role="switch" ${job.progress!==false?'checked':''} data-set="${job.progress!=null?'1':'0'}" onchange="this.dataset.set='1'"> Show progress</label>
        </div>
      </div>
    </details>
  `;
  container.appendChild(card);
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('add-job-btn').addEventListener('click', () => addJobCard());

// --- Init ---
loadConfig();
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class ConfigHandler(BaseHTTPRequestHandler):
    """Serves the config GUI SPA and REST API."""

    config_path: str = ""

    def log_message(self, format, *args):  # noqa: A002
        # Silence default stderr logging
        pass

    # --- Helpers ---

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    # --- Routes ---

    def do_GET(self):  # noqa: N802
        if self.path == "/":
            self._send_html(HTML_PAGE)
        elif self.path == "/api/config":
            self._handle_get_config()
        elif self.path == "/api/config/path":
            self._send_json({"path": self.config_path})
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        if self.path == "/api/config":
            self._handle_post_config()
        else:
            self.send_error(404)

    # --- GET /api/config ---

    def _handle_get_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = _yaml.load(f) or {}
            self._send_json(_to_plain(raw))
        else:
            # Return defaults when file doesn't exist yet
            self._send_json(SuperMDConfig().model_dump())

    # --- POST /api/config ---

    def _handle_post_config(self):
        try:
            data = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json({"error": f"Invalid JSON: {exc}"}, 400)
            return

        # Validate through Pydantic
        try:
            SuperMDConfig(**data)
        except ValidationError as exc:
            errors = exc.errors()
            msg = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors
            )
            self._send_json({"error": msg}, 400)
            return

        # Clean None values from jobs overrides
        if "jobs" in data:
            for job in data["jobs"]:
                for key in list(job):
                    if job[key] is None:
                        del job[key]

        # Remove top-level None values
        data = {k: v for k, v in data.items() if v is not None}

        # Load existing YAML to preserve comments, or start fresh
        doc = CommentedMap()
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = _yaml.load(f)
                if loaded is not None:
                    doc = loaded

        # Update in-place (preserves comments on existing keys)
        _update_yaml_doc(doc, data)

        # Write YAML
        os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            _yaml.dump(doc, f)

        self._send_json({"ok": True})


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def start_server(config_path: str, port: int = 8734):
    """Start the configuration GUI HTTP server."""
    ConfigHandler.config_path = os.path.abspath(config_path)
    server = HTTPServer(("127.0.0.1", port), ConfigHandler)
    url = f"http://localhost:{port}"
    print(f"SuperMD GUI running at {url}")
    print(f"Editing: {ConfigHandler.config_path}")
    print("Press Ctrl+C to stop")
    try:
        webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down GUI server")
        server.server_close()
