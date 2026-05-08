"""
Agente especializado en materiales didácticos para escuelas secundarias.
Genera planes de clase, guías, evaluaciones y recursos pedagógicos.
"""
from core.framework import Agent, Task, Crew


def crear_agente() -> Agent:
    return Agent(
        role="Docente Especialista en Diseño Curricular para Escuela Secundaria",
        goal=(
            "Generar materiales didácticos de alta calidad para docentes y estudiantes "
            "de escuela secundaria, alineados con el diseño curricular jurisdiccional "
            "argentino y las competencias del siglo XXI."
        ),
        backstory=(
            "Sos profesora de nivel secundario con especialización en diseño curricular "
            "y didáctica, con 18 años de experiencia en escuelas públicas y privadas "
            "de Buenos Aires. "
            "Conocés en profundidad el Diseño Curricular de la Provincia de Buenos Aires "
            "y de CABA para todos los años del secundario, las Resoluciones del CFE "
            "sobre la Nueva Secundaria, y los lineamientos curriculares nacionales. "
            "Tus materiales priorizan el aprendizaje significativo, el pensamiento crítico "
            "y la inclusión educativa. Sabés adaptar contenidos para diferentes perfiles "
            "de estudiantes y contextos socioeconómicos. "
            "Usás metodologías activas: ABP (Aprendizaje Basado en Proyectos), aula invertida, "
            "gamificación y aprendizaje cooperativo. "
            "Escribís en un lenguaje claro, motivador y cercano a los adolescentes argentinos."
        ),
    )


def crew_material(
    materia: str,
    anio_secundaria: str,
    tema: str,
    tipo_material: str = "plan de clase",
    duracion: str = "80 minutos",
    contexto: str = "",
) -> str:
    """
    Genera material didáctico para escuela secundaria.

    Args:
        materia: Asignatura (ej: 'Química', 'Matemática', 'Biología')
        anio_secundaria: Año del secundario (ej: '3° año', '5° año')
        tema: Tema a trabajar
        tipo_material: 'plan de clase', 'guía de trabajo', 'evaluación', 'actividad'
        duracion: Duración estimada de la clase o actividad
        contexto: Información adicional sobre el grupo o institución
    """
    agente = crear_agente()

    tarea_material = Task(
        description=(
            f"Creá un **{tipo_material}** completo para la asignatura **{materia}** "
            f"de **{anio_secundaria}** de la escuela secundaria.\n\n"
            f"Tema: {tema}\n"
            f"Duración: {duracion}\n"
            f"{f'Contexto: {contexto}' if contexto else ''}\n\n"
            "El material debe incluir:\n"
            "- Objetivos de aprendizaje (qué van a saber/poder hacer los estudiantes)\n"
            "- Contenidos conceptuales, procedimentales y actitudinales\n"
            "- Recursos necesarios\n"
            "- Desarrollo de la clase/actividad con tiempos estimados\n"
            "- Estrategias didácticas explicitadas\n"
            "- Actividades para los estudiantes (individuales y grupales)\n"
            "- Consignas claras y motivadoras\n"
            "- Criterios e instrumentos de evaluación\n"
            "- Sugerencias de adaptación para estudiantes con dificultades\n\n"
            "El lenguaje debe ser accesible para adolescentes argentinos. "
            "Incluí ejemplos de la vida cotidiana y contextos locales cuando sea posible."
        ),
        expected_output=(
            f"{tipo_material.title()} completo y listo para usar, con todos los componentes "
            "didácticos, formato Markdown claro y profesional."
        ),
        agent=agente,
    )

    tarea_complementaria = Task(
        description=(
            f"Con base en el {tipo_material} de {tema}, generá el siguiente material complementario:\n\n"
            "1. **Para el docente**: 3 preguntas orientadoras para la reflexión post-clase "
            "y posibles errores conceptuales frecuentes de los estudiantes\n\n"
            "2. **Para los estudiantes**: Una ficha resumen (máximo 1 página A4) con los "
            "conceptos clave del tema, que puedan guardar para estudiar\n\n"
            "3. **Extensión/profundización**: Una actividad opcional desafiante para "
            "estudiantes que terminan antes o quieren profundizar\n\n"
            "4. **Recursos digitales sugeridos**: 3-5 recursos (videos de YouTube, "
            "simulaciones, apps) relevantes para este tema, con descripción breve de cada uno"
        ),
        expected_output=(
            "Material complementario con las 4 secciones solicitadas: reflexión docente, "
            "ficha resumen para estudiantes, actividad de extensión y recursos digitales."
        ),
        agent=agente,
        context_tasks=[tarea_material],
    )

    crew = Crew(
        agents=[agente],
        tasks=[tarea_material, tarea_complementaria],
    )

    return crew.kickoff()
