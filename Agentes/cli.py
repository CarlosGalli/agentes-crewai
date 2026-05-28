"""
cli.py — Interfaz de línea de comandos con menú interactivo.

Uso:
    python cli.py                  # menú interactivo
    python cli.py parcial_cbc      # lanzar agente directamente
    python cli.py --lista          # listar agentes disponibles
"""

import sys
import os
import importlib
import argparse
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from agentes.registry import AGENTES, CATEGORIAS

# ── colores ANSI ──────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    PURPLE = "\033[35m"
    CYAN   = "\033[36m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    RED    = "\033[31m"
    GRAY   = "\033[90m"
    BG_DARK = "\033[40m"

def _ansi(texto, *codigos):
    """Aplica códigos ANSI si la terminal los soporta."""
    if not sys.stdout.isatty():
        return texto
    return "".join(codigos) + texto + C.RESET

def cls():
    os.system("cls" if os.name == "nt" else "clear")

# ── helpers de entrada ────────────────────────────────────────────────────────
def pedir(prompt, default=None, tipo=str):
    sufijo = f" [{default}]" if default is not None else ""
    raw = input(f"  {prompt}{sufijo}: ").strip()
    if raw == "" and default is not None:
        return default
    if raw == "":
        return None
    try:
        return tipo(raw)
    except Exception:
        return raw

def pedir_archivo(label, extensiones=None):
    while True:
        ruta = pedir(label)
        if ruta is None:
            return None
        p = Path(ruta)
        if not p.exists():
            print(_ansi(f"  ! Archivo no encontrado: {ruta}", C.RED))
            continue
        if extensiones and p.suffix.lower() not in extensiones:
            print(_ansi(f"  ! Extensión no válida. Permitidas: {extensiones}", C.YELLOW))
            continue
        return str(p)

def pedir_bool(label, default=True):
    d = "S/n" if default else "s/N"
    raw = input(f"  {label} [{d}]: ").strip().lower()
    if raw == "":
        return default
    return raw in ("s", "si", "sí", "y", "yes", "1", "true")

def pedir_archivo_salida(label, default=None):
    ruta = pedir(label, default=default or "(auto)")
    if not ruta or ruta == "(auto)":
        return None
    return ruta

# ── menú principal ────────────────────────────────────────────────────────────
def mostrar_banner():
    print()
    print(_ansi("  ╔══════════════════════════════════════╗", C.PURPLE, C.BOLD))
    print(_ansi("  ║          AGENTES — Galli CBC          ║", C.PURPLE, C.BOLD))
    print(_ansi("  ╚══════════════════════════════════════╝", C.PURPLE, C.BOLD))
    print()

def mostrar_lista():
    """Muestra todos los agentes organizados por categoría."""
    keys = list(AGENTES.keys())
    idx  = 1
    mapa = {}   # número → key

    for cat in CATEGORIAS:
        agentes_cat = [(k, v) for k, v in AGENTES.items() if v["categoria"] == cat]
        if not agentes_cat:
            continue
        print(_ansi(f"  {cat}", C.CYAN, C.BOLD))
        for key, ag in agentes_cat:
            num = str(idx)
            mapa[num] = key
            print(f"    {_ansi(num.rjust(2) + '.', C.YELLOW)} "
                  f"{_ansi(ag['nombre'], C.BOLD)}  "
                  f"{_ansi(ag['descripcion'], C.GRAY)}")
            idx += 1
        print()

    return mapa

def menu_interactivo():
    cls()
    mostrar_banner()
    mapa = mostrar_lista()
    print(_ansi("  0.  Salir", C.GRAY))
    print()

    eleccion = input("  Elegir agente (número o nombre): ").strip()

    if eleccion == "0" or eleccion.lower() in ("salir", "exit", "q"):
        print()
        return None

    # Por número
    if eleccion in mapa:
        return mapa[eleccion]

    # Por nombre de key
    if eleccion in AGENTES:
        return eleccion

    # Búsqueda parcial por nombre visible
    matches = [k for k, v in AGENTES.items()
               if eleccion.lower() in v["nombre"].lower() or
                  eleccion.lower() in k.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(_ansi(f"\n  Varios agentes coinciden: {matches}", C.YELLOW))
        return None

    print(_ansi(f"\n  Agente no encontrado: '{eleccion}'", C.RED))
    return None

# ── recolección de parámetros ─────────────────────────────────────────────────
def recolectar_parametros(key: str) -> dict:
    ag = AGENTES[key]
    print()
    print(_ansi(f"  ── {ag['nombre']} ──", C.PURPLE, C.BOLD))
    print(_ansi(f"  {ag['descripcion']}", C.GRAY))
    print()

    kwargs = {}
    for p in ag["parametros"]:
        nombre = p["nombre"]
        tipo   = p["tipo"]
        label  = p["label"]
        req    = p.get("requerido", False)
        default = p.get("default")

        if tipo == "archivo":
            val = pedir_archivo(label, p.get("extensiones"))
            if val is None and req:
                print(_ansi("  Parámetro requerido.", C.RED))
                return None
            kwargs[nombre] = val

        elif tipo == "archivo_salida":
            val = pedir_archivo_salida(label, default)
            kwargs[nombre] = val

        elif tipo == "bool":
            kwargs[nombre] = pedir_bool(label, default if default is not None else True)

        elif tipo == "texto":
            val = pedir(label, default)
            kwargs[nombre] = val

        elif tipo == "opciones":
            opciones = p.get("opciones", [])
            print(f"\n  {label}:")
            for i, op in enumerate(opciones, 1):
                print(f"    {i}. {op}")
            while True:
                raw = input(f"  Elegí (1-{len(opciones)}): ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(opciones):
                    val = opciones[int(raw) - 1]
                    break
                if raw in opciones:
                    val = raw
                    break
                print(_ansi(f"  Opción inválida.", C.YELLOW))
            kwargs[nombre] = val

        elif tipo == "entero":
            val = pedir(label, default, tipo=int)
            kwargs[nombre] = val

    return kwargs

# ── ejecutor ──────────────────────────────────────────────────────────────────
def ejecutar_agente(key: str, kwargs: dict):
    ag = AGENTES[key]
    print()
    print(_ansi(f"  Iniciando: {ag['nombre']}...", C.GREEN))
    print(_ansi("  " + "─" * 40, C.GRAY))
    print()

    try:
        modulo = importlib.import_module(ag["modulo"])
        funcion = getattr(modulo, ag["funcion"])
        # Agregar verbose=True si la función lo acepta
        import inspect
        sig = inspect.signature(funcion)
        if "verbose" in sig.parameters:
            kwargs["verbose"] = True
        resultado = funcion(**kwargs)
        print()
        print(_ansi(f"  ✓ Completado.", C.GREEN, C.BOLD))
        if resultado:
            print(_ansi(f"  Salida: {resultado}", C.CYAN))
    except KeyboardInterrupt:
        print(_ansi("\n  Cancelado.", C.YELLOW))
    except Exception as e:
        print(_ansi(f"\n  Error: {e}", C.RED))
        import traceback
        traceback.print_exc()

# ── CLI directo (sin menú) ────────────────────────────────────────────────────
def cli_directo(key: str, args_extra: list):
    """
    Invoca un agente pasando parámetros por línea de comandos.
    Ejemplo: python cli.py parcial_cbc archivo.pdf --sin-imagen
    """
    if key not in AGENTES:
        print(_ansi(f"Agente desconocido: '{key}'", C.RED))
        print(f"Disponibles: {list(AGENTES.keys())}")
        sys.exit(1)

    ag = AGENTES[key]

    # Parser dinámico según los parámetros del agente
    sub = argparse.ArgumentParser(prog=f"cli.py {key}",
                                   description=ag["descripcion"])
    for p in ag["parametros"]:
        nombre  = p["nombre"]
        req     = p.get("requerido", False)
        default = p.get("default")
        tipo_p  = p["tipo"]

        if tipo_p == "bool":
            sub.add_argument(f"--{nombre.replace('_','-')}",
                             dest=nombre, action="store_true", default=default)
            sub.add_argument(f"--no-{nombre.replace('_','-')}",
                             dest=nombre, action="store_false")
        elif req:
            sub.add_argument(nombre)
        else:
            sub.add_argument(f"--{nombre.replace('_','-')}",
                             dest=nombre, default=default)

    parsed = sub.parse_args(args_extra)
    kwargs = vars(parsed)

    ejecutar_agente(key, kwargs)

# ── punto de entrada ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Lanzador de agentes — Galli CBC",
        add_help=False
    )
    parser.add_argument("agente",   nargs="?", help="Nombre del agente a ejecutar")
    parser.add_argument("--lista",  action="store_true", help="Listar agentes disponibles")
    parser.add_argument("--help",   action="store_true")

    args, resto = parser.parse_known_args()

    if args.help and not args.agente:
        print(__doc__)
        mostrar_banner()
        mostrar_lista()
        return

    if args.lista:
        mostrar_banner()
        mostrar_lista()
        return

    if args.agente:
        cli_directo(args.agente, resto)
        return

    # Modo interactivo
    while True:
        key = menu_interactivo()
        if key is None:
            break
        kwargs = recolectar_parametros(key)
        if kwargs is not None:
            ejecutar_agente(key, kwargs)
        print()
        input(_ansi("  Presioná Enter para volver al menú...", C.GRAY))
        cls()

if __name__ == "__main__":
    main()
