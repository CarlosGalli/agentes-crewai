"""
CLI principal del sistema multi-agente.
Uso:
    python main.py                          # Modo interactivo
    python main.py --demo                   # Ejecuta demos de los 4 agentes
    python main.py --agente quimica_cbc     # Usar agente específico directamente
    python main.py --agente matematica_cbc
    python main.py --agente apsa
    python main.py --agente escuelas
"""
import argparse
import sys
import os
from pathlib import Path

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, str(Path(__file__).parent))

# La consola de Windows usa cp1252 por defecto y rompe al imprimir emojis o
# caracteres fuera de Latin-1 que generan los modelos. Forzamos UTF-8 con
# fallback a 'replace' para que los prints nunca aborten la corrida.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def verificar_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nError: La variable ANTHROPIC_API_KEY no está configurada.")
        print("Configurala así en PowerShell:")
        print('  $env:ANTHROPIC_API_KEY = "tu-api-key-aqui"')
        print("\nO agregala permanentemente en las variables de entorno de Windows.")
        sys.exit(1)


def modo_interactivo():
    """Modo conversacional: el usuario ingresa tareas y el orquestador las clasifica."""
    import orchestrator

    print("\n" + "="*60)
    print("  SISTEMA MULTI-AGENTE - Modo Interactivo")
    print("  Agentes disponibles:")
    print("    - QuímicaCBC: ejercicios y guías de química universitaria")
    print("    - MatemáticaCBC: ejercicios resueltos de matemática universitaria")
    print("    - APSA: informes técnicos de tratamiento de agua")
    print("    - Escuelas: materiales didácticos para secundaria")
    print("="*60)
    print("Escribí tu tarea y el sistema la derivará al agente correcto.")
    print("Comandos: 'salir' o 'exit' para terminar\n")

    while True:
        try:
            tarea = input("Tarea > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break

        if not tarea:
            continue
        if tarea.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego!")
            break

        try:
            resultado = orchestrator.procesar(tarea)
            print("\n" + "="*60)
            print("RESULTADO:")
            print("="*60)
            print(resultado[:3000])
            if len(resultado) > 3000:
                print(f"\n... (resultado completo guardado en outputs/)")
        except Exception as e:
            print(f"\nError al procesar la tarea: {e}")


def modo_agente_directo(agente: str):
    """Usa un agente específico con parámetros interactivos."""
    if agente == "quimica_cbc":
        from agents import quimica_cbc
        tema = input("Tema de Química CBC (ej: estequiometría): ").strip() or "estequiometría"
        cantidad = input("Cantidad de ejercicios [5]: ").strip() or "5"
        dificultad = input("Dificultad (básica/intermedia/avanzada/mixta) [mixta]: ").strip() or "mixta"
        resultado = quimica_cbc.crew_ejercicios(tema, int(cantidad), dificultad)

    elif agente == "matematica_cbc":
        from agents import matematica_cbc
        tema = input("Tema de Matemática CBC (ej: derivadas, límites, trigonometría): ").strip() or "derivadas"
        cantidad = input("Cantidad de ejercicios [5]: ").strip() or "5"
        dificultad = input("Dificultad (básica/intermedia/avanzada/mixta) [mixta]: ").strip() or "mixta"
        resultado = matematica_cbc.crew_ejercicios(tema, int(cantidad), dificultad)

    elif agente == "apsa":
        from agents import apsa
        tipo = input("Tipo de informe (análisis/diagnóstico/diseño/auditoría) [diagnóstico]: ").strip() or "diagnóstico"
        instalacion = input("Descripción de la instalación: ").strip() or "Planta potabilizadora municipal"
        resultado = apsa.crew_informe(tipo, instalacion)

    elif agente == "escuelas":
        from agents import escuelas
        materia = input("Materia (ej: Química, Biología, Física): ").strip() or "Química"
        anio = input("Año del secundario (ej: 3° año): ").strip() or "3° año"
        tema = input("Tema: ").strip() or "reacciones químicas"
        tipo = input("Tipo de material (plan de clase/guía/evaluación/actividad) [plan de clase]: ").strip() or "plan de clase"
        resultado = escuelas.crew_material(materia, anio, tema, tipo)
    else:
        print(f"Agente '{agente}' no reconocido. Opciones: quimica_cbc, matematica_cbc, apsa, escuelas")
        sys.exit(1)

    import orchestrator
    output_path = orchestrator.guardar_output(agente, f"[modo directo] {agente}", resultado)
    print(f"\n[Resultado guardado en: {output_path}]")

    print("\n" + "="*60)
    print(resultado[:5000])
    if len(resultado) > 5000:
        print("\n... (ver archivo completo en outputs/)")


def modo_demo():
    """Ejecuta una tarea de demostración para cada uno de los 3 agentes."""
    import orchestrator

    demos = [
        (
            "quimica_cbc",
            "Necesito 3 ejercicios de estequiometría para el parcial de Química del CBC, "
            "nivel básico, con resolución detallada"
        ),
        (
            "matematica_cbc",
            "Necesito 3 ejercicios resueltos de derivadas para el parcial de Matemática del CBC, "
            "nivel intermedio, incluyendo regla de la cadena"
        ),
        (
            "apsa",
            "Informe de diagnóstico de calidad del agua para una planta de tratamiento "
            "municipal con problemas de turbidez elevada (15 NTU) y cloro libre bajo (0.1 mg/L)"
        ),
        (
            "escuelas",
            "Plan de clase de 80 minutos para 3° año de secundaria sobre reacciones "
            "químicas cotidianas, con actividades prácticas"
        ),
    ]

    print("\n=== MODO DEMO: Probando los 4 agentes ===\n")

    for agente_esperado, tarea in demos:
        print(f"\n{'#'*60}")
        print(f"Demo: {agente_esperado.upper()}")
        print(f"{'#'*60}")
        try:
            resultado = orchestrator.procesar(tarea)
            # Solo mostrar el inicio del resultado en consola
            print("\n--- Resultado (primeras 800 palabras) ---")
            words = resultado.split()
            preview = " ".join(words[:200])
            print(preview)
            if len(words) > 200:
                print("\n[... resultado completo en outputs/ ...]")
        except Exception as e:
            print(f"Error en demo {agente_esperado}: {e}")

    print("\n=== Demo completado. Revisá la carpeta outputs/ para los resultados completos ===")


def main():
    verificar_api_key()

    parser = argparse.ArgumentParser(
        description="Sistema Multi-Agente: QuímicaCBC + MatemáticaCBC + APSA + Escuelas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                            Modo interactivo con orquestador
  python main.py --demo                     Demo de los 4 agentes
  python main.py --agente quimica_cbc       Usar agente de Química CBC directamente
  python main.py --agente matematica_cbc    Usar agente de Matemática CBC directamente
  python main.py --agente apsa              Usar agente APSA directamente
  python main.py --agente escuelas          Usar agente de Escuelas directamente
        """
    )
    parser.add_argument("--demo", action="store_true", help="Ejecutar demos de los 4 agentes")
    parser.add_argument(
        "--agente",
        choices=["quimica_cbc", "matematica_cbc", "apsa", "escuelas"],
        help="Usar un agente específico directamente (sin orquestador)"
    )

    args = parser.parse_args()

    if args.demo:
        modo_demo()
    elif args.agente:
        modo_agente_directo(args.agente)
    else:
        modo_interactivo()


if __name__ == "__main__":
    main()
