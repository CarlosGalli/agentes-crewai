"""
Generador automático de contenido didáctico para Matemática CBC-UBA.

Ejecuta el agente matematica_cbc sobre las 6 unidades del programa oficial
y guarda los resultados en outputs/ con nombres descriptivos. Sin prompts
interactivos: corré el script y esperá.

Uso:
    python generar_contenido.py            # corrida real (gasta tokens)
    python generar_contenido.py --dry-run  # imprime el plan sin llamar a la API
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Forzar UTF-8 en stdout/stderr para que los emojis del modelo no rompan en cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


UNIDADES = [
    (1, "Números reales y álgebra", "numeros_reales_algebra"),
    (2, "Funciones", "funciones"),
    (3, "Trigonometría", "trigonometria"),
    (4, "Límites y continuidad", "limites_continuidad"),
    (5, "Derivadas", "derivadas"),
    (6, "Integrales", "integrales"),
]

CANTIDAD = 10
DIFICULTAD = "mixta"

OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def verificar_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: la variable ANTHROPIC_API_KEY no está configurada.")
        print('  $env:ANTHROPIC_API_KEY = "tu-api-key-aqui"')
        sys.exit(1)


def guardar_unidad(numero: int, tema: str, slug: str, resultado: str) -> Path:
    """Guarda el resultado con nombre descriptivo: matematica_cbc_unidad_NN_<slug>.md"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUTS_DIR / f"matematica_cbc_unidad_{numero:02d}_{slug}.md"

    cabecera = (
        f"# Matemática CBC-UBA — Unidad {numero}: {tema}\n"
        f"**Generado:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"**Cantidad:** {CANTIDAD} ejercicios · **Dificultad:** {DIFICULTAD}\n"
        f"**Archivo:** `{filename.name}` · **Timestamp:** {timestamp}\n\n"
        f"---\n\n"
    )
    filename.write_text(cabecera + resultado, encoding="utf-8")
    return filename


def imprimir_plan_dry_run() -> None:
    """Imprime qué se procesaría sin llamar a la API ni escribir archivos."""
    print("=" * 70)
    print("  GENERADOR — Matemática CBC-UBA · MODO DRY-RUN (sin llamar a la API)")
    print(f"  Unidades: {len(UNIDADES)} · Ejercicios por unidad: {CANTIDAD} · Dificultad: {DIFICULTAD}")
    print("=" * 70)
    print()
    print(f"Directorio destino: {OUTPUTS_DIR}")
    print()
    print(f"  {'#':<3} {'Unidad':<32} {'Archivo destino'}")
    print(f"  {'-'*3} {'-'*32} {'-'*48}")
    for numero, tema, slug in UNIDADES:
        archivo = f"matematica_cbc_unidad_{numero:02d}_{slug}.md"
        existe = (OUTPUTS_DIR / archivo).exists()
        marca_existe = "  [ya existe, se sobrescribiría]" if existe else ""
        print(f"  {numero:<3} {tema:<32} {archivo}{marca_existe}")

    print()
    print("Estimación (basada en corrida previa):")
    print(f"  - Tiempo total: ~6-7 min ({len(UNIDADES)} unidades × ~60-75s c/u)")
    print(f"  - Tokens output: ~5K por unidad × {len(UNIDADES)} = ~30K (Sonnet 4.6)")
    print()
    print("No se hicieron llamadas a la API ni se modificaron archivos.")
    print("Para ejecutar realmente: python generar_contenido.py")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generador de contenido CBC-UBA para Matemática",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime el plan (qué unidades y qué archivos) sin llamar a la API ni escribir nada.",
    )
    args = parser.parse_args()

    if args.dry_run:
        imprimir_plan_dry_run()
        return

    verificar_api_key()

    from agents import matematica_cbc

    print("=" * 70)
    print("  GENERADOR AUTOMÁTICO — Matemática CBC-UBA")
    print(f"  Unidades: {len(UNIDADES)} · Ejercicios por unidad: {CANTIDAD} · Dificultad: {DIFICULTAD}")
    print("=" * 70)

    inicio_total = time.time()
    resultados: list[tuple[int, str, Path | None, str]] = []

    for numero, tema, slug in UNIDADES:
        print(f"\n[{numero}/{len(UNIDADES)}] Unidad {numero}: {tema}")
        print("-" * 70)
        t0 = time.time()
        try:
            resultado = matematica_cbc.crew_ejercicios(tema, CANTIDAD, DIFICULTAD)
            path = guardar_unidad(numero, tema, slug, resultado)
            elapsed = time.time() - t0
            size_kb = path.stat().st_size / 1024
            print(f"[OK] {tema} → {path.name} ({size_kb:.1f} KB, {elapsed:.0f}s)")
            resultados.append((numero, tema, path, "ok"))
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[ERROR] {tema} falló tras {elapsed:.0f}s: {e}")
            resultados.append((numero, tema, None, f"error: {e}"))

    total = time.time() - inicio_total
    print("\n" + "=" * 70)
    print(f"  RESUMEN — {total:.0f}s totales ({total/60:.1f} min)")
    print("=" * 70)
    for numero, tema, path, estado in resultados:
        marca = "OK " if estado == "ok" else "ERR"
        destino = path.name if path else estado
        print(f"  [{marca}] Unidad {numero}: {tema:<32} → {destino}")

    fallos = sum(1 for _, _, _, estado in resultados if estado != "ok")
    if fallos:
        print(f"\n{fallos} unidad(es) fallaron. Revisá los mensajes de error de arriba.")
        sys.exit(1)
    print(f"\nTodo OK. {len(resultados)} archivos generados en {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
