"""
web.py — Servidor web local para el panel de agentes.
Abre automáticamente el browser en http://localhost:7070

Uso:
    python web.py
    python web.py --puerto 8080
"""

import sys
import os
import json
import threading
import importlib
import inspect
import subprocess
import webbrowser
import argparse
import queue
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, Response, send_from_directory
from agentes.registry import AGENTES, CATEGORIAS

app = Flask(__name__, static_folder=None)

# Cola de logs por ejecución (job_id → queue)
_jobs: dict[str, dict] = {}

# ── utilidades ────────────────────────────────────────────────────────────────

def _coerce(valor, tipo, default=None):
    """Convierte valor del form al tipo esperado."""
    if valor is None or valor == "":
        return default
    if tipo == "bool":
        return valor in (True, "true", "1", "on", "yes")
    if tipo == "entero":
        try:
            return int(valor)
        except Exception:
            return default
    if tipo == "archivo_multiple":
        try:
            parsed = json.loads(valor) if isinstance(valor, str) else valor
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return valor


# ── rutas API ─────────────────────────────────────────────────────────────────

@app.route("/api/agentes")
def api_agentes():
    """Devuelve el registry completo."""
    return jsonify({"agentes": AGENTES, "categorias": CATEGORIAS})


@app.route("/api/ejecutar", methods=["POST"])
def api_ejecutar():
    """
    Lanza un agente en un thread separado.
    Body JSON: { "agente": "key", "params": { ... } }
    Devuelve: { "job_id": "..." }
    """
    body   = request.get_json(force=True)
    key    = body.get("agente")
    params = body.get("params", {})

    if key not in AGENTES:
        return jsonify({"error": f"Agente desconocido: {key}"}), 400

    ag = AGENTES[key]

    # Construir kwargs
    kwargs = {}
    for p in ag["parametros"]:
        nombre  = p["nombre"]
        tipo    = p["tipo"]
        default = p.get("default")
        val     = params.get(nombre)
        kwargs[nombre] = _coerce(val, tipo, default)

        if p.get("requerido") and not kwargs[nombre]:
            return jsonify({"error": f"Parámetro requerido: {p['label']}"}), 400

    job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = {"queue": q, "status": "running", "resultado": None}

    def _run():
        class LogCapture:
            def write(self, msg):
                if msg.strip():
                    q.put({"tipo": "log", "texto": msg.rstrip()})
            def flush(self):
                pass

        orig = sys.stdout
        sys.stdout = LogCapture()
        try:
            import os
            if not os.environ.get('ANTHROPIC_API_KEY'):
                raise ValueError("Falta ANTHROPIC_API_KEY. Configurala en el archivo .env")
            modulo  = importlib.import_module(ag["modulo"])
            funcion = getattr(modulo, ag["funcion"])
            sig     = inspect.signature(funcion)
            if "verbose" in sig.parameters:
                kwargs["verbose"] = True
            resultado = funcion(**kwargs)
            sys.stdout = orig
            _jobs[job_id]["status"]    = "ok"
            _jobs[job_id]["resultado"] = str(resultado) if resultado else ""
            q.put({"tipo": "fin", "status": "ok", "resultado": str(resultado or "")})
        except Exception as e:
            import traceback
            sys.stdout = orig
            _jobs[job_id]["status"] = "error"
            q.put({"tipo": "log",  "texto": traceback.format_exc()})
            q.put({"tipo": "fin",  "status": "error", "resultado": str(e)})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/stream/<job_id>")
def api_stream(job_id):
    """Server-Sent Events: transmite el log del job en tiempo real."""
    if job_id not in _jobs:
        return jsonify({"error": "job no encontrado"}), 404

    def generate():
        q = _jobs[job_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=60)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("tipo") == "fin":
                    break
            except queue.Empty:
                yield "data: {\"tipo\":\"ping\"}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/abrir-archivo", methods=["POST"])
def api_abrir_archivo():
    """Abre un archivo con la app por defecto del sistema."""
    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not Path(path).exists():
        return jsonify({"error": "archivo no encontrado"}), 404
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/elegir-archivo", methods=["POST"])
def api_elegir_archivo():
    """Abre el diálogo nativo de archivos y devuelve la ruta elegida."""
    body = request.get_json(force=True)
    extensiones = body.get("extensiones", [])
    es_salida   = body.get("es_salida", False)

    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        if es_salida:
            path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")]
            )
        else:
            ftypes = [(e.upper().lstrip("."), f"*{e}") for e in extensiones] + \
                     [("Todos", "*.*")]
            path = filedialog.askopenfilename(filetypes=ftypes)

        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-temp", methods=["POST"])
def api_upload_temp():
    """Recibe un archivo subido desde el browser y lo guarda en un directorio temporal.
    Devuelve la ruta absoluta para pasarla al agente."""
    if "archivo" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    f = request.files["archivo"]
    if not f.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    suffix = Path(f.filename).suffix.lower()
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                         prefix="agente_upload_")
    tmp_path = tmp.name
    tmp.close()
    f.save(tmp_path)
    return jsonify({"path": tmp_path, "nombre": f.filename})


@app.route("/api/ejecutar-multi-pdf", methods=["POST"])
def api_ejecutar_multi_pdf():
    """Lanza run_batch con múltiples PDFs. Body: { "archivos": [...] }"""
    body     = request.get_json(force=True)
    archivos = body.get("archivos", [])
    if not archivos:
        return jsonify({"error": "No se enviaron archivos"}), 400

    job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = {"queue": q, "status": "running", "resultado": None}

    def _run():
        class LogCapture:
            def write(self, msg):
                if msg.strip():
                    q.put({"tipo": "log", "texto": msg.rstrip()})
            def flush(self):
                pass
        orig = sys.stdout
        sys.stdout = LogCapture()
        try:
            from agentes.subir_pdf.subir_pdf import run_batch
            resultado = run_batch(archivos, verbose=True)
            sys.stdout = orig
            _jobs[job_id]["status"]    = "ok"
            _jobs[job_id]["resultado"] = resultado
            q.put({"tipo": "fin", "status": "ok", "resultado": resultado})
        except Exception as e:
            import traceback
            sys.stdout = orig
            _jobs[job_id]["status"] = "error"
            q.put({"tipo": "log",  "texto": traceback.format_exc()})
            q.put({"tipo": "fin",  "status": "error", "resultado": str(e)})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── HTML principal ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentes — Galli CBC</title>
<style>
  :root {
    --purple: #534AB7; --purple-lt: #EEEDFE; --green: #1D9E75;
    --teal: #0F6E56;   --red: #E24B4A;        --orange: #D85A30;
    --dark: #2C2C2A;   --gray: #888780;        --gray-lt: #F1EFE8;
    --bg: #F8F8F6;     --white: #FFFFFF;       --border: #D9D8D2;
    --sidebar-w: 260px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
         color: var(--dark); height: 100vh; display: flex; flex-direction: column; }

  /* topbar */
  #topbar { background: var(--purple); height: 52px; display: flex;
            align-items: center; padding: 0 20px; gap: 12px; flex-shrink: 0; }
  #topbar .logo { color: #fff; font-weight: 700; font-size: 17px; letter-spacing: .5px; }
  #topbar .sub  { color: #CECBF6; font-size: 12px; }

  /* layout */
  #layout { display: flex; flex: 1; overflow: hidden; }

  /* sidebar */
  #sidebar { width: var(--sidebar-w); background: var(--white); border-right: 1px solid var(--border);
             overflow-y: auto; flex-shrink: 0; padding: 12px 0; }
  .cat-label { font-size: 11px; font-weight: 700; color: var(--gray); text-transform: uppercase;
               padding: 12px 16px 4px; letter-spacing: .8px; }
  .ag-btn { width: 100%; text-align: left; background: none; border: none; cursor: pointer;
            padding: 9px 16px; font-size: 14px; color: var(--dark); border-left: 3px solid transparent;
            transition: background .15s; }
  .ag-btn:hover  { background: var(--gray-lt); }
  .ag-btn.act    { background: var(--purple-lt); border-left-color: var(--purple);
                   color: var(--purple); font-weight: 600; }

  /* main */
  #main { flex: 1; overflow-y: auto; padding: 28px 32px; display: flex;
          flex-direction: column; gap: 20px; }

  /* card del agente */
  #agente-card { background: var(--white); border: 1px solid var(--border);
                 border-radius: 10px; padding: 24px 28px; }
  #agente-nombre { font-size: 18px; font-weight: 700; color: var(--purple); margin-bottom: 4px; }
  #agente-desc   { font-size: 13px; color: var(--gray); margin-bottom: 20px; }
  #agente-cat    { display: inline-block; font-size: 11px; font-weight: 600;
                   background: var(--purple-lt); color: var(--purple);
                   border-radius: 20px; padding: 2px 10px; margin-bottom: 16px; }

  /* parámetros */
  .param-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .param-label { font-size: 13px; color: var(--dark); width: 220px; flex-shrink: 0; }
  .param-label .req { color: var(--red); margin-left: 2px; }
  .param-input { flex: 1; font-size: 13px; padding: 7px 10px; border: 1px solid var(--border);
                 border-radius: 6px; background: var(--bg); color: var(--dark);
                 font-family: inherit; outline: none; }
  .param-input:focus { border-color: var(--purple); }
  .btn-browse { padding: 7px 12px; font-size: 12px; background: var(--gray-lt);
                border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
                color: var(--dark); white-space: nowrap; }
  .btn-browse:hover { background: var(--border); }
  .param-check { width: 17px; height: 17px; accent-color: var(--purple); cursor: pointer; }

  /* botón ejecutar */
  #btn-run { background: var(--green); color: #fff; border: none; border-radius: 8px;
             padding: 11px 28px; font-size: 15px; font-weight: 700; cursor: pointer;
             display: flex; align-items: center; gap: 8px; transition: background .15s; }
  #btn-run:hover    { background: var(--teal); }
  #btn-run:disabled { background: var(--gray); cursor: not-allowed; }
  #run-status { font-size: 13px; color: var(--gray); }

  /* log */
  #log-card { background: #1E1E2E; border-radius: 10px; padding: 16px 18px;
              font-family: 'Consolas', monospace; font-size: 12.5px;
              color: #CDD6F4; min-height: 180px; max-height: 340px;
              overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
  .log-ok   { color: #A6E3A1; }
  .log-err  { color: #F38BA8; }
  .log-info { color: #89B4FA; }
  .log-dim  { color: #6C7086; }
  .log-fin-ok  { color: #A6E3A1; font-weight: bold; }
  .log-fin-err { color: #F38BA8; font-weight: bold; }

  /* resultado */
  #resultado-bar { display: none; background: #EAF3DE; border: 1px solid #A6E3A1;
                   border-radius: 8px; padding: 10px 16px; font-size: 13px;
                   color: var(--teal); display: none; align-items: center; gap: 10px; }
  #resultado-bar.show { display: flex; }
  #btn-abrir { background: var(--green); color: #fff; border: none; border-radius: 6px;
               padding: 5px 14px; font-size: 12px; cursor: pointer; font-weight: 600; }
  #btn-abrir:hover { background: var(--teal); }

  /* home screen */
  #home { display: flex; flex-direction: column; gap: 32px; }
  .home-section-title { font-size: 11px; font-weight: 700; color: var(--gray);
                        text-transform: uppercase; letter-spacing: .8px; margin-bottom: 12px; }
  .home-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
  .home-card { background: var(--white); border: 1px solid var(--border); border-radius: 10px;
               padding: 18px 20px; display: flex; flex-direction: column; gap: 7px;
               transition: border-color .15s, box-shadow .15s; }
  .home-card:hover { border-color: var(--purple); box-shadow: 0 2px 14px rgba(83,74,183,.1); }
  .home-card-cat  { display: inline-block; font-size: 10px; font-weight: 700;
                    background: var(--purple-lt); color: var(--purple);
                    border-radius: 20px; padding: 2px 9px; width: fit-content; }
  .home-card-name { font-size: 15px; font-weight: 700; color: var(--dark); line-height: 1.3; }
  .home-card-desc { font-size: 12px; color: var(--gray); line-height: 1.55; flex: 1; }
  .btn-usar { margin-top: 8px; padding: 7px 18px; background: var(--purple); color: #fff;
              border: none; border-radius: 7px; font-size: 13px; font-weight: 700;
              cursor: pointer; transition: background .15s; font-family: inherit;
              align-self: flex-start; }
  .btn-usar:hover { background: #3f38a0; }

  /* drag & drop zone */
  .dropzone { border: 2px dashed var(--border); border-radius: 8px; padding: 22px 16px;
              text-align: center; cursor: pointer; transition: border-color .2s, background .2s;
              background: var(--bg); color: var(--gray); font-size: 13px; user-select: none; }
  .dropzone:hover, .dropzone.over { border-color: var(--purple); background: var(--purple-lt); color: var(--purple); }
  .dropzone.ready { border-color: var(--green); background: #EAF3DE; color: var(--teal); }
  .dropzone .dz-icon { font-size: 20px; margin-bottom: 6px; display: block; }
  .dropzone .dz-label { font-size: 13px; }
  .dropzone .dz-preview { font-size: 13px; font-weight: 600; }

  /* multi-pdf upload */
  .mfr { background: var(--white); border: 1px solid var(--border);
          border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }
  .mfr-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .mfr-icon { font-size: 16px; flex-shrink: 0; }
  .mfr-name { font-size: 13px; font-weight: 600; flex: 1; color: var(--dark);
              overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mfr-remove { background: none; border: none; color: var(--gray); cursor: pointer;
                font-size: 13px; padding: 2px 8px; border-radius: 4px; flex-shrink: 0; }
  .mfr-remove:hover { background: #fee; color: var(--red); }
  .mfr-fields { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px; }
  .mfr-field { display: flex; flex-direction: column; gap: 3px; }
  .mfr-label { font-size: 10px; font-weight: 700; color: var(--gray);
               text-transform: uppercase; letter-spacing: .5px; }
  .mfr-error { margin-top: 8px; font-size: 12px; color: var(--red);
               background: #fee8e8; border-radius: 4px; padding: 4px 8px; }

  /* archivo_multiple */
  .amf-item { display:flex; align-items:center; gap:8px; padding:6px 10px;
              background:var(--bg); border:1px solid var(--border);
              border-radius:6px; font-size:12px; color:var(--dark); }
  .amf-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:500; }
  .amf-err  { font-size:11px; color:var(--red); flex-shrink:0; max-width:180px;
              overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .amf-del  { background:none; border:none; color:var(--gray); cursor:pointer;
              font-size:12px; padding:0 4px; flex-shrink:0; line-height:1; }
  .amf-del:hover { color:var(--red); }
</style>
</head>
<body>

<div id="topbar">
  <span class="logo">AGENTES</span>
  <span class="sub">Galli CBC — Sistema multi-agente</span>
</div>

<div id="layout">
  <div id="sidebar" id="sidebar"></div>

  <div id="main">
    <div id="home"></div>
    <div id="agente-card" style="display:none">
      <div id="agente-cat"></div>
      <div id="agente-nombre"></div>
      <div id="agente-desc"></div>
      <div id="params-container"></div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:8px">
        <button id="btn-run" onclick="ejecutar()">▶&nbsp; Ejecutar</button>
        <span id="run-status"></span>
      </div>
    </div>
    <div id="resultado-bar">
      <span>✓ Completado:</span>
      <span id="resultado-path" style="flex:1;word-break:break-all"></span>
      <button id="btn-abrir" onclick="abrirResultado()">Abrir</button>
    </div>
    <div id="log-card" style="display:none"></div>
  </div>
</div>

<script>
let AGENTES = {};
let agenteActual = null;
let resultadoActual = '';

// ── cargar agentes ────────────────────────────────────────────────────────────
async function init() {
  const r = await fetch('/api/agentes');
  const d = await r.json();
  AGENTES = d.agentes;
  renderSidebar(d.agentes, d.categorias);
  renderHome(d.agentes, d.categorias);
}

function renderSidebar(agentes, categorias) {
  const sb = document.getElementById('sidebar');
  sb.innerHTML = '';
  for (const cat of categorias) {
    const entries = Object.entries(agentes).filter(([,v]) => v.categoria === cat);
    if (!entries.length) continue;
    const lbl = document.createElement('div');
    lbl.className = 'cat-label';
    lbl.textContent = cat;
    sb.appendChild(lbl);
    for (const [key, ag] of entries) {
      const btn = document.createElement('button');
      btn.className = 'ag-btn';
      btn.textContent = ag.nombre;
      btn.dataset.key = key;
      btn.onclick = () => seleccionar(key, btn);
      sb.appendChild(btn);
    }
  }
}

function renderHome(agentes, categorias) {
  const home = document.getElementById('home');
  home.innerHTML = '';
  for (const cat of categorias) {
    const entries = Object.entries(agentes).filter(([, v]) => v.categoria === cat);
    if (!entries.length) continue;

    const section = document.createElement('div');

    const title = document.createElement('div');
    title.className = 'home-section-title';
    title.textContent = cat;
    section.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'home-grid';

    for (const [key, ag] of entries) {
      const card = document.createElement('div');
      card.className = 'home-card';
      card.innerHTML = `
        <div class="home-card-cat">${ag.categoria}</div>
        <div class="home-card-name">${ag.nombre}</div>
        <div class="home-card-desc">${ag.descripcion}</div>
        <button class="btn-usar" data-key="${key}">Usar →</button>`;
      card.querySelector('.btn-usar').onclick = () => {
        const sideBtn = document.querySelector(`.ag-btn[data-key="${key}"]`);
        seleccionar(key, sideBtn);
      };
      grid.appendChild(card);
    }

    section.appendChild(grid);
    home.appendChild(section);
  }
}

// ── seleccionar agente ────────────────────────────────────────────────────────
function seleccionar(key, btn) {
  document.querySelectorAll('.ag-btn').forEach(b => b.classList.remove('act'));
  btn.classList.add('act');
  agenteActual = key;
  const ag = AGENTES[key];

  document.getElementById('home').style.display = 'none';
  document.getElementById('agente-card').style.display = 'block';
  document.getElementById('agente-cat').textContent    = ag.categoria;
  document.getElementById('agente-nombre').textContent = ag.nombre;
  document.getElementById('agente-desc').textContent   = ag.descripcion;
  document.getElementById('log-card').style.display    = 'none';
  document.getElementById('log-card').innerHTML        = '';
  document.getElementById('resultado-bar').classList.remove('show');
  document.getElementById('run-status').textContent    = '';

  renderParams(ag.parametros);
}

// ── renderizar parámetros ─────────────────────────────────────────────────────
function renderParams(params) {
  const ag = AGENTES[agenteActual];
  if (ag && ag.ui_mode === 'multi_pdf') { renderMultiPdfUI(); return; }
  const c = document.getElementById('params-container');
  c.innerHTML = '';
  for (const p of params) {
    const row = document.createElement('div');
    row.className = 'param-row';

    const lbl = document.createElement('label');
    lbl.className = 'param-label';
    lbl.innerHTML = p.label + (p.requerido ? '<span class="req">*</span>' : '');
    lbl.htmlFor = 'param_' + p.nombre;
    row.appendChild(lbl);

    if (p.tipo === 'bool') {
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.className = 'param-check';
      chk.id = 'param_' + p.nombre;
      chk.checked = p.default !== false;
      row.appendChild(chk);

    } else if (p.tipo === 'opciones') {
      const sel = document.createElement('select');
      sel.className = 'param-input';
      sel.id = 'param_' + p.nombre;
      for (const op of (p.opciones || [])) {
        const opt = document.createElement('option');
        opt.value = op;
        opt.textContent = op;
        sel.appendChild(opt);
      }
      row.appendChild(sel);

    } else if (p.tipo === 'archivo_upload') {
      const accept = (p.extensiones || []).join(',');
      const wrap = document.createElement('div');
      wrap.style.cssText = 'flex:1;display:flex;flex-direction:column;gap:6px;';

      const fileInp = document.createElement('input');
      fileInp.type = 'file';
      fileInp.accept = accept;
      fileInp.id = 'param_' + p.nombre + '_file';
      fileInp.style.cssText = 'display:none;';

      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.id = 'param_' + p.nombre;

      const zone = document.createElement('div');
      zone.className = 'dropzone';
      zone.innerHTML = '<span class="dz-icon">📄</span><div class="dz-label">Arrastrá el PDF acá o hacé clic para seleccionar</div>';

      async function uploadFile(file) {
        zone.className = 'dropzone';
        zone.innerHTML = '<span class="dz-icon">⏳</span><div class="dz-preview">Subiendo ' + escHtml(file.name) + '…</div>';
        const fd = new FormData();
        fd.append('archivo', file);
        const r = await fetch('/api/upload-temp', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.path) {
          hidden.value = d.path;
          zone.className = 'dropzone ready';
          zone.innerHTML = '<span class="dz-icon">✅</span><div class="dz-preview">' + escHtml(d.nombre) + '</div>';
        } else {
          zone.className = 'dropzone';
          zone.innerHTML = '<span class="dz-icon">❌</span><div class="dz-label">Error al subir — intentá de nuevo</div>';
        }
      }

      zone.onclick    = () => fileInp.click();
      zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('over'); };
      zone.ondragleave = () => zone.classList.remove('over');
      zone.ondrop = (e) => {
        e.preventDefault();
        zone.classList.remove('over');
        const file = e.dataTransfer.files[0];
        if (file) uploadFile(file);
      };
      fileInp.onchange = () => { if (fileInp.files[0]) uploadFile(fileInp.files[0]); };

      wrap.appendChild(fileInp);
      wrap.appendChild(zone);
      wrap.appendChild(hidden);
      row.appendChild(wrap);

    } else if (p.tipo === 'archivo_multiple') {
      const accept2 = (p.extensiones || []).join(',');
      _amfLists[p.nombre] = [];
      const wrap2 = document.createElement('div');
      wrap2.style.cssText = 'flex:1;display:flex;flex-direction:column;gap:8px;';
      const fileInp2 = document.createElement('input');
      fileInp2.type = 'file'; fileInp2.accept = accept2; fileInp2.multiple = true;
      fileInp2.style.cssText = 'display:none;';
      const hidden2 = document.createElement('input');
      hidden2.type = 'hidden'; hidden2.id = 'param_' + p.nombre; hidden2.value = '[]';
      const zone2 = document.createElement('div');
      zone2.className = 'dropzone';
      zone2.innerHTML = '<span class="dz-icon">📂</span><div class="dz-label">Arrastrá los archivos acá o hacé clic para seleccionar (múltiple)</div>';
      const listDiv2 = document.createElement('div');
      listDiv2.id = 'amf_list_' + p.nombre;
      const _pname = p.nombre;
      const _addFiles = (files) => {
        for (const f of files) {
          const idx = _amfLists[_pname].length;
          _amfLists[_pname].push({file:f, nombre:f.name, path:null, status:'pending', error:null});
          _amfRender(_pname);
          _amfUpload(_pname, idx);
        }
      };
      zone2.onclick     = () => fileInp2.click();
      zone2.ondragover  = (e) => { e.preventDefault(); zone2.classList.add('over'); };
      zone2.ondragleave = () => zone2.classList.remove('over');
      zone2.ondrop = (e) => { e.preventDefault(); zone2.classList.remove('over'); _addFiles(Array.from(e.dataTransfer.files)); };
      fileInp2.onchange = () => { _addFiles(Array.from(fileInp2.files)); fileInp2.value = ''; };
      wrap2.appendChild(fileInp2); wrap2.appendChild(zone2);
      wrap2.appendChild(listDiv2); wrap2.appendChild(hidden2);
      row.appendChild(wrap2);

    } else if (p.tipo === 'archivo' || p.tipo === 'archivo_salida') {
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.className = 'param-input';
      inp.id = 'param_' + p.nombre;
      inp.placeholder = p.tipo === 'archivo_salida' ? '(automático)' : 'Ruta del archivo...';
      row.appendChild(inp);

      const btn = document.createElement('button');
      btn.className = 'btn-browse';
      btn.textContent = '…';
      btn.onclick = async () => {
        const r = await fetch('/api/elegir-archivo', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            extensiones: p.extensiones || [],
            es_salida: p.tipo === 'archivo_salida'
          })
        });
        const d = await r.json();
        if (d.path) inp.value = d.path;
      };
      row.appendChild(btn);

    } else {
      const inp = document.createElement('input');
      inp.type = p.tipo === 'entero' ? 'number' : 'text';
      inp.className = 'param-input';
      inp.id = 'param_' + p.nombre;
      if (p.default != null) inp.value = p.default;
      row.appendChild(inp);
    }

    c.appendChild(row);
  }
}

// ── ejecutar ──────────────────────────────────────────────────────────────────
async function ejecutar() {
  if (!agenteActual) return;
  const ag = AGENTES[agenteActual];
  if (ag.ui_mode === 'multi_pdf') { await ejecutarMultiPdf(); return; }

  // recolectar params
  const params = {};
  for (const p of ag.parametros) {
    const el = document.getElementById('param_' + p.nombre);
    if (!el) continue;
    if (p.tipo === 'bool') params[p.nombre] = el.checked;
    else params[p.nombre] = el.value || null;
    // archivo_upload: el hidden input ya tiene la ruta temp, no hace falta nada extra
  }

  // UI
  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  btn.innerHTML = '⏳&nbsp; Ejecutando…';
  document.getElementById('run-status').textContent = '';
  document.getElementById('resultado-bar').classList.remove('show');

  const log = document.getElementById('log-card');
  log.style.display = 'block';
  log.innerHTML = '<span class="log-dim">Iniciando...</span>\n';

  // lanzar
  const r = await fetch('/api/ejecutar', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ agente: agenteActual, params })
  });
  const d = await r.json();
  if (d.error) {
    log.innerHTML += `<span class="log-err">${d.error}</span>\n`;
    btn.disabled = false;
    btn.innerHTML = '▶&nbsp; Ejecutar';
    return;
  }

  // escuchar stream SSE
  const es = new EventSource('/api/stream/' + d.job_id);
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.tipo === 'ping') return;
    if (msg.tipo === 'log') {
      const cls = msg.texto.includes('Error') || msg.texto.includes('error') ? 'log-err' :
                  msg.texto.includes('✓') || msg.texto.includes('Generado') ? 'log-ok' : 'log-info';
      log.innerHTML += `<span class="${cls}">${escHtml(msg.texto)}</span>\n`;
      log.scrollTop = log.scrollHeight;
    }
    if (msg.tipo === 'fin') {
      es.close();
      btn.disabled = false;
      btn.innerHTML = '▶&nbsp; Ejecutar';
      if (msg.status === 'ok') {
        log.innerHTML += `<span class="log-fin-ok">✓ Completado.</span>\n`;
        document.getElementById('run-status').textContent = '✓ Listo';
        if (msg.resultado) {
          resultadoActual = msg.resultado;
          document.getElementById('resultado-path').textContent = msg.resultado;
          document.getElementById('resultado-bar').classList.add('show');
        }
      } else {
        log.innerHTML += `<span class="log-fin-err">✗ Error: ${escHtml(msg.resultado)}</span>\n`;
        document.getElementById('run-status').textContent = '✗ Error';
      }
      log.scrollTop = log.scrollHeight;
    }
  };
}

async function abrirResultado() {
  if (!resultadoActual) return;
  await fetch('/api/abrir-archivo', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ path: resultadoActual })
  });
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── archivo_multiple (tipo de parámetro genérico) ────────────────────────────
const _amfLists = {};
const _amfIcons = { pending:'⏳', uploading:'📤', ok:'✅', error:'❌' };

function _amfRender(paramName) {
  const list   = document.getElementById('amf_list_' + paramName);
  const hidden = document.getElementById('param_' + paramName);
  if (!list) return;
  const files = _amfLists[paramName] || [];
  list.innerHTML = files.map((f, i) => `
    <div class="amf-item">
      <span>${_amfIcons[f.status] || '⏳'}</span>
      <span class="amf-name">${escHtml(f.nombre)}</span>
      ${f.status === 'error' ? `<span class="amf-err">${escHtml(f.error || '')}</span>` : ''}
      <button class="amf-del" onclick="_amfRemove('${paramName}',${i})" title="Quitar">✕</button>
    </div>`).join('');
  if (hidden) {
    const ready = files.filter(f => f.status === 'ok').map(f => ({path: f.path, nombre: f.nombre}));
    hidden.value = JSON.stringify(ready);
  }
}

function _amfRemove(paramName, idx) {
  _amfLists[paramName].splice(idx, 1);
  _amfRender(paramName);
}

async function _amfUpload(paramName, idx) {
  const entry = _amfLists[paramName][idx];
  if (!entry) return;
  entry.status = 'uploading';
  _amfRender(paramName);
  const fd = new FormData();
  fd.append('archivo', entry.file);
  try {
    const r = await fetch('/api/upload-temp', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.path) { entry.path = d.path; entry.status = 'ok'; }
    else { entry.status = 'error'; entry.error = d.error || 'Error desconocido'; }
  } catch (e) { entry.status = 'error'; entry.error = e.message; }
  _amfRender(paramName);
}

// ── multi-pdf upload ──────────────────────────────────────────────────────────
let multiPdfFiles = [];
const _mfrIcons = { pending:'⏳', uploading:'📤', ready:'✅', ok:'✔️', error:'❌' };

function renderMultiPdfUI() {
  multiPdfFiles = [];
  const c = document.getElementById('params-container');
  c.innerHTML = `
    <div>
      <div id="multi-dropzone" class="dropzone" style="margin-bottom:14px;">
        <span class="dz-icon">📎</span>
        <div class="dz-label">Arrastrá los PDFs acá o hacé clic para seleccionar varios</div>
        <input type="file" id="multi-file-inp" accept=".pdf" multiple style="display:none;">
      </div>
      <div id="multi-file-list"></div>
    </div>`;

  const zone = document.getElementById('multi-dropzone');
  const inp  = document.getElementById('multi-file-inp');
  zone.onclick     = () => inp.click();
  zone.ondragover  = (e) => { e.preventDefault(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = (e) => {
    e.preventDefault(); zone.classList.remove('over');
    addMultiFiles(Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf')));
  };
  inp.onchange = () => { addMultiFiles(Array.from(inp.files)); inp.value = ''; };
}

function addMultiFiles(files) {
  for (const f of files) {
    multiPdfFiles.push({
      file: f, tmpPath: null, nombre: f.name,
      titulo: f.name.replace(/\.pdf$/i, '').replace(/[_-]+/g, ' '),
      cuatrimestre: '', solapa: '1er Parcial', status: 'pending', error: null
    });
  }
  renderMultiFileList();
  multiPdfFiles.forEach((e, i) => { if (e.status === 'pending') uploadMultiFile(i); });
}

function renderMultiFileList() {
  const list = document.getElementById('multi-file-list');
  if (!list) return;
  list.innerHTML = multiPdfFiles.map((e, i) => `
    <div class="mfr" id="mfr-${i}">
      <div class="mfr-header">
        <span class="mfr-icon">${_mfrIcons[e.status] || '⏳'}</span>
        <span class="mfr-name">${escHtml(e.nombre)}</span>
        <button class="mfr-remove" onclick="removeMultiFile(${i})" title="Quitar">✕</button>
      </div>
      <div class="mfr-fields">
        <div class="mfr-field">
          <div class="mfr-label">Título *</div>
          <input class="param-input" value="${escHtml(e.titulo)}"
            oninput="multiPdfFiles[${i}].titulo=this.value">
        </div>
        <div class="mfr-field">
          <div class="mfr-label">Cuatrimestre</div>
          <input class="param-input" placeholder="ej: 1C 2025" value="${escHtml(e.cuatrimestre)}"
            oninput="multiPdfFiles[${i}].cuatrimestre=this.value">
        </div>
        <div class="mfr-field">
          <div class="mfr-label">Solapa *</div>
          <select class="param-input" onchange="multiPdfFiles[${i}].solapa=this.value">
            <option value="1er Parcial"${e.solapa==='1er Parcial'?' selected':''}>1er Parcial</option>
            <option value="2do Parcial"${e.solapa==='2do Parcial'?' selected':''}>2do Parcial</option>
            <option value="Finales"${e.solapa==='Finales'?' selected':''}>Finales</option>
          </select>
        </div>
      </div>
      ${e.status==='error'?`<div class="mfr-error">${escHtml(e.error||'Error al subir')}</div>`:''}
    </div>`).join('');
}

function removeMultiFile(i) {
  multiPdfFiles.splice(i, 1);
  renderMultiFileList();
}

async function uploadMultiFile(i) {
  multiPdfFiles[i].status = 'uploading';
  renderMultiFileList();
  const fd = new FormData();
  fd.append('archivo', multiPdfFiles[i].file);
  try {
    const r = await fetch('/api/upload-temp', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.path) {
      multiPdfFiles[i].tmpPath = d.path;
      multiPdfFiles[i].status  = 'ready';
    } else {
      multiPdfFiles[i].status = 'error';
      multiPdfFiles[i].error  = d.error || 'Error desconocido';
    }
  } catch (err) {
    multiPdfFiles[i].status = 'error';
    multiPdfFiles[i].error  = err.message;
  }
  renderMultiFileList();
}

async function ejecutarMultiPdf() {
  const ready = multiPdfFiles.filter(e => e.status === 'ready');
  if (!ready.length) {
    document.getElementById('run-status').textContent = '⚠ No hay archivos listos';
    return;
  }
  const sin_titulo = ready.find(e => !e.titulo.trim());
  if (sin_titulo) {
    document.getElementById('run-status').textContent = '⚠ Completá todos los títulos';
    return;
  }

  const archivos = ready.map(e => ({
    ruta_pdf: e.tmpPath, nombre_original: e.nombre,
    titulo: e.titulo.trim(), cuatrimestre: e.cuatrimestre.trim(), solapa: e.solapa,
  }));

  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  btn.innerHTML = '⏳&nbsp; Ejecutando…';
  document.getElementById('run-status').textContent = '';
  document.getElementById('resultado-bar').classList.remove('show');

  const log = document.getElementById('log-card');
  log.style.display = 'block';
  log.innerHTML = `<span class="log-dim">Procesando ${ready.length} PDF(s)...</span>\n`;

  const r = await fetch('/api/ejecutar-multi-pdf', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ archivos })
  });
  const d = await r.json();
  if (d.error) {
    log.innerHTML += `<span class="log-err">${escHtml(d.error)}</span>\n`;
    btn.disabled = false; btn.innerHTML = '▶&nbsp; Ejecutar';
    return;
  }

  const es = new EventSource('/api/stream/' + d.job_id);
  es.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.tipo === 'ping') return;
    if (msg.tipo === 'log') {
      const cls = msg.texto.includes('Error') || msg.texto.includes('error') ? 'log-err' :
                  msg.texto.includes('✓') || msg.texto.includes('✅') ? 'log-ok' : 'log-info';
      log.innerHTML += `<span class="${cls}">${escHtml(msg.texto)}</span>\n`;
      log.scrollTop = log.scrollHeight;
    }
    if (msg.tipo === 'fin') {
      es.close();
      btn.disabled = false; btn.innerHTML = '▶&nbsp; Ejecutar';
      if (msg.status === 'ok') {
        log.innerHTML += `<span class="log-fin-ok">✓ Completado.</span>\n`;
        document.getElementById('run-status').textContent = '✓ Listo';
        multiPdfFiles.forEach(e => { if (e.status === 'ready') e.status = 'ok'; });
        renderMultiFileList();
      } else {
        log.innerHTML += `<span class="log-fin-err">✗ Error: ${escHtml(msg.resultado)}</span>\n`;
        document.getElementById('run-status').textContent = '✗ Error';
      }
      log.scrollTop = log.scrollHeight;
    }
  };
}

init();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML

@app.route("/batch")
def batch():
    p = Path(__file__).parent / "agentes" / "subir_pdf" / "subir_batch.html"
    return p.read_text(encoding="utf-8")


# ── arranque ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", "-p", type=int, default=7070)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://localhost:{args.puerto}"
    print(f"\n  Agentes — Galli CBC")
    print(f"  Servidor: {url}")
    print(f"  Ctrl+C para detener\n")

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=args.puerto, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
