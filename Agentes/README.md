# Agentes — Sistema multi-agente Galli CBC

Pipeline de agentes IA para tareas de educación, APSA y escuelas.

## Estructura

```
Agentes/
├── cli.py                        ← Interfaz de consola (menú interactivo)
├── gui.py                        ← Interfaz gráfica (tkinter)
├── agentes/
│   ├── registry.py               ← Registro central de agentes
│   ├── parcial_cbc/              ← Agente: resolución de parciales CBC
│   │   ├── parcial_cbc.py
│   │   ├── agente_extractor.py
│   │   ├── agente_resolvedor.py
│   │   └── agente_generador_pdf.py
│   └── <nuevo_agente>/           ← Plantilla para agregar agentes
│       └── <nuevo_agente>.py
└── README.md
```

## Instalación

```bash
pip install anthropic reportlab matplotlib numpy pillow
```

Variable de entorno:
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-...

# Linux/Mac
export ANTHROPIC_API_KEY=sk-ant-...
```

## Uso

### Interfaz web (recomendado)
```bash
cd C:\Users\carlo\agentes-crewai\Agentes
python web.py
```
Se abre automáticamente en http://localhost:7070

### Menú interactivo en consola

### Menú interactivo en consola
```bash
python cli.py
```

### Directo desde consola
```bash
python cli.py parcial_cbc foto.jpg
python cli.py parcial_cbc parcial.pdf --salida resolucion.pdf
python cli.py --lista
```

### Interfaz gráfica
```bash
python gui.py
```

### Desde otro script Python
```python
from agentes.parcial_cbc.parcial_cbc import procesar_parcial
procesar_parcial("foto.jpg", salida="resolucion.pdf")
```

## Agregar un nuevo agente

1. Crear carpeta: `agentes/<nombre>/`
2. Crear `agentes/<nombre>/__init__.py` (vacío)
3. Crear `agentes/<nombre>/<nombre>.py` con una función principal `run(param1, param2, ...) -> str`
4. Registrar en `agentes/registry.py`:

```python
"mi_agente": {
    "nombre":      "Mi Agente",
    "descripcion": "Qué hace en una oración",
    "categoria":   "APSA",          # APSA | Educación | Escuelas | Personal
    "modulo":      "agentes.mi_agente.mi_agente",
    "funcion":     "run",
    "parametros": [
        {
            "nombre":      "ruta_entrada",
            "tipo":        "archivo",           # archivo | archivo_salida | bool | texto | entero
            "label":       "Archivo de entrada",
            "requerido":   True,
            "extensiones": [".pdf", ".xlsx"],
        },
        {
            "nombre":    "modo_debug",
            "tipo":      "bool",
            "label":     "Modo debug",
            "requerido": False,
            "default":   False,
        },
    ],
},
```

El CLI y la GUI lo detectan automáticamente — no hay nada más que tocar.

## Agentes disponibles

| Agente | Categoría | Descripción |
|--------|-----------|-------------|
| parcial_cbc | Educación | Genera PDF de resolución de parciales CBC desde PDF o foto |
