"""
subir_pdf.py — Sube un PDF resuelto a QuímicaCBC.

Copia el PDF a public/docs/, inserta la tarjeta HTML en la sección
correcta de public/index.html y hace git add + commit + push.

Uso interactivo:
    python subir_pdf.py

Uso programático:
    from subir_pdf import run
    run(titulo="1er Parcial Di Risio", cuatrimestre="1C 2025",
        solapa="1er Parcial", ruta_pdf="C:/ruta/archivo.pdf")
"""

import re
import shutil
import subprocess
from pathlib import Path

# ── Rutas fijas del proyecto ──────────────────────────────────────────────────
REPO_ROOT  = Path(r"C:\Users\carlo\OneDrive\Desktop\quimicacbc")
DOCS_DIR   = REPO_ROOT / "public" / "docs"
INDEX_HTML = REPO_ROOT / "public" / "index.html"

SOLAPAS = ["1er Parcial", "2do Parcial", "Finales"]
TAB_IDS = {
    "1er Parcial": "primer",
    "2do Parcial": "segundo",
    "Finales":     "finales",
}
PLACEHOLDER = {
    "2do Parcial": "Próximamente se agregarán parciales resueltos de 2do Parcial.",
    "Finales":     "Próximamente se agregarán finales resueltos.",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nombre_salida(ruta_pdf: str) -> str:
    """Deriva el nombre de salida preservando el nombre original del archivo.

    Ejemplos:
        2024_Final_B.pdf        → 2024_Final_B_resuelto.pdf
        parcial_1C_2025.pdf     → parcial_1C_2025_resuelto.pdf
        algo_resuelto.pdf       → algo_resuelto.pdf  (ya tiene el sufijo)
    """
    stem = Path(ruta_pdf).stem
    if stem.endswith("_resuelto"):
        return stem + ".pdf"
    return stem + "_resuelto.pdf"


def _pdf_id(filename: str) -> str:
    """ID corto para el viewer JS (sin sufijo _resuelto.pdf)."""
    base = filename.replace("_resuelto.pdf", "")
    return re.sub(r"-+", "-", base).strip("-")


def _escape_js(s: str) -> str:
    """Escapa comillas simples para usar en atributo onclick."""
    return s.replace("'", "\\'")


def _card_html(tab_id: str, titulo_completo: str, pdf_filename: str) -> str:
    pdf_id  = _pdf_id(pdf_filename)
    pdf_url = f"/docs/{pdf_filename}"
    titulo_js = _escape_js(titulo_completo)
    return (
        f'        <div class="pr-card">\n'
        f'          <div class="pr-card-title">{titulo_completo}</div>\n'
        f'          <div class="pr-card-sub">Resuelto con soluciones detalladas</div>\n'
        f'          <div class="pr-card-btns">\n'
        f"            <button class=\"btn btn-p btn-sm\" onclick=\"toggleParcViewer('{tab_id}','{pdf_id}','{titulo_js}','{pdf_url}',this)\">👁 Ver PDF</button>\n"
        f'            <a href="{pdf_url}" target="_blank" class="btn btn-g btn-sm" style="text-decoration:none;">📄 Descargar</a>\n'
        f'          </div>\n'
        f'        </div>'
    )


def _viewer_html(tab_id: str) -> str:
    return (
        f'      <div class="pr-viewer" id="pr-viewer-{tab_id}">\n'
        f'        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">\n'
        f'          <span style="font-size:13px;font-weight:700;color:var(--text);" id="pr-viewer-{tab_id}-title"></span>\n'
        f"          <button class=\"btn btn-g btn-sm\" onclick=\"closeParcViewer('{tab_id}')\">✕ Cerrar</button>\n"
        f'        </div>\n'
        f'        <iframe id="pr-viewer-{tab_id}-iframe" src="" width="100%" height="850px"\n'
        f'          style="border:1px solid var(--border);border-radius:8px;background:var(--bg2);"></iframe>\n'
        f'      </div>'
    )


# ── Lógica de inserción en index.html ─────────────────────────────────────────

def _div_close_pos(html: str, open_pos: int) -> int:
    """Dado el inicio de un '<div', devuelve la posición del '</div>' que lo cierra."""
    depth = 1
    i = open_pos + 4          # saltar '<div'
    while i < len(html) and depth > 0:
        if html[i:i+4] == '<div':
            depth += 1
            i += 4
        elif html[i:i+6] == '</div>':
            depth -= 1
            if depth == 0:
                return i
            i += 6
        else:
            i += 1
    return -1


def _insertar_en_grid(html: str, tab_id: str, card: str) -> str:
    """Inserta una tarjeta al final del pr-card-grid de la sección indicada."""
    # Caso normal: grid seguido de viewer (estructura habitual)
    pattern = re.compile(
        r'(id="prcontent-' + tab_id + r'".*?<div class="pr-card-grid">.*?)'
        r'(\s*</div>\s*\n\s*<div class="pr-viewer")',
        re.DOTALL,
    )
    def replacer(m):
        return m.group(1) + "\n" + card + "\n      " + m.group(2).lstrip()
    new_html, n = pattern.subn(replacer, html)
    if n > 0:
        return new_html

    # Fallback: sin viewer — usar conteo de profundidad para hallar el cierre del grid
    sec_pos  = html.find(f'id="prcontent-{tab_id}"')
    grid_tag = '<div class="pr-card-grid">'
    grid_pos = html.find(grid_tag, sec_pos)
    if grid_pos == -1:
        raise ValueError(f"No se encontró pr-card-grid en prcontent-{tab_id}")

    close = _div_close_pos(html, grid_pos)
    if close == -1:
        raise ValueError(f"HTML mal formado: sin cierre de pr-card-grid en prcontent-{tab_id}")

    return html[:close] + "\n" + card + "\n      " + html[close:]


def _reemplazar_placeholder(html: str, tab_id: str, solapa: str, card: str) -> str:
    """Reemplaza el div placeholder con card-grid + viewer.
    Lanza ValueError si el texto del placeholder no coincide."""
    placeholder_text = re.escape(PLACEHOLDER[solapa])
    pattern = re.compile(
        r'(<div id="prcontent-' + tab_id + r'"[^>]*>)\s*'
        r'<div[^>]*>' + placeholder_text + r'</div>\s*'
        r'(</div>)',
        re.DOTALL,
    )
    viewer = _viewer_html(tab_id)
    replacement = (
        r'\1\n'
        '      <div class="pr-card-grid">\n'
        + card + '\n'
        '      </div>\n'
        + viewer + '\n'
        r'    \2'
    )
    new_html, n = pattern.subn(replacement, html)
    if n == 0:
        raise ValueError(f"Placeholder de '{solapa}' no encontrado en index.html")
    return new_html


def _crear_grid_en_seccion(html: str, tab_id: str, card: str) -> str:
    """Reemplaza todo el contenido interno de prcontent-{tab_id} con un grid + viewer nuevos.
    Usa conteo de profundidad para hallar el cierre exacto de la sección."""
    viewer = _viewer_html(tab_id)
    new_content = (
        '\n      <div class="pr-card-grid">\n'
        + card + '\n'
        + '      </div>\n'
        + viewer + '\n'
        + '    '
    )

    marker = f'<div id="prcontent-{tab_id}"'
    start  = html.find(marker)
    if start == -1:
        raise ValueError(f"No se encontró la sección prcontent-{tab_id} en index.html")

    tag_end = html.index('>', start) + 1   # posición justo después del '>'

    close = _div_close_pos(html, start)
    if close == -1:
        raise ValueError(f"HTML mal formado: sin cierre de prcontent-{tab_id}")

    return html[:tag_end] + new_content + html[close:]


def actualizar_index_html(titulo_completo: str, solapa: str, pdf_filename: str,
                          verbose: bool = True) -> None:
    tab_id = TAB_IDS[solapa]
    html   = INDEX_HTML.read_text(encoding="utf-8")
    card   = _card_html(tab_id, titulo_completo, pdf_filename)

    content_marker = f'id="prcontent-{tab_id}"'
    pos = html.find(content_marker)
    if pos == -1:
        raise ValueError(f"No se encontró '{content_marker}' en index.html")

    next_tab = html.find('id="prcontent-', pos + len(content_marker))
    section  = html[pos: next_tab if next_tab != -1 else pos + 8000]

    if '<div class="pr-card-grid">' in section:
        # El grid ya existe: agregar tarjeta al final
        html = _insertar_en_grid(html, tab_id, card)
        if verbose:
            print(f"  ✓ Tarjeta insertada en grid existente de '{solapa}'")
    else:
        # Sin grid: intentar reemplazar placeholder conocido
        placeholder_ok = False
        if solapa in PLACEHOLDER:
            try:
                html = _reemplazar_placeholder(html, tab_id, solapa, card)
                placeholder_ok = True
                if verbose:
                    print(f"  ✓ Placeholder reemplazado con grid y tarjeta en '{solapa}'")
            except ValueError:
                pass  # texto del placeholder cambió → crear grid desde cero

        if not placeholder_ok:
            # Crear grid completo reemplazando el contenido actual de la sección
            html = _crear_grid_en_seccion(html, tab_id, card)
            if verbose:
                print(f"  ✓ Grid creado desde cero en sección '{solapa}'")

    INDEX_HTML.write_text(html, encoding="utf-8")


# ── Función principal ─────────────────────────────────────────────────────────

def run(
    titulo:       str,
    cuatrimestre: str,
    solapa:       str,
    ruta_pdf:     str,
    verbose:      bool = True,
) -> str:
    ruta = Path(ruta_pdf.strip('"'))
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_pdf}")
    if ruta.suffix.lower() != ".pdf":
        raise ValueError("El archivo debe ser un PDF (.pdf)")
    if solapa not in SOLAPAS:
        raise ValueError(f"Solapa inválida '{solapa}'. Opciones: {SOLAPAS}")

    titulo_completo = f"{titulo} — {cuatrimestre}" if cuatrimestre.strip() else titulo
    pdf_filename    = _nombre_salida(ruta_pdf)
    dest            = DOCS_DIR / pdf_filename

    if verbose:
        print(f"\n  PDF origen:  {ruta}")
        print(f"  Destino:     {dest}")
        print(f"  Solapa:      {solapa}")
        print(f"  Título:      {titulo_completo}")

    # 1. Copiar PDF
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ruta, dest)
    if verbose:
        print("  ✓ PDF copiado")

    # 2. Actualizar index.html
    actualizar_index_html(titulo_completo, solapa, pdf_filename, verbose)

    # 3. git add + commit + push
    rel_pdf   = f"public/docs/{pdf_filename}"
    rel_index = "public/index.html"
    git = lambda *args: ["git", "-C", str(REPO_ROOT), *args]

    cmds = [
        (git("add", rel_pdf, rel_index),   "add"),
        (git("commit", "-m", f"feat: agregar PDF resuelto — {titulo_completo[:70]}"),
         "commit"),
        (git("push", "origin", "main"),    "push"),
    ]
    for cmd, label in cmds:
        if verbose:
            print(f"  $ git {label}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Error en 'git {label}':\n{result.stderr.strip()}"
            )
        if verbose and result.stdout.strip():
            print(f"    {result.stdout.strip()}")

    msg = f"✅ Publicado: {titulo_completo} → {pdf_filename}"
    if verbose:
        print(f"\n  {msg}")
    return msg


# ── Batch: múltiples PDFs con único commit ────────────────────────────────────

def run_batch(archivos: list, verbose: bool = True) -> str:
    """
    Procesa múltiples PDFs y hace un único git commit + push.

    Cada dict en `archivos` debe tener:
        ruta_pdf         (str): ruta al archivo PDF (puede ser temp)
        nombre_original  (str, opcional): nombre original del archivo
        titulo           (str): título del examen
        cuatrimestre     (str): cuatrimestre/año (puede ser vacío)
        solapa           (str): "1er Parcial" | "2do Parcial" | "Finales"
    """
    if not archivos:
        raise ValueError("La lista de archivos está vacía")

    processed    = []
    files_to_add = []

    for i, item in enumerate(archivos, 1):
        titulo       = item["titulo"]
        cuatrimestre = item.get("cuatrimestre", "")
        solapa       = item["solapa"]
        ruta_pdf     = item["ruta_pdf"]
        nombre_orig  = item.get("nombre_original") or Path(ruta_pdf).name

        ruta = Path(ruta_pdf.strip('"'))
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_pdf}")
        if ruta.suffix.lower() != ".pdf":
            raise ValueError(f"El archivo debe ser un PDF: {ruta_pdf}")
        if solapa not in SOLAPAS:
            raise ValueError(f"Solapa inválida '{solapa}'")

        titulo_completo = f"{titulo} — {cuatrimestre}" if cuatrimestre.strip() else titulo
        pdf_filename    = _nombre_salida(nombre_orig)
        dest            = DOCS_DIR / pdf_filename

        if verbose:
            print(f"\n  [{i}/{len(archivos)}] {titulo_completo}")
            print(f"  PDF origen:  {ruta}")
            print(f"  Destino:     {dest}")
            print(f"  Solapa:      {solapa}")

        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, dest)
        if verbose:
            print("  ✓ PDF copiado")

        actualizar_index_html(titulo_completo, solapa, pdf_filename, verbose)

        files_to_add.append(f"public/docs/{pdf_filename}")
        processed.append(titulo_completo)

    files_to_add.append("public/index.html")
    git = lambda *args: ["git", "-C", str(REPO_ROOT), *args]

    if len(processed) == 1:
        commit_msg = f"feat: agregar PDF resuelto — {processed[0][:70]}"
    else:
        commit_msg = f"feat: agregar {len(archivos)} PDFs resueltos"

    cmds = [
        (git("add", *files_to_add),       "add"),
        (git("commit", "-m", commit_msg), "commit"),
        (git("push", "origin", "main"),   "push"),
    ]
    for cmd, label in cmds:
        if verbose:
            print(f"  $ git {label}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error en 'git {label}':\n{result.stderr.strip()}")
        if verbose and result.stdout.strip():
            print(f"    {result.stdout.strip()}")

    msg = f"✅ Publicados {len(archivos)} PDF(s): {', '.join(processed)}"
    if verbose:
        print(f"\n  {msg}")
    return msg


# ── Modo interactivo ──────────────────────────────────────────────────────────

def _pedir(prompt: str, opciones: list = None) -> str:
    while True:
        val = input(f"  {prompt}: ").strip()
        if not val:
            print("    Campo requerido.")
            continue
        if opciones and val not in opciones:
            print(f"    Opciones válidas: {opciones}")
            continue
        return val


def main():
    print()
    print("  ══════════════════════════════════════")
    print("    Subir PDF resuelto — QuímicaCBC")
    print("  ══════════════════════════════════════")

    titulo       = _pedir("Título del examen  (ej: 1er Parcial Di Risio)")
    cuatrimestre = _pedir("Cuatrimestre / año (ej: 1C 2025)")

    print()
    print("  ¿A qué solapa va?")
    for i, s in enumerate(SOLAPAS, 1):
        print(f"    {i}. {s}")
    choice = _pedir("Elegí (1/2/3)", opciones=["1", "2", "3"])
    solapa = SOLAPAS[int(choice) - 1]

    ruta_pdf = _pedir("\n  Ruta del archivo PDF")

    print()
    run(titulo=titulo, cuatrimestre=cuatrimestre, solapa=solapa, ruta_pdf=ruta_pdf)


if __name__ == "__main__":
    main()
