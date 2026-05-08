# Sistema Multi-Agente: QuímicaCBC + APSA + Escuelas

Sistema de agentes especializados con arquitectura CrewAI (Agent → Task → Crew → Orchestrator),
implementado sobre el SDK de Anthropic y Claude Sonnet 4.6.

## Agentes

| Agente | Especialidad |
|--------|-------------|
| **QuímicaCBC** | Ejercicios y guías de Química para el CBC-UBA |
| **APSA** | Informes técnicos de tratamiento de agua industrial |
| **Escuelas** | Materiales didácticos para escuela secundaria |

## Arquitectura

```
main.py
  └── orchestrator.py          ← Clasifica la tarea y despacha al agente correcto
        ├── agents/quimica_cbc.py  ← Crew: 2 tareas (ejercicios + resumen teórico)
        ├── agents/apsa.py         ← Crew: 2 tareas (informe + plan de acción)
        └── agents/escuelas.py     ← Crew: 2 tareas (material + complementario)
              └── core/framework.py  ← Agent, Task, Crew (inspirado en CrewAI)
```

## Requisitos

- Python 3.10+ (probado con Python 3.14)
- API Key de Anthropic

## Instalación

```powershell
pip install anthropic
```

## Configuración

```powershell
$env:ANTHROPIC_API_KEY = "tu-api-key-aqui"
```

Para que persista entre sesiones, configurala en las variables de entorno del sistema:
1. Buscá "Variables de entorno" en Windows
2. Agregá `ANTHROPIC_API_KEY` con tu clave

## Uso

### Modo interactivo (recomendado)
```powershell
python main.py
```
El orquestador clasifica automáticamente tu tarea y la deriva al agente correcto.

**Ejemplos de tareas que podés escribir:**
- `"Necesito 5 ejercicios de estequiometría para el parcial del CBC"`
- `"Hacé un informe de diagnóstico de agua para una planta con pH 8.5 y turbidez 12 NTU"`
- `"Creá un plan de clase de Química para 3° año secundaria sobre la tabla periódica"`

### Modo demo
```powershell
python main.py --demo
```

### Agente directo (sin orquestador)
```powershell
python main.py --agente quimica_cbc
python main.py --agente apsa
python main.py --agente escuelas
```

## Resultados

Todos los resultados se guardan automáticamente en la carpeta `outputs/` como archivos `.md`.

## Nota sobre CrewAI

CrewAI oficial requiere Python <3.14. Este sistema implementa la misma arquitectura
(Agent, Task, Crew, Orchestrator) usando el SDK de Anthropic directamente,
compatible con Python 3.14+.
