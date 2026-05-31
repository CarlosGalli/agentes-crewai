"""
resolver_parciales.py — Resuelve múltiples parciales en batch.

Para cada archivo (JPG, PNG, PDF):
1. Llama al pipeline completo de parcial_cbc: Extractor → Resolvedor → PDF
2. Guarda el PDF en C:/Users/carlo/agentes-crewai/outputs/ con nombre_resuelto.pdf
3. Muestra progreso ("Resolviendo 1/3: parcial_2024.jpg...")
4. Muestra resumen al terminar: X resueltos, X errores, rutas generadas

Uso programático:
    from agentes.resolver_parciales.resolver_parciales import run
    run(archivos=[{"path": "/tmp/p.jpg", "nombre": "parcial_1C.jpg"}, ...])
"""

import sys
from pathlib import Path

OUTPUTS_DIR = Path(r"C:\Users\carlo\agentes-crewai\outputs")

FORMATOS_SOPORTADOS = {".jpg", ".jpeg", ".png", ".pdf"}


def _normalizar(item) -> tuple[str, str]:
    """Devuelve (ruta_str, stem_original) desde str o dict {path, nombre}."""
    if isinstance(item, dict):
        ruta_str = item.get("path", "").strip('"')
        nombre   = item.get("nombre") or Path(ruta_str).name
    else:
        ruta_str = str(item).strip('"')
        nombre   = Path(ruta_str).name
    return ruta_str, Path(nombre).stem


def run(archivos: list, verbose: bool = True) -> str:
    if not archivos:
        raise ValueError("No se recibieron archivos para resolver")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from agentes.parcial_cbc.parcial_cbc import procesar_parcial
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from agentes.parcial_cbc.parcial_cbc import procesar_parcial

    ok_list  = []
    err_list = []
    total    = len(archivos)

    for i, item in enumerate(archivos, 1):
        ruta_str, stem = _normalizar(item)
        ruta = Path(ruta_str)

        if verbose:
            print(f"\n  Resolviendo {i}/{total}: {ruta.name}...")

        ext = ruta.suffix.lower()

        if not ruta.exists():
            err_list.append((ruta.name, "Archivo no encontrado"))
            if verbose:
                print(f"  ✗ Archivo no encontrado: {ruta_str}")
            continue

        if ext not in FORMATOS_SOPORTADOS:
            err_list.append((ruta.name, f"Formato no soportado: {ext}"))
            if verbose:
                print(f"  ✗ Formato no soportado: {ext}")
            continue

        salida = str(OUTPUTS_DIR / f"{stem}_resuelto.pdf")

        try:
            pdf = procesar_parcial(
                ruta_entrada     = str(ruta),
                salida           = salida,
                imagen_enunciado = True,
                guardar_json     = False,
                verbose          = verbose,
            )
            ok_list.append(pdf)
            if verbose:
                print(f"  ✓ PDF generado: {pdf}")
        except Exception as e:
            err_list.append((ruta.name, str(e)))
            if verbose:
                print(f"  ✗ Error en {ruta.name}: {e}")

    if verbose:
        print(f"\n{'='*55}")
        print(f"  Resumen: {len(ok_list)} resuelto(s), {len(err_list)} error(es)")
        for pdf in ok_list:
            print(f"  ✓ {pdf}")
        for nombre, err in err_list:
            print(f"  ✗ {nombre}: {err}")
        print(f"{'='*55}")

    lineas = [f"✅ {len(ok_list)} resuelto(s), {len(err_list)} error(es)"]
    for pdf in ok_list:
        lineas.append(f"  → {pdf}")
    for nombre, err in err_list:
        lineas.append(f"  ✗ {nombre}: {err}")
    return "\n".join(lineas)
