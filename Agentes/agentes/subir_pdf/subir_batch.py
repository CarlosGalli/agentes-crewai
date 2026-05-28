"""
subir_batch.py — Sube múltiples PDFs resueltos a QuímicaCBC en una sola operación.

Copia todos los PDFs, actualiza index.html y hace un único git commit + push al final.
Si algún PDF falla, continúa con los demás y reporta los errores al terminar.

Uso interactivo:
    python subir_batch.py

Uso programático:
    from subir_batch import run_batch
    run_batch([
        {"titulo": "1er Parcial Di Risio", "cuatrimestre": "1C 2025",
         "solapa": "1er Parcial", "ruta_pdf": "C:/ruta/parcial.pdf"},
        {"titulo": "Final Di Risio",       "cuatrimestre": "2024 B",
         "solapa": "Finales",    "ruta_pdf": "C:/ruta/final.pdf"},
    ])
"""

import shutil
import subprocess
from pathlib import Path

try:
    from agentes.subir_pdf.subir_pdf import (
        REPO_ROOT, DOCS_DIR, SOLAPAS,
        _nombre_salida, actualizar_index_html,
    )
except ImportError:
    from subir_pdf import (
        REPO_ROOT, DOCS_DIR, SOLAPAS,
        _nombre_salida, actualizar_index_html,
    )


# ── Función principal batch ───────────────────────────────────────────────────

def run_batch(items: list[dict], verbose: bool = True) -> dict:
    """
    Procesa una lista de PDFs y hace un único commit al final.

    Cada item debe tener: titulo, cuatrimestre, solapa, ruta_pdf.
    Devuelve {"ok": [...], "errores": [...]}.
    """
    if not items:
        raise ValueError("La lista de PDFs está vacía.")

    ok      = []
    errores = []
    archivos_git = ["public/index.html"]

    if verbose:
        print(f"\n  Procesando {len(items)} PDF(s)...\n")

    for i, item in enumerate(items, 1):
        titulo       = item["titulo"]
        cuatrimestre = item.get("cuatrimestre", "").strip()
        solapa       = item["solapa"]
        ruta_pdf     = item["ruta_pdf"].strip('"')

        titulo_completo = f"{titulo} — {cuatrimestre}" if cuatrimestre else titulo
        if verbose:
            print(f"  [{i}/{len(items)}] {titulo_completo}")

        try:
            ruta = Path(ruta_pdf)
            if not ruta.exists():
                raise FileNotFoundError(f"Archivo no encontrado: {ruta_pdf}")
            if ruta.suffix.lower() != ".pdf":
                raise ValueError("El archivo debe ser un PDF (.pdf)")
            if solapa not in SOLAPAS:
                raise ValueError(f"Solapa inválida '{solapa}'. Opciones: {SOLAPAS}")

            pdf_filename = _nombre_salida(ruta_pdf)
            dest         = DOCS_DIR / pdf_filename

            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ruta, dest)
            if verbose:
                print(f"    ✓ Copiado → {pdf_filename}")

            actualizar_index_html(titulo_completo, solapa, pdf_filename, verbose=False)
            if verbose:
                print(f"    ✓ Tarjeta agregada en '{solapa}'")

            archivos_git.append(f"public/docs/{pdf_filename}")
            ok.append({"titulo": titulo_completo, "archivo": pdf_filename})

        except Exception as e:
            errores.append({"titulo": titulo_completo, "error": str(e)})
            if verbose:
                print(f"    ✗ Error: {e}")

    if not ok:
        if verbose:
            print("\n  ✗ Ningún PDF pudo procesarse. Se cancela el commit.")
        return {"ok": ok, "errores": errores}

    # ── Único commit para todos los PDFs procesados ───────────────────────────
    titulos_ok = ", ".join(i["titulo"] for i in ok)
    msg_commit = f"feat: agregar {len(ok)} PDF(s) resuelto(s) — {titulos_ok[:100]}"

    git = lambda *args: ["git", "-C", str(REPO_ROOT), *args]
    cmds = [
        (git("add", *archivos_git),            "add"),
        (git("commit", "-m", msg_commit),       "commit"),
        (git("push", "origin", "main"),         "push"),
    ]

    if verbose:
        print(f"\n  Haciendo commit de {len(ok)} archivo(s)...")

    for cmd, label in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error en 'git {label}':\n{result.stderr.strip()}")
        if verbose and result.stdout.strip():
            print(f"    $ git {label}: {result.stdout.strip()}")

    if verbose:
        print(f"\n  ✅ {len(ok)} PDF(s) publicados.")
        for item in ok:
            print(f"    • {item['titulo']} → {item['archivo']}")
        if errores:
            print(f"\n  ✗ {len(errores)} error(es):")
            for e in errores:
                print(f"    • {e['titulo']}: {e['error']}")

    return {"ok": ok, "errores": errores}


# ── Modo interactivo ──────────────────────────────────────────────────────────

def _pedir(prompt: str, opciones: list = None, opcional: bool = False) -> str:
    while True:
        val = input(f"  {prompt}: ").strip()
        if not val and opcional:
            return ""
        if not val:
            print("    Campo requerido.")
            continue
        if opciones and val not in opciones:
            print(f"    Opciones válidas: {opciones}")
            continue
        return val


def _cargar_item(n: int) -> dict | None:
    """Pide datos de un PDF. Devuelve None si el usuario quiere terminar."""
    print(f"\n  ── PDF #{n} ──")
    titulo = input("  Título (Enter para terminar): ").strip()
    if not titulo:
        return None

    cuatrimestre = _pedir("Cuatrimestre / año (ej: 1C 2025)", opcional=True)

    print()
    for i, s in enumerate(SOLAPAS, 1):
        print(f"    {i}. {s}")
    choice = _pedir("Solapa (1/2/3)", opciones=["1", "2", "3"])
    solapa = SOLAPAS[int(choice) - 1]

    ruta_pdf = _pedir("Ruta del PDF")

    return {"titulo": titulo, "cuatrimestre": cuatrimestre,
            "solapa": solapa, "ruta_pdf": ruta_pdf}


def main():
    print()
    print("  ══════════════════════════════════════════")
    print("    Subir PDFs en batch — QuímicaCBC")
    print("  ══════════════════════════════════════════")
    print("  Ingresá los PDFs uno a uno.")
    print("  Dejá el título vacío para terminar y subir.\n")

    items = []
    n = 1
    while True:
        item = _cargar_item(n)
        if item is None:
            break
        items.append(item)
        n += 1

    if not items:
        print("\n  No se ingresó ningún PDF. Saliendo.")
        return

    print(f"\n  Se procesarán {len(items)} PDF(s):")
    for i, item in enumerate(items, 1):
        cuatri = f" — {item['cuatrimestre']}" if item.get("cuatrimestre") else ""
        print(f"    {i}. {item['titulo']}{cuatri}  [{item['solapa']}]")

    confirmar = input("\n  ¿Confirmar y subir? (s/N): ").strip().lower()
    if confirmar not in ("s", "si", "sí", "y", "yes"):
        print("  Cancelado.")
        return

    run_batch(items)


if __name__ == "__main__":
    main()
