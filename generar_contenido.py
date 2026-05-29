"""
Generador automático de contenido didáctico para Matemática CBC-UBA.
Llama directamente a la API de Anthropic — sin CrewAI ni frameworks externos.

100 ejercicios por unidad en 10 lotes de 10. 3 segundos de delay entre lotes.

Uso:
    python generar_contenido.py            # genera las 6 unidades completas
    python generar_contenido.py --dry-run  # muestra el plan sin llamar a la API
    python generar_contenido.py --unidad 1 # solo la unidad indicada
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Configuración ──────────────────────────────────────────────────────────────

UNIDADES = [
    (1, "Números reales y álgebra",  "numeros_reales_algebra"),
    (2, "Funciones",                 "funciones"),
    (3, "Trigonometría",             "trigonometria"),
    (4, "Límites y continuidad",     "limites_continuidad"),
    (5, "Derivadas",                 "derivadas"),
    (6, "Integrales",                "integrales"),
]

CANTIDAD_POR_LOTE = 10   # ejercicios por llamada a la API
LOTES            = 10    # lotes por unidad → 100 ejercicios por unidad
DELAY_ENTRE_LOTES = 3    # segundos entre lotes
MODEL            = "claude-sonnet-4-6"
MAX_TOKENS       = 4096

OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# ── Prompt del sistema ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Sos un profesor de Matemática CBC-UBA con más de 15 años de experiencia dictando \
Matemática (61) y Análisis Matemático (51/66). Conocés en profundidad el programa \
oficial: álgebra (números reales, polinomios, ecuaciones, complejos), funciones \
(lineales, cuadráticas, racionales, exponenciales, logarítmicas), trigonometría \
(razones, identidades, ecuaciones), límites (indeterminaciones, continuidad), \
derivadas (reglas, cadena, aplicaciones) e integrales (primitivas, métodos, TFC). \
Sabés exactamente qué dificultades tienen los ingresantes y cómo construir \
ejercicios graduados que consolidan el conocimiento paso a paso.

Generás ejercicios resueltos en formato Markdown con esta estructura EXACTA:

## Ejercicio N — Título descriptivo
**Dificultad:** ⭐ Básica | ⭐⭐ Intermedia | ⭐⭐⭐ Avanzada

### Enunciado
Enunciado completo con la función o expresión concreta a trabajar. \
Usá notación LaTeX inline ($f(x)$, $\\lim$, $\\int$, etc.) y en bloque \
($$expresión$$) donde corresponda.

### Resolución paso a paso

**Paso 1: Identificar la estrategia.**
Propiedad o fórmula aplicada + justificación.

**Paso 2: Desarrollo algebraico.**
Todos los pasos sin saltear nada.

(mínimo 4 pasos, máximo 8)

### Respuesta Final
Resultado completo con notación matemática correcta.

---

REGLAS ABSOLUTAS:
- Cada ejercicio DEBE tener datos concretos (funciones y valores numéricos reales, no genéricos).
- Mostrá TODOS los pasos algebraicos; nunca los saltees.
- Distribuí: básica ≈ 30 %, intermedia ≈ 40 %, avanzada ≈ 30 %.
- Respondé SOLO con los ejercicios en el formato indicado, sin texto introductorio ni conclusión final.\
"""


# ── Funciones ──────────────────────────────────────────────────────────────────

def generar_lote(client: anthropic.Anthropic, tema: str, numero_inicio: int) -> str:
    numero_fin = numero_inicio + CANTIDAD_POR_LOTE - 1
    prompt = (
        f"Generá {CANTIDAD_POR_LOTE} ejercicios resueltos de Matemática CBC-UBA "
        f"sobre el tema: **{tema}**.\n"
        f"Numeralos del {numero_inicio} al {numero_fin}.\n"
        f"Seguí exactamente el formato del sistema."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def guardar_unidad(numero: int, tema: str, slug: str, secciones: list[str]) -> Path:
    filename = OUTPUTS_DIR / f"matematica_cbc_unidad_{numero:02d}_{slug}.md"
    total = CANTIDAD_POR_LOTE * LOTES
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cabecera = (
        f"# Matemática CBC-UBA — Unidad {numero}: {tema}\n"
        f"**Generado:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"**Cantidad:** {total} ejercicios · **Dificultad:** mixta\n"
        f"**Archivo:** `{filename.name}` · **Timestamp:** {timestamp}\n\n"
        f"---\n\n"
    )
    filename.write_text(cabecera + "\n\n".join(secciones), encoding="utf-8")
    return filename


def imprimir_plan(solo_unidad: int | None) -> None:
    unidades = [u for u in UNIDADES if solo_unidad is None or u[0] == solo_unidad]
    total_por_unidad = CANTIDAD_POR_LOTE * LOTES
    total_llamadas = len(unidades) * LOTES
    print("=" * 70)
    print("  GENERADOR — Matemática CBC-UBA · DRY-RUN (sin llamadas a la API)")
    print(f"  {len(unidades)} unidades · {total_por_unidad} ejercicios c/u "
          f"· {LOTES} lotes × {CANTIDAD_POR_LOTE} · {DELAY_ENTRE_LOTES}s delay")
    print("=" * 70)
    for numero, tema, slug in unidades:
        archivo = f"matematica_cbc_unidad_{numero:02d}_{slug}.md"
        existe = "  [ya existe → se sobreescribirá]" if (OUTPUTS_DIR / archivo).exists() else ""
        print(f"  U{numero} {tema:<32} → {archivo}{existe}")
    mins = total_llamadas * 1.5
    print(f"\nTiempo estimado: ~{mins:.0f}–{mins*2:.0f} min · {total_llamadas} llamadas a la API")
    print("Para ejecutar: python generar_contenido.py")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generador Matemática CBC-UBA")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--unidad", type=int, default=None, help="Solo esta unidad (1-6)")
    args = parser.parse_args()

    unidades = [u for u in UNIDADES if args.unidad is None or u[0] == args.unidad]
    if not unidades:
        print(f"[ERROR] Unidad {args.unidad} no encontrada (válidas: 1-6).")
        sys.exit(1)

    if args.dry_run:
        imprimir_plan(args.unidad)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY no configurada.")
        print('  PowerShell: $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    total_por_unidad = CANTIDAD_POR_LOTE * LOTES

    print("=" * 70)
    print("  GENERADOR AUTOMÁTICO — Matemática CBC-UBA (API directa)")
    print(f"  {len(unidades)} unidades · {total_por_unidad} ejercicios c/u · {MODEL}")
    print("=" * 70)

    inicio_total = time.time()
    resultados: list[tuple[int, str, Path | None, str]] = []

    for numero, tema, slug in unidades:
        print(f"\n[U{numero}] {tema}")
        print("-" * 70)
        t0 = time.time()
        secciones: list[str] = []
        errores = 0

        for lote in range(LOTES):
            numero_inicio = lote * CANTIDAD_POR_LOTE + 1
            numero_fin    = numero_inicio + CANTIDAD_POR_LOTE - 1
            print(f"  Lote {lote+1:2}/{LOTES}  (ej. {numero_inicio:3}–{numero_fin:3})...",
                  end=" ", flush=True)

            for intento in range(1, 4):
                try:
                    texto = generar_lote(client, tema, numero_inicio)
                    secciones.append(texto)
                    print("✓")
                    break
                except Exception as e:
                    if intento < 3:
                        print(f"[reintento {intento+1}] ", end="", flush=True)
                        time.sleep(5)
                    else:
                        print(f"✗ {e}")
                        errores += 1

            if lote < LOTES - 1:
                time.sleep(DELAY_ENTRE_LOTES)

        if secciones:
            path = guardar_unidad(numero, tema, slug, secciones)
            elapsed = time.time() - t0
            size_kb = path.stat().st_size / 1024
            print(f"  → {path.name}  ({size_kb:.1f} KB, {elapsed:.0f}s, {errores} errores de lote)")
            resultados.append((numero, tema, path, "ok"))
        else:
            print(f"  [ERROR] Sin resultados para U{numero}")
            resultados.append((numero, tema, None, "sin resultados"))

    total_elapsed = time.time() - inicio_total
    print("\n" + "=" * 70)
    print(f"  RESUMEN — {total_elapsed:.0f}s totales ({total_elapsed/60:.1f} min)")
    print("=" * 70)
    for numero, tema, path, estado in resultados:
        marca = "OK " if estado == "ok" else "ERR"
        destino = path.name if path else estado
        print(f"  [{marca}] U{numero} {tema:<32} → {destino}")

    fallos = sum(1 for *_, estado in resultados if estado != "ok")
    if fallos:
        print(f"\n{fallos} unidad(es) con problemas.")
        sys.exit(1)
    print(f"\nTodo OK. Archivos en {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
