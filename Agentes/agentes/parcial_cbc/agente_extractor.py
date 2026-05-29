"""
Agente 1 — Extractor
Lee un PDF o imagen de parcial y devuelve JSON estructurado con los ejercicios.
Usa Claude Vision (claude-sonnet-4-5 o superior).
"""

import anthropic
import base64
import json
import sys
from pathlib import Path

# ── helpers ───────────────────────────────────────────────────────────────────

def _encode_image(path: str) -> tuple[str, str]:
    """Devuelve (base64_data, media_type)."""
    p = Path(path)
    ext = p.suffix.lower()
    media_map = {
        '.png':  'image/png',
        '.jpg':  'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif':  'image/gif',
    }
    if ext not in media_map:
        raise ValueError(f"Extensión no soportada para imagen: {ext}")
    data = base64.standard_b64encode(p.read_bytes()).decode()
    return data, media_map[ext]


def _encode_pdf(path: str) -> tuple[str, str]:
    """Devuelve (base64_data, 'application/pdf')."""
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    return data, 'application/pdf'


PROMPT_EXTRACCION = """Analizá el documento adjunto. Es un examen parcial de Matemática CBC (UBA).

Extraé TODOS los ejercicios del parcial. Para cada uno devolvé:
- numero: número del ejercicio (entero)
- enunciado: texto completo del enunciado tal como aparece, con notación matemática clara
- tipo: uno de [interseccion, ceros_positividad, composicion_asintotas, trigonometrica, otro]
- funciones: lista de funciones mencionadas, cada una como {"nombre": "f", "expresion": "x^2 - 4x - 4"}
- dominio_restriccion: si hay restricción de dominio explícita (ej. "[-pi, pi]"), sino null
- pide: lista de lo que pide el ejercicio (ej. ["puntos de interseccion", "grafico"])

Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, sin bloques de código.
Formato exacto:
{
  "materia": "Matematica CBC",
  "parcial": "1er Parcial",
  "cuatrimestre": "1er cuatrimestre 2025",
  "tema": "Tema 1",
  "ejercicios": [ { ...campos arriba... }, ... ]
}
"""

# ── función principal ─────────────────────────────────────────────────────────

def extraer_ejercicios(ruta_archivo: str, verbose: bool = False) -> dict:
    """
    Recibe la ruta a un PDF o imagen del parcial.
    Devuelve el diccionario con todos los ejercicios estructurados.
    """
    client = anthropic.Anthropic()
    path   = Path(ruta_archivo)

    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

    ext = path.suffix.lower()

    # Construir el bloque de contenido según el tipo de archivo
    if ext == '.pdf':
        b64, mtype = _encode_pdf(ruta_archivo)
        source_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": mtype, "data": b64}
        }
    elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        b64, mtype = _encode_image(ruta_archivo)
        source_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": mtype, "data": b64}
        }
    else:
        raise ValueError(f"Formato no soportado: {ext}. Usar PDF o imagen.")

    if verbose:
        print(f"[Extractor] Procesando: {path.name} ({ext})")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                source_block,
                {"type": "text", "text": PROMPT_EXTRACCION}
            ]
        }]
    )

    raw = response.content[0].text.strip()

    # Limpiar posibles bloques de código que el modelo agregue
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"El modelo no devolvió JSON válido: {e}\n---\n{raw}")

    if verbose:
        n = len(data.get("ejercicios", []))
        print(f"[Extractor] {n} ejercicio(s) extraído(s).")
        for ej in data.get("ejercicios", []):
            print(f"  Ej {ej['numero']} ({ej['tipo']}): {ej['enunciado'][:60]}...")

    return data


# ── CLI de prueba ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python agente_extractor.py <ruta_pdf_o_imagen>")
        sys.exit(1)

    resultado = extraer_ejercicios(sys.argv[1], verbose=True)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
