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

    "matematica_cbc": {
        "nombre":      "Matemática CBC",
        "descripcion": "Genera ejercicios resueltos, resúmenes y guías para las 6 unidades del CBC",
        "categoria":   "Educación",
        "modulo":      "agentes.matematica_cbc.matematica_cbc",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "tarea",
                "tipo":      "texto",
                "label":     "Tarea",
                "requerido": True,
            },
            {
                "nombre":    "unidad",
                "tipo":      "texto",
                "label":     "Unidad (opcional)",
                "requerido": False,
            },
        ],
    },

    "quimica_cbc": {
        "nombre":      "Química CBC",
        "descripcion": "Genera ejercicios resueltos y resúmenes para Química CBC-UBA",
        "categoria":   "Educación",
        "modulo":      "agentes.quimica_cbc.quimica_cbc",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "tarea",
                "tipo":      "texto",
                "label":     "Tarea",
                "requerido": True,
            },
            {
                "nombre":    "unidad",
                "tipo":      "texto",
                "label":     "Unidad (opcional)",
                "requerido": False,
            },
        ],
    },

    "apsa": {
        "nombre":      "APSA",
        "descripcion": "Genera documentos técnicos para ACUALITE PROYECTOS S.A.",
        "categoria":   "APSA",
        "modulo":      "agentes.apsa.apsa",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "tarea",
                "tipo":      "texto",
                "label":     "Tarea",
                "requerido": True,
            },
            {
                "nombre":    "tipo_documento",
                "tipo":      "texto",
                "label":     "Tipo de documento (opcional)",
                "requerido": False,
            },
            {
                "nombre":    "cliente",
                "tipo":      "texto",
                "label":     "Cliente (opcional)",
                "requerido": False,
            },
        ],
    },

    "escuelas": {
        "nombre":      "Escuelas",
        "descripcion": "Genera planificaciones y material curricular DGCyE",
        "categoria":   "Escuelas",
        "modulo":      "agentes.escuelas.escuelas",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "tarea",
                "tipo":      "texto",
                "label":     "Tarea",
                "requerido": True,
            },
            {
                "nombre":    "materia",
                "tipo":      "texto",
                "label":     "Materia (opcional)",
                "requerido": False,
            },
            {
                "nombre":    "escuela",
                "tipo":      "texto",
                "label":     "Escuela (opcional)",
                "requerido": False,
            },
            {
                "nombre":    "anio_curso",
                "tipo":      "texto",
                "label":     "Año / Curso (opcional)",
                "requerido": False,
            },
        ],
    },

    "video_derbuk": {
        "nombre":      "Video DERBUK",
        "descripcion": "Genera pantallas pedagógicas para videos de Química CBC en YouTube",
        "categoria":   "YouTube",
        "modulo":      "agentes.video_derbuk.video_derbuk",
        "funcion":     "run",
        "parametros": [
            {
                "nombre":    "ejercicio",
                "tipo":      "texto",
                "label":     "Ejercicio",
                "requerido": True,
            },
            {
                "nombre":    "unidad",
                "tipo":      "texto",
                "label":     "Unidad (opcional)",
                "requerido": False,
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
