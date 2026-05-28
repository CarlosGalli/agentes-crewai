"""
registry.py — Registro central de agentes disponibles.

Para agregar un nuevo agente:
1. Crear carpeta:  agentes/<nombre>/
2. Crear archivo:  agentes/<nombre>/<nombre>.py  con función run(args) -> str
3. Agregar entrada en AGENTES abajo.
"""

AGENTES = {
    "parcial_cbc": {
        "nombre":      "Parcial CBC",
        "descripcion": "Genera PDF de resolución completa a partir de un parcial de Matemática CBC (PDF o foto)",
        "categoria":   "Educación",
        "modulo":      "agentes.parcial_cbc.parcial_cbc",
        "funcion":     "procesar_parcial",
        "parametros": [
            {
                "nombre":      "ruta_entrada",
                "tipo":        "archivo",
                "label":       "PDF o imagen del parcial",
                "requerido":   True,
                "extensiones": [".pdf", ".png", ".jpg", ".jpeg"],
            },
            {
                "nombre":    "salida",
                "tipo":      "archivo_salida",
                "label":     "PDF de salida",
                "requerido": False,
                "default":   None,   # auto: mismo directorio, _resolucion.pdf
            },
            {
                "nombre":    "imagen_enunciado",
                "tipo":      "bool",
                "label":     "Incrustar imagen del enunciado",
                "requerido": False,
                "default":   True,
            },
            {
                "nombre":    "guardar_json",
                "tipo":      "bool",
                "label":     "Guardar JSONs intermedios (debug)",
                "requerido": False,
                "default":   False,
            },
        ],
    },

    "subir_pdf": {
        "nombre":      "Subir PDF al sitio",
        "descripcion": "Sube un PDF resuelto a la solapa correspondiente del sitio quimicacbc.com",
        "categoria":   "QuimicaCBC",
        "modulo":      "agentes.subir_pdf.subir_pdf",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "titulo",
                "tipo":      "texto",
                "label":     "Título del examen (ej: 1er Parcial Di Risio)",
                "requerido": True,
            },
            {
                "nombre":    "cuatrimestre",
                "tipo":      "texto",
                "label":     "Cuatrimestre / año (ej: 1C 2025)",
                "requerido": True,
            },
            {
                "nombre":    "solapa",
                "tipo":      "opciones",
                "label":     "Solapa destino",
                "opciones":  ["1er Parcial", "2do Parcial", "Finales"],
                "requerido": True,
            },
            {
                "nombre":      "ruta_pdf",
                "tipo":        "archivo_upload",
                "label":       "Archivo PDF a subir",
                "requerido":   True,
                "extensiones": [".pdf"],
            },
        ],
    },

    # ── Plantilla para próximos agentes ────────────────────────────────────
    # "nuevo_agente": {
    #     "nombre":      "Nombre visible",
    #     "descripcion": "Qué hace en una oración",
    #     "categoria":   "APSA | Educación | Escuelas | Personal",
    #     "modulo":      "agentes.nuevo_agente.nuevo_agente",
    #     "funcion":     "run",
    #     "parametros": [
    #         {"nombre": "entrada", "tipo": "archivo", "label": "...",
    #          "requerido": True, "extensiones": [".pdf"]},
    #     ],
    # },
}

CATEGORIAS = sorted({a["categoria"] for a in AGENTES.values()})
