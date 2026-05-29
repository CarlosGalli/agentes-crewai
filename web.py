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
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, Response
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

  /* panel parcial */
  #panel-parcial { display:none; flex-direction:column; gap:16px; }
  .apikey-row-local { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
  .apikey-row-local label { font-size:13px; color:var(--gray); white-space:nowrap; }
  .apikey-row-local input { flex:1; padding:7px 10px; border:1px solid var(--border); border-radius:6px;
                             background:var(--bg); font-size:13px; font-family:monospace; }
  .ej-card-local { background:var(--white); border:1px solid var(--border); border-radius:8px; overflow:hidden; }
  .ej-header-local { display:flex; align-items:center; gap:10px; padding:9px 14px;
                      background:var(--gray-lt); cursor:pointer; border-bottom:1px solid var(--border); }
  .ej-num-local { font-size:11px; font-weight:700; color:var(--purple); background:var(--purple-lt);
                  border-radius:20px; padding:2px 9px; }
  .ej-title-local { font-size:14px; font-weight:600; flex:1; }
  .ej-body-local { padding:14px; font-size:12.5px; font-family:'Consolas',monospace; white-space:pre-wrap;
                   display:none; max-height:350px; overflow-y:auto; line-height:1.6; }
  .ej-body-local.open { display:block; }
  .streaming-cur::after { content:'▋'; animation:blink .7s infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
  .btn-run-parcial { background:var(--green); color:#fff; border:none; border-radius:8px;
                     padding:10px 24px; font-size:14px; font-weight:700; cursor:pointer; }
  .btn-run-parcial:hover { background:var(--teal); }
  .btn-run-parcial:disabled { background:var(--gray); cursor:not-allowed; }
  .copy-small { padding:3px 9px; border:1px solid var(--border); border-radius:5px; background:none;
                font-size:11px; cursor:pointer; color:var(--gray); }
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

    <!-- Panel Parcial CBC y Video DERBUK (llaman al proxy local) -->
    <div id="panel-parcial">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div class="apikey-row-local" style="flex:1;min-width:260px">
          <label for="parcial-apikey">🔑 API Key Anthropic</label>
          <input type="password" id="parcial-apikey" placeholder="sk-ant-..."
                 oninput="localStorage.setItem('apsa_apikey',this.value)" />
        </div>
        <button class="btn-run-parcial" id="btn-parcial" onclick="resolverParcial()">
          ▶ Resolver ejercicios
        </button>
        <span id="parcial-status" style="font-size:13px;color:var(--gray)"></span>
      </div>
      <div id="parcial-list" style="display:flex;flex-direction:column;gap:10px"></div>
    </div>
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

  // Agentes del registry
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

  // Sección YouTube (agentes con proxy)
  const lblYT = document.createElement('div');
  lblYT.className = 'cat-label';
  lblYT.textContent = 'YouTube';
  sb.appendChild(lblYT);

  const btnDerbuk = document.createElement('button');
  btnDerbuk.className = 'ag-btn';
  btnDerbuk.id = 'btn-derbuk';
  btnDerbuk.textContent = 'Video DERBUK';
  btnDerbuk.onclick = () => mostrarParcial('derbuk', btnDerbuk);
  sb.appendChild(btnDerbuk);

  // Sección Parciales
  const lblP = document.createElement('div');
  lblP.className = 'cat-label';
  lblP.textContent = 'Parciales';
  sb.appendChild(lblP);

  const btnP = document.createElement('button');
  btnP.className = 'ag-btn';
  btnP.id = 'btn-parcial-sidebar';
  btnP.textContent = '1er Parcial 2024';
  btnP.onclick = () => mostrarParcial('parcial2024', btnP);
  sb.appendChild(btnP);
}

// ── seleccionar agente ────────────────────────────────────────────────────────
function seleccionar(key, btn) {
  document.querySelectorAll('.ag-btn').forEach(b => b.classList.remove('act'));
  btn.classList.add('act');
  agenteActual = key;
  const ag = AGENTES[key];

  document.getElementById('empty').style.display = 'none';
  document.getElementById('panel-parcial').style.display = 'none';
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

// ── panel parcial / video derbuk (proxy local) ────────────────────────────────

const EJERCICIOS_2024 = [
  { n:1, titulo:"Isoelectrónicos — neutrones de ²⁵R²⁺", enunciado:`Las especies ²⁵R²⁺ y ₁₀X son isoelectrónicas. Indicar el número de neutrones que tiene el ion ²⁵R²⁺.` },
  { n:2, titulo:"Ion isoelectrónico con 4° gas noble", enunciado:`Cuando un átomo del elemento X pierde 1 electrón, forma un ion isoelectrónico con el cuarto gas noble. ¿Cuál afirmación es la única correcta? (A) X pertenece al grupo 1; (B) La carga del ion es −1; (C) El número másico del isótopo de X que tiene 45 neutrones es 80; (D) La CE de X es [Kr](5s)².` },
  { n:3, titulo:"Fórmula de oxosal con Cl en oxidación +1", enunciado:`Escribir la fórmula de una oxosal que contenga cloro en estado de oxidación +1.` },
  { n:4, titulo:"Lewis del HClO — simples, dobles y triples", enunciado:`Indicar para el HClO cuántos enlaces covalentes simples, cuántos dobles y cuántos triples presenta en su estructura de Lewis.` },
  { n:5, titulo:"Mayores ángulos de enlace (VSEPR) — CS₂", enunciado:`¿Cuál de estas moléculas presenta mayores ángulos de enlace según VSEPR?: (a) CCl₂ con 2 pares libres, (b) NH₂ con 1 par libre, (c) H₂O, (d) CS₂. Justificar.` },
  { n:6, titulo:"Propiedades intermoleculares del SCl₂", enunciado:`¿Cuál/es de las siguientes propiedades corresponde/n al SCl₂?: (A) fuerzas de London, (B) enlaces de hidrógeno, (C) fuerzas dipolo permanente-dipolo permanente, (D) conduce la corriente en estado sólido.` },
  { n:7, titulo:"Moles de átomos de O en cafeína — 200 mg", enunciado:`La cafeína es C₈H₁₀N₄O₂ (MM=194 g/mol). Una taza de café tiene 200 mg de cafeína. Calcular los moles de átomos de O ingeridos en una taza. Nₐ=6,02×10²³ mol⁻¹.` },
  { n:8, titulo:"HF vs HI — afirmaciones correctas", enunciado:`El fluoruro de hidrógeno (HF) y el yoduro de hidrógeno (HI) tienen: a) igual número de moléculas en un mol de sustancia; b) igual % en masa de H; c) distinto número de átomos en un mol; d) igual masa molar. ¿Cuál es correcta?` },
  { n:9, titulo:"Afirmación incorrecta sobre materia", enunciado:`Seleccionar la afirmación incorrecta: a) La fórmula molecular y empírica de una sustancia pueden ser la misma. b) "Átomo" y "elemento" significan lo mismo. c) Un sistema heterogéneo puede tener un solo componente. d) La densidad y el punto de fusión son propiedades intensivas.` },
  { n:10, titulo:"Mayor solubilidad en agua", enunciado:`¿Cuál presenta mayor solubilidad en agua?: a) 1-propanol (CH₃CH₂CH₂OH), b) 2-hexanona (CH₃CH₂CH₂CH₂COCH₃), c) butanona (CH₃CH₂COCH₃), d) 1-pentanol (CH₃CH₂CH₂CH₂CH₂OH).` },
];

const DERBUK_SISTEMA = `Sos un profesor de química del CBC que genera contenido para el canal DERBUK. Aplicás MODELADO COGNITIVO: el resolutor "piensa en voz alta" en cada pantalla. Formato de respuesta: JSON con estructura {"titulo_video":"...","pantallas":[{"numero":1,"titulo":"...","texto_visual":"...","narracion":"..."}]}. Mínimo 8 pantallas. Español rioplatense. Solo JSON, sin explicación adicional.`;

const PARCIAL_SISTEMA = `Sos un profesor especializado en Química CBC-UBA. Resolvés ejercicios paso a paso con: datos identificados, desarrollo con justificación del "¿por qué?" de cada paso, y respuesta final marcada. Español rioplatense. Sé conciso pero completo.`;

let modoPanel = null;
let parcialTextos = {};
let parcialEstados = {};

function mostrarParcial(modo, btn) {
  document.querySelectorAll('.ag-btn').forEach(b => b.classList.remove('act'));
  btn.classList.add('act');
  modoPanel = modo;
  document.getElementById('empty').style.display = 'none';
  document.getElementById('agente-card').style.display = 'none';
  document.getElementById('log-card').style.display = 'none';
  document.getElementById('resultado-bar').classList.remove('show');

  const panel = document.getElementById('panel-parcial');
  panel.style.display = 'flex';

  const apikey = localStorage.getItem('apsa_apikey') || '';
  document.getElementById('parcial-apikey').value = apikey;

  if (modo === 'parcial2024') {
    document.getElementById('btn-parcial').textContent = '▶ Resolver los 10 ejercicios';
    parcialTextos = {};
    parcialEstados = {};
    EJERCICIOS_2024.forEach(e => { parcialTextos[e.n] = ''; parcialEstados[e.n] = 'pendiente'; });
    renderParcialList(EJERCICIOS_2024);
  } else if (modo === 'derbuk') {
    document.getElementById('btn-parcial').textContent = '▶ Generar pantallas';
    document.getElementById('parcial-list').innerHTML = `
      <div style="background:var(--white);border:1px solid var(--border);border-radius:8px;padding:18px 20px;display:flex;flex-direction:column;gap:10px">
        <label style="font-size:13px;color:var(--gray)">Ejercicio a resolver<span style="color:var(--red)">*</span></label>
        <textarea id="derbuk-enunciado" rows="4" style="padding:8px 10px;border:1px solid var(--border);border-radius:6px;font-size:13px;font-family:inherit;background:var(--bg);resize:vertical" placeholder="Ej: ¿Cuántos gramos de NaCl se necesitan para preparar 500 mL de solución 0,5 M?"></textarea>
        <label style="font-size:13px;color:var(--gray)">Unidad temática (opcional)</label>
        <input id="derbuk-unidad" type="text" style="padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:13px;background:var(--bg)" placeholder="Ej: Unidad 6 — Soluciones" />
        <div id="derbuk-output" style="display:none;background:#1E1E2E;border-radius:8px;padding:14px;font-family:monospace;font-size:12px;color:#CDD6F4;white-space:pre-wrap;max-height:400px;overflow-y:auto"></div>
      </div>`;
  }
}

function renderParcialList(ejercicios) {
  const el = document.getElementById('parcial-list');
  el.innerHTML = ejercicios.map(e => {
    const st = parcialEstados[e.n] || 'pendiente';
    const ico = st === 'pendiente' ? '⬜' : st === 'corriendo' ? '🔄' : st === 'listo' ? '✅' : '❌';
    const bodyClass = 'ej-body-local' + (st === 'listo' || st === 'corriendo' ? ' open' : '') + (st === 'corriendo' ? ' streaming-cur' : '');
    return `
      <div class="ej-card-local" id="ejcard${e.n}">
        <div class="ej-header-local" onclick="toggleEj(${e.n})">
          <span class="ej-num-local">Ej. ${e.n}</span>
          <span class="ej-title-local">${e.titulo}</span>
          <span>${ico}</span>
          ${st === 'listo' ? `<button class="copy-small" onclick="event.stopPropagation();navigator.clipboard.writeText(parcialTextos[${e.n}])">copiar</button>` : ''}
        </div>
        <div class="${bodyClass}" id="ejbody${e.n}">${escHtml(parcialTextos[e.n] || '')}</div>
      </div>`;
  }).join('');
}

function toggleEj(n) {
  document.getElementById('ejbody' + n)?.classList.toggle('open');
}

async function resolverParcial() {
  const key = document.getElementById('parcial-apikey').value.trim();
  if (!key) { alert('Ingresá tu API key.'); return; }
  localStorage.setItem('apsa_apikey', key);

  if (modoPanel === 'derbuk') {
    await resolverDerbuk(key); return;
  }

  // Parcial 2024
  const btn = document.getElementById('btn-parcial');
  btn.disabled = true;
  for (const ej of EJERCICIOS_2024) {
    document.getElementById('parcial-status').textContent = `Resolviendo ejercicio ${ej.n}/10...`;
    parcialEstados[ej.n] = 'corriendo';
    parcialTextos[ej.n] = '';
    renderParcialList(EJERCICIOS_2024);
    try {
      const resp = await fetch('/api/proxy/anthropic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Api-Key': key },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514', max_tokens: 1500, stream: true,
          system: PARCIAL_SISTEMA,
          messages: [{ role: 'user', content: `Resolvé este ejercicio del 1er Parcial de Química CBC 2024 (Cátedra Di Risio):\n\n${ej.enunciado}` }]
        })
      });
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;
          try {
            const ev = JSON.parse(data);
            if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') {
              parcialTextos[ej.n] += ev.delta.text;
              const box = document.getElementById('ejbody' + ej.n);
              if (box) { box.textContent = parcialTextos[ej.n]; box.scrollTop = box.scrollHeight; }
            }
          } catch(e) {}
        }
      }
      parcialEstados[ej.n] = 'listo';
    } catch(err) {
      parcialTextos[ej.n] = 'Error: ' + err.message;
      parcialEstados[ej.n] = 'error';
    }
    renderParcialList(EJERCICIOS_2024);
    const b = document.getElementById('ejbody' + ej.n);
    if (b) { b.classList.remove('streaming-cur'); b.classList.add('open'); b.textContent = parcialTextos[ej.n]; }
  }
  document.getElementById('parcial-status').textContent = '✓ Todos resueltos';
  btn.disabled = false;
}

async function resolverDerbuk(key) {
  const enunciado = document.getElementById('derbuk-enunciado')?.value?.trim();
  const unidad = document.getElementById('derbuk-unidad')?.value?.trim();
  if (!enunciado) { alert('Ingresá el ejercicio.'); return; }
  const btn = document.getElementById('btn-parcial');
  btn.disabled = true;
  document.getElementById('parcial-status').textContent = 'Generando pantallas...';
  const out = document.getElementById('derbuk-output');
  out.style.display = 'block'; out.textContent = '';
  let texto = '';
  try {
    const prompt = `Ejercicio: ${enunciado}` + (unidad ? `\nUnidad: ${unidad}` : '');
    const resp = await fetch('/api/proxy/anthropic', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Api-Key': key },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514', max_tokens: 3000, stream: true,
        system: DERBUK_SISTEMA,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n'); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        try {
          const ev = JSON.parse(data);
          if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') {
            texto += ev.delta.text;
            out.textContent = texto; out.scrollTop = out.scrollHeight;
          }
        } catch(e) {}
      }
    }
    document.getElementById('parcial-status').textContent = '✓ Listo';
  } catch(err) {
    out.textContent = 'Error: ' + err.message;
  }
  btn.disabled = false;
}

init();
</script>
</body>
</html>
"""

@app.route("/api/proxy/anthropic", methods=["POST"])
def api_proxy_anthropic():
    """
    Proxy para llamadas a la API de Anthropic desde el browser.
    Evita el bloqueo CORS que impide llamadas directas desde JavaScript.
    Body JSON: mismo formato que /v1/messages de Anthropic.
    Header requerido: X-Api-Key con la API key del usuario.
    """
    import urllib.request
    import urllib.error

    api_key = request.headers.get("X-Api-Key", "")
    if not api_key:
        return jsonify({"error": "Falta el header X-Api-Key"}), 400

    body = request.get_data()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    stream = "stream" in request.get_json(force=True, silent=True) and \
             request.get_json(force=True, silent=True).get("stream", False)

    try:
        with urllib.request.urlopen(req) as resp:
            if stream:
                def generate():
                    while True:
                        chunk = resp.read(512)
                        if not chunk:
                            break
                        yield chunk
                return Response(
                    generate(),
                    status=resp.status,
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
            else:
                data = resp.read()
                return Response(data, status=resp.status, mimetype="application/json")
    except urllib.error.HTTPError as e:
        return Response(e.read(), status=e.code, mimetype="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
