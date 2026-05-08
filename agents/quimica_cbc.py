"""
Agente especializado en Química nivel CBC-UBA.
Genera ejercicios, problemas y guías de estudio para el Ciclo Básico Común.
"""
from core.framework import Agent, Task, Crew


def crear_agente() -> Agent:
    return Agent(
        role="Profesor de Química CBC-UBA",
        goal=(
            "Generar ejercicios, problemas y materiales de estudio de Química "
            "para estudiantes del Ciclo Básico Común de la UBA, con rigor científico "
            "y lenguaje claro y accesible."
        ),
        backstory=(
            "Sos profesor de Química en el CBC de la UBA con más de 15 años de experiencia. "
            "Conocés en profundidad el programa oficial de Química General del CBC: "
            "estructura atómica, tabla periódica, enlace químico, estequiometría, "
            "soluciones, reacciones ácido-base, termodinámica básica y electroquímica. "
            "Sabés exactamente qué dificultades tienen los ingresantes universitarios "
            "y cómo diseñar ejercicios graduados que construyen el conocimiento paso a paso. "
            "Usás el lenguaje coloquial porteño cuando explicás conceptos, sin perder "
            "el rigor científico. Siempre incluís las respuestas o soluciones detalladas."
        ),
    )


def crew_ejercicios(tema: str, cantidad: int = 5, dificultad: str = "mixta") -> str:
    """
    Genera una serie de ejercicios de Química CBC sobre un tema dado.

    Args:
        tema: Tema de Química CBC (ej: 'estequiometría', 'enlace químico')
        cantidad: Cantidad de ejercicios a generar
        dificultad: 'básica', 'intermedia', 'avanzada' o 'mixta'
    """
    agente = crear_agente()

    tarea_ejercicios = Task(
        description=(
            f"Generá {cantidad} ejercicios de Química CBC-UBA sobre el tema: **{tema}**.\n"
            f"Nivel de dificultad: {dificultad}.\n\n"
            "Para cada ejercicio incluí:\n"
            "- Enunciado claro y completo\n"
            "- Datos necesarios\n"
            "- Resolución paso a paso\n"
            "- Respuesta final con unidades\n"
            "- Conceptos clave involucrados\n\n"
            "Si corresponde, incluí fórmulas estructurales, ecuaciones químicas balanceadas "
            "y diagramas explicativos en texto (usando ASCII o descripción)."
        ),
        expected_output=(
            f"Una guía de {cantidad} ejercicios resueltos de {tema} para CBC-UBA, "
            "con enunciados, resolución detallada y respuestas. "
            "Formato: Markdown estructurado con numeración clara."
        ),
        agent=agente,
    )

    tarea_resumen = Task(
        description=(
            f"Con base en los ejercicios de {tema}, escribí un resumen teórico breve "
            "(máximo 300 palabras) que repase los conceptos fundamentales necesarios "
            "para resolver ese tipo de problemas. "
            "Incluí fórmulas clave y tips para el parcial."
        ),
        expected_output=(
            "Resumen teórico conciso con conceptos clave, fórmulas y consejos prácticos. "
            "Formato: Markdown con secciones claras."
        ),
        agent=agente,
        context_tasks=[tarea_ejercicios],
    )

    crew = Crew(
        agents=[agente],
        tasks=[tarea_ejercicios, tarea_resumen],
    )

    return crew.kickoff()
