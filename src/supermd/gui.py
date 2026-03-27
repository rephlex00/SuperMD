"""Lightweight web GUI for editing SuperMD configuration."""

import json
import os
import secrets
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

/* ── Light theme: solarized purple ── */
:root[data-theme="light"],
[data-theme="light"] {
  --pico-primary: #6c3483;
  --pico-primary-hover: #512e6a;
  --pico-primary-focus: rgba(108, 52, 131, .2);
  --pico-primary-inverse: #fff;
  --pico-background-color: #fdf6ff;
  --pico-card-background-color: #f5ecf8;
  --pico-card-sectioning-background-color: #efe4f3;
  --pico-muted-color: #7c6b85;
  --pico-muted-border-color: #d8c6e0;
  --pico-color: #2d1b38;
  --pico-h1-color: #4a1a6b;
  --pico-h2-color: #5b2d7a;
  --pico-h3-color: #6c3483;
  --pico-form-element-background-color: #fff;
  --pico-form-element-color: #2d1b38;
  --pico-form-element-border-color: #c9a8d8;
  --pico-form-element-focus-color: #6c3483;
  --pico-switch-color: #d8c6e0;
  --pico-switch-checked-background-color: #6c3483;
  --pico-secondary: #8e5ea2;
  --pico-secondary-hover: #7a4d8e;
  --pico-ins-color: #5a8a5e;
  --pico-del-color: #b34040;
  --pico-mark-background-color: #e8d0f0;
  --pico-mark-color: #4a1a6b;
}

/* ── Dark theme: deep near-black purple ── */
:root[data-theme="dark"],
[data-theme="dark"] {
  --pico-primary: #b48ece;
  --pico-primary-hover: #c9a8e0;
  --pico-primary-focus: rgba(180, 142, 206, .25);
  --pico-primary-inverse: #110b18;
  --pico-background-color: #0e0812;
  --pico-card-background-color: #170f1f;
  --pico-card-sectioning-background-color: #1e1429;
  --pico-muted-color: #8a7399;
  --pico-muted-border-color: #2e2240;
  --pico-color: #ddd0e8;
  --pico-h1-color: #d4b8e8;
  --pico-h2-color: #c9a8de;
  --pico-h3-color: #b48ece;
  --pico-form-element-background-color: #150e1c;
  --pico-form-element-color: #ddd0e8;
  --pico-form-element-border-color: #3a2a50;
  --pico-form-element-focus-color: #b48ece;
  --pico-switch-color: #3a2a50;
  --pico-switch-checked-background-color: #9a6fbf;
  --pico-secondary: #9a6fbf;
  --pico-secondary-hover: #b48ece;
  --pico-ins-color: #7acc80;
  --pico-del-color: #e06060;
  --pico-mark-background-color: #2e1a42;
  --pico-mark-color: #d4b8e8;
  --pico-table-border-color: #2e2240;
  --pico-code-background-color: #1a1024;
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
.theme-toggle {
  background: none; border: 1px solid var(--pico-muted-border-color);
  cursor: pointer; font-size: .85rem; padding: .3rem .7rem;
  border-radius: 4px; color: var(--pico-muted-color);
}
.theme-toggle:hover { border-color: var(--pico-primary); color: var(--pico-primary); }
#login-overlay {
  display: none; position: fixed; inset: 0; z-index: 200;
  background: var(--pico-background-color);
  justify-content: center; align-items: center;
}
#login-overlay.active { display: flex; }
#login-box { width: 100%; max-width: 24rem; padding: 2rem; }
#login-box h2 { margin-top: 0; }
#login-error { color: var(--pico-del-color); font-size: .85rem; min-height: 1.2em; }
.hint {
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.1rem; height: 1.1rem; border-radius: 50%;
  background: var(--pico-muted-border-color); color: var(--pico-color);
  font-size: .7rem; font-weight: 700; cursor: help;
  position: relative; vertical-align: middle; margin-left: .35rem;
  line-height: 1; user-select: none; flex-shrink: 0;
}
.hint:hover { background: var(--pico-primary); color: var(--pico-primary-inverse); }
.hint::after {
  content: attr(data-tip);
  position: absolute; bottom: calc(100% + .5rem); left: 50%;
  transform: translateX(-50%);
  background: var(--pico-card-background-color);
  color: var(--pico-color);
  border: 1px solid var(--pico-muted-border-color);
  border-radius: 6px; padding: .5rem .75rem;
  font-size: .78rem; font-weight: 400; line-height: 1.4;
  width: max-content; max-width: 22rem;
  white-space: normal; text-align: left;
  pointer-events: none; opacity: 0;
  transition: opacity .15s;
  z-index: 50; box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
.hint:hover::after { opacity: 1; }
</style>
</head>
<body>
<header class="container">
  <div>
    <h1>SuperMD Configuration</h1>
    <p id="config-path">Loading…</p>
  </div>
  <button class="theme-toggle" id="theme-btn" onclick="toggleTheme()" title="Toggle dark mode"></button>
</header>

<main class="container">

  <!-- AI Settings -->
  <h2 class="section-title">AI Settings</h2>
  <label>Model <span class="hint" data-tip="The LLM model used to transcribe each page. Requires the matching llm plugin installed (e.g. llm-gemini for Gemini models). Can be overridden per-job.">?</span>
    <input type="text" id="model" placeholder="gpt-4o-mini">
    <small>LLM model name (e.g. gpt-4o-mini, gemini/gemini-2.5-flash, claude-sonnet-4-6)</small>
  </label>

  <!-- Prompts -->
  <h2 class="section-title">Prompts</h2>
  <label>Transcription Prompt <span class="hint" data-tip="Sent to the LLM once per page image. Substitutions: {context} — replaced with the previous page's Markdown output so the model has continuity across multi-page notes.">?</span>
    <textarea id="prompt" rows="12" placeholder="Page transcription prompt…"></textarea>
    <small>Sent per page image. Use {context} for previous-page continuity.</small>
  </label>
  <label>Title Prompt <span class="hint" data-tip="Prompt used for image-to-title extraction from notebook title annotations. Only applies to .note files that contain title metadata. No substitutions available — the page title image is sent alongside this prompt.">?</span>
    <textarea id="title_prompt" rows="4" placeholder="Title extraction prompt…"></textarea>
    <small>Used for image-to-title extraction.</small>
  </label>
  <label>Note Title Prompt <mark>optional</mark> <span class="hint" data-tip="If set, a second LLM call runs after all pages are transcribed to derive a short title. Leave empty to disable. Substitutions: {markdown} — the full assembled transcription text. The result is available as {{title}} in output templates.">?</span>
    <textarea id="note_title_prompt" rows="4" placeholder="Leave empty to disable title derivation"></textarea>
    <small>If set, a second LLM call generates a title. Use {markdown} placeholder. Leave empty to disable.</small>
  </label>

  <!-- Output Templates -->
  <h2 class="section-title">Output Templates</h2>
  <label>Output Path Template <span class="hint" data-tip="Jinja2 template for the output subdirectory relative to the job's output path. Variables: {{file_basename}} — input filename without extension, {{title}} — LLM-derived title, {{ctime}} / {{mtime}} — datetime objects. DATE tokens: {{DATE:YYYY}}, {{DATE:MM}}, {{DATE:MMM}}, {{DATE:DD}}, {{DATE:dddd}}, etc. Example: {{DATE:YYYY/MM MMM}} → 2026/03 Mar">?</span>
    <input type="text" id="output_path_template" placeholder="{{file_basename}}">
    <small>Jinja2 template for output subdirectory. Supports {{DATE:format}} tokens.</small>
  </label>
  <label>Output Filename Template <span class="hint" data-tip="Jinja2 template for the output filename. Same variables and DATE tokens as Output Path Template. Example: {{DATE:YYMMDD}}-{{file_basename}}.md → 260313-20260313_143000.md">?</span>
    <input type="text" id="output_filename_template" placeholder="{{file_basename}}.md">
    <small>Jinja2 template for output filename.</small>
  </label>
  <label>Output File Template (Jinja2) <span class="hint" data-tip="Full Jinja2 template for the final .md file. All variables from path/filename templates plus: {{llm_output}} / {{markdown}} — the full transcription, {{images}} — list of page images (each has .name, .rel_path, .abs_path), {{links}} — notebook cross-references (.note only), {{keywords}} — notebook keywords (.note only), {{titles}} — notebook title annotations (.note only). Supports DATE tokens, conditionals, loops, and all Jinja2 syntax.">?</span>
    <textarea id="template" rows="14" placeholder="---\ncreated: {{DATE:YYYY-MM-DD}}\n---\n{{llm_output}}"></textarea>
    <small>Rendered once per input file to produce the final .md output.</small>
  </label>

  <!-- Processing Defaults -->
  <h2 class="section-title">Processing Defaults</h2>
  <div class="grid">
    <label>Log Level <span class="hint" data-tip="Controls log verbosity. DEBUG shows all internal details, INFO shows conversion progress, WARNING and ERROR show only problems.">?</span>
      <select id="defaults.level">
        <option value="DEBUG">DEBUG</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
      </select>
    </label>
    <label>Cooldown (seconds) <span class="hint" data-tip="Delay between successive LLM calls for pages within a single file. Helps avoid rate-limit errors from the API provider. Set to 0 to disable.">?</span>
      <input type="number" id="defaults.cooldown" step="0.5" min="0" value="5.0">
    </label>
  </div>
  <fieldset>
    <label><input type="checkbox" id="defaults.force" role="switch"> Force reprocessing <span class="hint" data-tip="When enabled, re-process files even if the input hash is unchanged or the output has been hand-edited. Does not override ignoresnlock protection.">?</span></label>
    <label><input type="checkbox" id="defaults.progress" role="switch" checked> Show progress bar <span class="hint" data-tip="Show a tqdm progress bar during conversion. Automatically disabled when running multiple jobs in parallel.">?</span></label>
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

<div id="login-overlay">
  <div id="login-box">
    <h2>SuperMD Configuration</h2>
    <p>Enter the auth token to continue. The token is printed in the server logs at startup.</p>
    <label>Auth Token
      <input type="password" id="login-token" placeholder="Paste token here" autofocus>
    </label>
    <p id="login-error"></p>
    <button id="login-btn" onclick="submitLogin()">Authenticate</button>
  </div>
</div>

<script>
// --- Theme ---
function _getCookie(name) {
  const m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : null;
}
function _setCookie(name, val) {
  document.cookie = name + '=' + encodeURIComponent(val) + ';path=/;max-age=31536000;SameSite=Lax';
}
function _applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
}
function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  _setCookie('supermd_theme', next);
  _applyTheme(next);
}
(function() {
  const saved = _getCookie('supermd_theme') || 'light';
  _applyTheme(saved);
})();

// --- Auto-grow textareas ---
document.addEventListener('input', e => {
  if (e.target.tagName === 'TEXTAREA') {
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  }
});

// --- Auth ---
function _getToken() { return sessionStorage.getItem('supermd_token') || ''; }
function _headers(extra) {
  const h = Object.assign({}, extra || {});
  const t = _getToken();
  if (t) h['Authorization'] = 'Bearer ' + t;
  return h;
}

function showLogin(msg) {
  document.getElementById('login-overlay').classList.add('active');
  document.getElementById('login-error').textContent = msg || '';
  document.getElementById('login-token').focus();
}

function hideLogin() {
  document.getElementById('login-overlay').classList.remove('active');
  document.getElementById('login-error').textContent = '';
}

async function submitLogin() {
  const input = document.getElementById('login-token');
  const token = input.value.trim();
  if (!token) { document.getElementById('login-error').textContent = 'Token is required'; return; }
  sessionStorage.setItem('supermd_token', token);
  // Test the token
  const res = await fetch('/api/config/path', {headers: _headers()});
  if (res.status === 401) {
    sessionStorage.removeItem('supermd_token');
    document.getElementById('login-error').textContent = 'Invalid token';
    return;
  }
  hideLogin();
  loadConfig();
}

document.getElementById('login-token').addEventListener('keydown', e => {
  if (e.key === 'Enter') submitLogin();
});

// --- Config load/save ---
async function loadConfig() {
  try {
    const [cfgRes, pathRes] = await Promise.all([
      fetch('/api/config', {headers: _headers()}),
      fetch('/api/config/path', {headers: _headers()})
    ]);
    if (cfgRes.status === 401 || pathRes.status === 401) {
      showLogin(''); return;
    }
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
      headers: _headers({'Content-Type': 'application/json'}),
      body: JSON.stringify(gatherConfig())
    });
    if (res.status === 401) { showLogin('Session expired'); return; }
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
    auth_token: str = ""  # empty = no auth required

    def log_message(self, format, *args):  # noqa: A002
        # Silence default stderr logging
        pass

    # --- Auth ---

    def _check_auth(self):
        """Return True if request is authorized."""
        if not self.auth_token:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {self.auth_token}"

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
        elif self.path.startswith("/api/"):
            if not self._check_auth():
                self._send_json({"error": "Unauthorized"}, 401)
                return
            if self.path == "/api/config":
                self._handle_get_config()
            elif self.path == "/api/config/path":
                self._send_json({"path": self.config_path})
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        if not self._check_auth():
            self._send_json({"error": "Unauthorized"}, 401)
            return
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

def start_server(
    config_path: str,
    port: int = 8734,
    host: str = "127.0.0.1",
    token: str | None = None,
):
    """Start the configuration GUI HTTP server."""
    ConfigHandler.config_path = os.path.abspath(config_path)

    # Auto-generate a token when binding to a non-localhost address
    is_local = host in ("127.0.0.1", "localhost", "::1")
    if token:  # non-empty explicit token
        ConfigHandler.auth_token = token
    elif not is_local:
        ConfigHandler.auth_token = secrets.token_urlsafe(32)
    else:
        ConfigHandler.auth_token = ""

    server = HTTPServer((host, port), ConfigHandler)
    url = f"http://{host}:{port}"
    print(f"SuperMD GUI running at {url}")
    print(f"Editing: {ConfigHandler.config_path}")
    if ConfigHandler.auth_token:
        print(f"Auth token: {ConfigHandler.auth_token}")
    print("Press Ctrl+C to stop")
    try:
        if is_local:
            webbrowser.open(f"http://localhost:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down GUI server")
        server.server_close()
