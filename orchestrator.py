"""
Orquestador central del sistema multi-agente.
Clasifica la tarea recibida y la deriva al agente especializado correcto.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from core.framework import get_client, MODEL
import agents.quimica_cbc as quimica_cbc
import agents.apsa as apsa
import agents.escuelas as escuelas
import agents.matematica_cbc as matematica_cbc


OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

CLASIFICADOR_SYSTEM = """
Sos un orquestador inteligente de un sistema multi-agente. Tu única función es clasificar
tareas de texto y determinar cuál de los siguientes agentes especializados debe manejarlas:

1. **quimica_cbc**: Para tareas relacionadas con:
   - Química a nivel universitario CBC-UBA
   - Ejercicios, problemas y guías de química universitaria
   - Estequiometría, enlace químico, termodinámica, soluciones, etc.
   - Preparación para parciales de Química del CBC

2. **apsa**: Para tareas relacionadas con:
   - Tratamiento de agua potable e industrial
   - Informes técnicos de calidad del agua
   - Análisis fisicoquímicos y microbiológicos de agua
   - Plantas de tratamiento, desinfección, filtración
   - Normativa de agua potable argentina (ENOHSA, CAA, etc.)
   - APSA (Aguas Provinciales de Santa Fe) u otras empresas de agua

3. **escuelas**: Para tareas relacionadas con:
   - Materiales didácticos para escuela secundaria
   - Planes de clase para nivel medio
   - Evaluaciones y guías para secundaria
   - Diseño curricular para adolescentes
   - Cualquier materia de secundaria (no CBC universitario)

4. **matematica_cbc**: Para tareas relacionadas con:
   - Matemática a nivel universitario CBC-UBA (Matemática 61, Análisis 51/66)
   - Ejercicios resueltos de álgebra, funciones, trigonometría
   - Límites, derivadas e integrales
   - Estudio de funciones, gráficos, asíntotas
   - Preparación para parciales de Matemática del CBC

Respondé ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:
{
  "agente": "quimica_cbc" | "apsa" | "escuelas" | "matematica_cbc",
  "confianza": 0.0-1.0,
  "razon": "explicación breve de por qué elegiste ese agente",
  "parametros_sugeridos": {}
}

El campo "parametros_sugeridos" puede contener parámetros relevantes extraídos de la tarea.
"""


def clasificar_tarea(tarea: str) -> dict:
    """Usa Claude para clasificar la tarea y determinar el agente correcto."""
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=512,
        system=CLASIFICADOR_SYSTEM,
        messages=[
            {"role": "user", "content": f"Clasificá esta tarea:\n\n{tarea}"}
        ],
    )

    raw = response.content[0].text.strip()

    # Limpiar markdown si Claude lo envuelve
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)


def guardar_output(agente: str, tarea: str, resultado: str) -> Path:
    """Guarda el resultado en un archivo .md en el directorio outputs/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUTS_DIR / f"{agente}_{timestamp}.md"

    content = (
        f"# Resultado - {agente.replace('_', ' ').title()}\n"
        f"**Fecha:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"**Tarea original:**\n> {tarea}\n\n"
        f"---\n\n"
        f"{resultado}"
    )

    filename.write_text(content, encoding="utf-8")
    return filename


def procesar(tarea: str, guardar: bool = True) -> str:
    """
    Punto de entrada principal del orquestador.

    Recibe una tarea en lenguaje natural, la clasifica automáticamente
    y la deriva al agente especializado correcto.

    Args:
        tarea: Descripción de la tarea en lenguaje natural
        guardar: Si True, guarda el resultado en outputs/

    Returns:
        El resultado generado por el agente especializado
    """
    print(f"\n{'='*60}")
    print("ORQUESTADOR - Sistema Multi-Agente")
    print(f"{'='*60}")
    print(f"Tarea recibida: {tarea[:100]}{'...' if len(tarea) > 100 else ''}")

    # Paso 1: Clasificar la tarea
    print("\n[Orquestador] Clasificando tarea...")
    clasificacion = clasificar_tarea(tarea)

    agente_id = clasificacion["agente"]
    confianza = clasificacion["confianza"]
    razon = clasificacion["razon"]

    print(f"[Orquestador] Agente seleccionado: {agente_id}")
    print(f"[Orquestador] Confianza: {confianza:.0%}")
    print(f"[Orquestador] Razón: {razon}")

    if confianza < 0.5:
        print(f"[Orquestador] ADVERTENCIA: Confianza baja ({confianza:.0%}). Procediendo de todas formas.")

    # Paso 2: Derivar al agente correcto
    resultado = _despachar(agente_id, tarea, clasificacion.get("parametros_sugeridos", {}))

    # Paso 3: Guardar resultado si se solicitó
    if guardar and resultado:
        output_path = guardar_output(agente_id, tarea, resultado)
        print(f"\n[Orquestador] Resultado guardado en: {output_path}")

    return resultado


def _despachar(agente_id: str, tarea: str, params: dict) -> str:
    """Despacha la tarea al módulo del agente correcto."""
    if agente_id == "quimica_cbc":
        tema = params.get("tema", tarea)
        cantidad = int(params.get("cantidad", 5))
        dificultad = params.get("dificultad", "mixta")
        return quimica_cbc.crew_ejercicios(tema, cantidad, dificultad)

    elif agente_id == "apsa":
        tipo = params.get("tipo_informe", "diagnóstico")
        instalacion = params.get("instalacion", tarea)
        parametros_agua = params.get("parametros_agua")
        return apsa.crew_informe(tipo, instalacion, parametros_agua)

    elif agente_id == "escuelas":
        materia = params.get("materia", "Ciencias Naturales")
        anio = params.get("anio", "3° año")
        tema = params.get("tema", tarea)
        tipo_material = params.get("tipo_material", "plan de clase")
        return escuelas.crew_material(materia, anio, tema, tipo_material)

    elif agente_id == "matematica_cbc":
        tema = params.get("tema", tarea)
        cantidad = int(params.get("cantidad", 5))
        dificultad = params.get("dificultad", "mixta")
        return matematica_cbc.crew_ejercicios(tema, cantidad, dificultad)

    else:
        raise ValueError(f"Agente desconocido: {agente_id}")
