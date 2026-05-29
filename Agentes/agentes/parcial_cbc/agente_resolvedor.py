"""
Agente 2 — Resolvedor
Recibe el JSON del extractor y resuelve cada ejercicio.
Devuelve JSON con pasos detallados y datos para los gráficos.
"""

import anthropic
import json
import sys

# ── prompt base ───────────────────────────────────────────────────────────────

PROMPT_RESOLUCION = """Sos un profesor de Matemática CBC (UBA) que resuelve ejercicios paso a paso.

Recibís el siguiente ejercicio en JSON:
{ejercicio_json}

Resolvé el ejercicio COMPLETAMENTE. Devolvé ÚNICAMENTE un objeto JSON válido con esta estructura exacta:

{{
  "numero": <int>,
  "titulo": "<título corto del ejercicio>",
  "tipo": "<tipo>",
  "enunciado_limpio": "<enunciado con notación clara>",
  "idea_clave": "<una oración explicando la estrategia>",
  "pasos": [
    {{
      "titulo_paso": "<PASO N — descripción>",
      "filas": [
        {{"label": "<etiqueta corta>", "contenido": "<desarrollo>", "color": "<green|blue|>"}},
        ...
      ]
    }},
    ...
  ],
  "resultado_final": "<resultado resumido en una línea>",
  "grafico": {{
    "tipo": "<funcion|ceros_signo|homografica|trigonometrica|circulo_trig>",
    "funciones": [
      {{"nombre": "<nombre>", "expresion_python": "<expr evaluable con numpy, usar np.>", "color": "<hex>", "label": "<leyenda>"}}
    ],
    "puntos_destacados": [
      {{"x": <float>, "y": <float>, "label": "<texto>", "color": "<hex>"}}
    ],
    "asintotas": [
      {{"tipo": "<v|h>", "valor": <float>, "label": "<texto>", "color": "<hex>"}}
    ],
    "xlim": [<min>, <max>],
    "ylim": [<min>, <max>],
    "titulo_grafico": "<título>",
    "extras": {{}}
  }}
}}

REGLAS IMPORTANTES:
- Usá notación Unicode correcta: √ (U+221A), ∞ (U+221E), ℝ (U+211D), ∈ (U+2208), ∘ (U+2218), ± (U+00B1), Δ (U+0394), π (U+03C0), → (U+2192), ← (U+2190), ✓ (U+2713), ∪ (U+222A), × (U+00D7)
- En expresion_python usar np.sin, np.cos, np.sqrt, np.pi, etc.
- Si el ejercicio no necesita un campo de grafico (ej. asintotas vacías), poné lista vacía [].
- No agregues texto fuera del JSON.
- Para trigonométrica: incluí tanto tipo "funcion" como "circulo_trig" en extras si corresponde.
- Verificá cada resultado numérico antes de incluirlo.
"""

# ── función principal ─────────────────────────────────────────────────────────

def resolver_ejercicio(ejercicio: dict, verbose: bool = False) -> dict:
    """
    Recibe un dict de ejercicio (tal como viene del extractor).
    Devuelve dict con la resolución completa.
    """
    client = anthropic.Anthropic()

    prompt = PROMPT_RESOLUCION.format(
        ejercicio_json=json.dumps(ejercicio, ensure_ascii=False, indent=2)
    )

    if verbose:
        print(f"[Resolvedor] Resolviendo ejercicio {ejercicio.get('numero')} ({ejercicio.get('tipo')})...")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Limpiar bloques de código si el modelo los agrega
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Ejercicio {ejercicio.get('numero')}: JSON inválido: {e}\n---\n{raw[:500]}"
        )

    if verbose:
        n_pasos = len(data.get("pasos", []))
        print(f"[Resolvedor] Ej {data['numero']}: {n_pasos} paso(s). Resultado: {data.get('resultado_final','')[:60]}")

    return data


def resolver_todos(datos_extractor: dict, verbose: bool = False) -> dict:
    """
    Recibe el dict completo del extractor (con metadata + lista ejercicios).
    Devuelve dict con metadata + lista de resoluciones.
    """
    resoluciones = []
    for ej in datos_extractor.get("ejercicios", []):
        resolucion = resolver_ejercicio(ej, verbose=verbose)
        resoluciones.append(resolucion)

    return {
        "materia":       datos_extractor.get("materia", "Matemática CBC"),
        "parcial":       datos_extractor.get("parcial", "1er Parcial"),
        "cuatrimestre":  datos_extractor.get("cuatrimestre", ""),
        "tema":          datos_extractor.get("tema", ""),
        "resoluciones":  resoluciones
    }


# ── CLI de prueba ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python agente_resolvedor.py <datos_extractor.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        datos = json.load(f)

    resultado = resolver_todos(datos, verbose=True)
    out = sys.argv[1].replace(".json", "_resuelto.json")
    with open(out, "w") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Guardado en: {out}")
