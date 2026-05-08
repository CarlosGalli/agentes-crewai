"""
Agente especializado en Matemática nivel CBC-UBA.
Genera ejercicios resueltos de álgebra, funciones, trigonometría, límites,
derivadas e integrales para el Ciclo Básico Común.
"""
from core.framework import Agent, Task, Crew


def crear_agente() -> Agent:
    return Agent(
        role="Profesor de Matemática CBC-UBA",
        goal=(
            "Generar ejercicios resueltos y materiales de estudio de Matemática "
            "para estudiantes del Ciclo Básico Común de la UBA, con rigor formal "
            "y explicaciones claras paso a paso."
        ),
        backstory=(
            "Sos profesor de Matemática en el CBC de la UBA con más de 15 años de experiencia "
            "dictando Matemática (61) y Análisis Matemático (51/66). "
            "Conocés en profundidad el programa oficial: álgebra (números reales, polinomios, "
            "ecuaciones e inecuaciones, números complejos), funciones (lineales, cuadráticas, "
            "polinómicas, racionales, exponenciales, logarítmicas), trigonometría "
            "(razones trigonométricas, identidades, ecuaciones trigonométricas), "
            "límites (de funciones, indeterminaciones, continuidad), derivadas "
            "(reglas de derivación, regla de la cadena, aplicaciones, estudio de funciones) "
            "e integrales (primitivas, integral definida, métodos de integración, aplicaciones). "
            "Sabés exactamente qué dificultades tienen los ingresantes universitarios y cómo "
            "diseñar ejercicios graduados que construyen el conocimiento paso a paso. "
            "Usás el lenguaje coloquial porteño cuando explicás conceptos, sin perder "
            "el rigor matemático. Siempre mostrás todos los pasos algebraicos y las "
            "justificaciones de cada propiedad o teorema que usás."
        ),
    )


def crew_ejercicios(tema: str, cantidad: int = 5, dificultad: str = "mixta") -> str:
    """
    Genera una serie de ejercicios resueltos de Matemática CBC sobre un tema dado.

    Args:
        tema: Tema de Matemática CBC (ej: 'derivadas', 'límites', 'trigonometría',
              'álgebra', 'funciones', 'integrales')
        cantidad: Cantidad de ejercicios a generar
        dificultad: 'básica', 'intermedia', 'avanzada' o 'mixta'
    """
    agente = crear_agente()

    tarea_ejercicios = Task(
        description=(
            f"Generá {cantidad} ejercicios resueltos de Matemática CBC-UBA sobre el tema: **{tema}**.\n"
            f"Nivel de dificultad: {dificultad}.\n\n"
            "Para cada ejercicio incluí:\n"
            "- Enunciado claro y completo\n"
            "- Datos y dominio de validez si corresponde\n"
            "- Resolución paso a paso mostrando todos los pasos algebraicos\n"
            "- Justificación de las propiedades, reglas o teoremas aplicados\n"
            "- Respuesta final destacada\n"
            "- Conceptos clave involucrados\n\n"
            "Usá notación matemática clara (LaTeX inline cuando ayude: $f(x)$, $\\lim$, $\\int$, etc.). "
            "Si corresponde, incluí gráficos descriptivos en ASCII o descripciones de "
            "comportamiento (asíntotas, máximos, mínimos, puntos de inflexión)."
        ),
        expected_output=(
            f"Una guía de {cantidad} ejercicios resueltos de {tema} para CBC-UBA, "
            "con enunciados, resolución paso a paso, justificaciones y respuestas. "
            "Formato: Markdown estructurado con numeración clara y notación matemática."
        ),
        agent=agente,
    )

    tarea_resumen = Task(
        description=(
            f"Con base en los ejercicios de {tema}, escribí un resumen teórico breve "
            "(máximo 300 palabras) que repase los conceptos fundamentales necesarios "
            "para resolver ese tipo de problemas. "
            "Incluí definiciones clave, fórmulas, reglas de derivación/integración "
            "según corresponda, y tips para el parcial."
        ),
        expected_output=(
            "Resumen teórico conciso con definiciones, fórmulas clave y consejos prácticos. "
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
