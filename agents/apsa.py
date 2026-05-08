"""
Agente especializado en APSA - Tratamiento de Agua Industrial.
Redacta informes técnicos, protocolos y análisis de calidad de agua.
"""
from core.framework import Agent, Task, Crew


def crear_agente() -> Agent:
    return Agent(
        role="Ingeniero Especialista en Tratamiento de Agua Industrial - APSA",
        goal=(
            "Redactar informes técnicos precisos y completos sobre tratamiento de agua "
            "industrial, análisis fisicoquímicos y microbiológicos, diseño de plantas "
            "de tratamiento y cumplimiento normativo."
        ),
        backstory=(
            "Sos un ingeniero químico especializado en tratamiento de agua potable e "
            "industrial con 20 años de experiencia en APSA (Aguas Provinciales de Santa Fe) "
            "y otras empresas del sector. "
            "Dominás los procesos de coagulación-floculación, sedimentación, filtración, "
            "desinfección con cloro/UV/ozono, osmosis inversa, intercambio iónico y "
            "tratamiento de efluentes industriales. "
            "Conocés en detalle la normativa argentina: Ley 26.221, resoluciones de ENOHSA, "
            "estándares del CAA (Código Alimentario Argentino) para agua potable, y "
            "normativas provinciales de vuelco de efluentes. "
            "Tus informes son claros, técnicamente rigurosos e incluyen parámetros, "
            "unidades de medida correctas, tablas comparativas y recomendaciones operativas."
        ),
    )


def crew_informe(
    tipo_informe: str,
    instalacion: str,
    parametros: dict | None = None,
    contexto_extra: str = "",
) -> str:
    """
    Genera un informe técnico de tratamiento de agua.

    Args:
        tipo_informe: Tipo de informe ('análisis', 'diagnóstico', 'diseño', 'auditoría')
        instalacion: Descripción de la instalación o sistema
        parametros: Dict con parámetros medidos (ej: {'pH': 7.2, 'turbidez': '3 NTU'})
        contexto_extra: Información adicional relevante
    """
    agente = crear_agente()

    params_str = ""
    if parametros:
        params_str = "\n\nParámetros relevados:\n" + "\n".join(
            f"  - {k}: {v}" for k, v in parametros.items()
        )

    tarea_informe = Task(
        description=(
            f"Redactá un informe técnico de **{tipo_informe}** para la siguiente instalación:\n"
            f"{instalacion}{params_str}\n\n"
            f"{contexto_extra}\n\n"
            "El informe debe incluir:\n"
            "1. Encabezado con datos de la instalación, fecha y número de informe\n"
            "2. Resumen ejecutivo (máximo 150 palabras)\n"
            "3. Descripción del sistema evaluado\n"
            "4. Metodología aplicada\n"
            "5. Resultados y análisis (con tablas si corresponde)\n"
            "6. Comparación con normativa vigente argentina\n"
            "7. Diagnóstico y hallazgos principales\n"
            "8. Recomendaciones técnicas concretas y priorizadas\n"
            "9. Conclusiones\n"
            "10. Referencias normativas\n\n"
            "Usá terminología técnica precisa e incluí todas las unidades de medida "
            "correspondientes (mg/L, NTU, UFC/100mL, etc.)."
        ),
        expected_output=(
            f"Informe técnico completo de {tipo_informe} de tratamiento de agua, "
            "con todas las secciones requeridas, formato profesional en Markdown."
        ),
        agent=agente,
    )

    tarea_recomendaciones = Task(
        description=(
            "Basándote en el informe anterior, elaborá un plan de acción ejecutivo con:\n"
            "- Acciones inmediatas (urgentes, plazo < 7 días)\n"
            "- Acciones de corto plazo (1-30 días)\n"
            "- Acciones de mediano plazo (1-6 meses)\n"
            "- Estimación de costos relativos (bajo/medio/alto)\n"
            "- KPIs para monitorear la mejora\n\n"
            "Formato: tabla Markdown con columnas: Acción | Plazo | Costo | KPI de seguimiento"
        ),
        expected_output=(
            "Plan de acción ejecutivo tabular con acciones priorizadas por urgencia, "
            "plazos, estimación de costo relativo y KPIs de seguimiento."
        ),
        agent=agente,
        context_tasks=[tarea_informe],
    )

    crew = Crew(
        agents=[agente],
        tasks=[tarea_informe, tarea_recomendaciones],
    )

    return crew.kickoff()
