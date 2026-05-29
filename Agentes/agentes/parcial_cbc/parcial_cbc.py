"""
parcial_cbc.py — Orquestador principal
Encadena Extractor → Resolvedor → Generador PDF.

Uso:
    python parcial_cbc.py <archivo>              # PDF o imagen
    python parcial_cbc.py <archivo> --imagen-enunciado  # incrusta imagen original
    python parcial_cbc.py <archivo> --salida mi_pdf.pdf
    python parcial_cbc.py <archivo> --guardar-json      # guarda JSONs intermedios

Integración con agentes-crewai:
    from parcial_cbc import procesar_parcial
    pdf_path = procesar_parcial("foto.jpg", salida="resolucion.pdf", imagen_enunciado=True)
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── importar los tres agentes ─────────────────────────────────────────────────
try:
    from agentes.parcial_cbc.agente_extractor import extraer_ejercicios
    from agentes.parcial_cbc.agente_resolvedor import resolver_todos
    from agentes.parcial_cbc.agente_generador_pdf import generar_pdf
except ImportError:
    from agente_extractor import extraer_ejercicios
    from agente_resolvedor import resolver_todos
    from agente_generador_pdf import generar_pdf


def procesar_parcial(
    ruta_entrada:       str,
    salida:             str  = None,
    imagen_enunciado:   bool = True,
    guardar_json:       bool = False,
    verbose:            bool = True,
) -> str:
    """
    Pipeline completo: entrada (PDF o imagen) → PDF de resolución.

    Parámetros:
        ruta_entrada     : path al PDF o imagen del parcial
        salida           : path del PDF de salida (default: mismo directorio, nombre auto)
        imagen_enunciado : si True, incrusta la imagen/primera pág en el PDF
        guardar_json     : si True, guarda los JSONs intermedios (debug)
        verbose          : mostrar progreso

    Retorna:
        path del PDF generado
    """
    entrada = Path(ruta_entrada)
    if not entrada.exists():
        raise FileNotFoundError(f"No existe: {ruta_entrada}")

    # Nombre de salida automático
    if salida is None:
        salida = str(entrada.parent / f"{entrada.stem}_resolucion.pdf")

    t0 = time.time()

    # ── AGENTE 1: Extractor ───────────────────────────────────────────────
    if verbose:
        print(f"\n{'='*55}")
        print(f"  PARCIAL CBC — Pipeline de resolución automática")
        print(f"{'='*55}")
        print(f"\n[1/3] Extrayendo ejercicios de: {entrada.name}")

    datos_extractor = extraer_ejercicios(str(entrada), verbose=verbose)

    if guardar_json:
        j1 = str(entrada.parent / f"{entrada.stem}_01_extraido.json")
        with open(j1, "w", encoding="utf-8") as f:
            json.dump(datos_extractor, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"      JSON guardado: {j1}")

    n_ej = len(datos_extractor.get("ejercicios", []))
    if n_ej == 0:
        raise ValueError("No se encontraron ejercicios en el archivo.")
    if verbose:
        print(f"      {n_ej} ejercicio(s) detectado(s).")

    # ── AGENTE 2: Resolvedor ──────────────────────────────────────────────
    if verbose:
        print(f"\n[2/3] Resolviendo {n_ej} ejercicio(s)...")

    datos_resolvedor = resolver_todos(datos_extractor, verbose=verbose)

    if guardar_json:
        j2 = str(entrada.parent / f"{entrada.stem}_02_resuelto.json")
        with open(j2, "w", encoding="utf-8") as f:
            json.dump(datos_resolvedor, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"      JSON guardado: {j2}")

    # ── AGENTE 3: Generador PDF ───────────────────────────────────────────
    if verbose:
        print(f"\n[3/3] Generando PDF: {Path(salida).name}")

    # Determinar si pasar la imagen del enunciado
    img_path = None
    if imagen_enunciado:
        ext = entrada.suffix.lower()
        if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
            img_path = str(entrada)
        # Si es PDF, no la incrustamos como imagen (ya está en el PDF base)

    generar_pdf(
        datos_resolvedor,
        salida,
        imagen_enunciado=img_path,
        verbose=verbose
    )

    elapsed = time.time() - t0
    if verbose:
        print(f"\n{'='*55}")
        print(f"  PDF generado en {elapsed:.1f}s")
        print(f"  Salida: {salida}")
        print(f"{'='*55}\n")

    return salida


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera PDF de resolución de parcial CBC a partir de PDF o imagen."
    )
    parser.add_argument("entrada",
        help="Ruta al PDF o imagen del parcial")
    parser.add_argument("--salida", "-o",
        help="Ruta del PDF de salida (default: <entrada>_resolucion.pdf)")
    parser.add_argument("--sin-imagen", action="store_true",
        help="No incrustar la imagen del enunciado en el PDF")
    parser.add_argument("--guardar-json", action="store_true",
        help="Guardar JSONs intermedios para debug")
    parser.add_argument("--silencioso", action="store_true",
        help="Sin output en consola")
    args = parser.parse_args()

    try:
        pdf = procesar_parcial(
            ruta_entrada     = args.entrada,
            salida           = args.salida,
            imagen_enunciado = not args.sin_imagen,
            guardar_json     = args.guardar_json,
            verbose          = not args.silencioso,
        )
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
