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

  /* empty state */
  #empty { display: flex; flex-direction: column; align-items: center; justify-content: center;
           flex: 1; color: var(--gray); gap: 8px; }
  #empty .ico { font-size: 52px; opacity: .3; }
  #empty p    { font-size: 15px; }
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
    <div id="empty">
      <div class="ico">🤖</div>
      <p>Elegí un agente de la lista</p>
    </div>
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

// ── seleccionar agente ────────────────────────────────────────────────────────
function seleccionar(key, btn) {
  document.querySelectorAll('.ag-btn').forEach(b => b.classList.remove('act'));
  btn.classList.add('act');
  agenteActual = key;
  const ag = AGENTES[key];

  document.getElementById('empty').style.display = 'none';
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
      fileInp.style.cssText = 'font-size:13px;';

      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.id = 'param_' + p.nombre;

      const status = document.createElement('span');
      status.id = 'param_' + p.nombre + '_status';
      status.style.cssText = 'font-size:11px;color:#888;';

      fileInp.onchange = async () => {
        const file = fileInp.files[0];
        if (!file) return;
        status.textContent = '⏳ Subiendo…';
        const fd = new FormData();
        fd.append('archivo', file);
        const r = await fetch('/api/upload-temp', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.path) {
          hidden.value = d.path;
          status.textContent = '✓ ' + d.nombre;
          status.style.color = '#1D9E75';
        } else {
          status.textContent = '✗ Error al subir';
          status.style.color = '#E24B4A';
        }
      };

      wrap.appendChild(fileInp);
      wrap.appendChild(hidden);
      wrap.appendChild(status);
      row.appendChild(wrap);

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

init();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML


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
