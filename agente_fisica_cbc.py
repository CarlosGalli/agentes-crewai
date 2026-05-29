"""
agente_fisica_cbc.py
Agente generador de contenido para FísicaCBC.
Genera soluciones paso a paso en formato JSON para los 180 ejercicios del banco.
Uso: python agente_fisica_cbc.py
      python agente_fisica_cbc.py --unidad 1      (solo una unidad)
      python agente_fisica_cbc.py --desde 11 --hasta 20 --unidad 2  (rango)
      python agente_fisica_cbc.py --dry-run       (ver plan sin llamar a la API)
Requisito: variable de entorno ANTHROPIC_API_KEY
Salida:    outputs/fisica_cbc_ejercicios.json  (acumulativo)
"""

import anthropic
import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Fix Unicode output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── BANCO DE EJERCICIOS ────────────────────────────────────────────────────────

UNIDADES = [
    {
        "id": 1,
        "nombre": "Magnitudes y vectores",
        "descripcion": "Magnitudes escalares y vectoriales, operaciones con vectores, descomposición, módulo, ángulo, unidades SI.",
        "ejercicios": [
            {"n": 1,  "desc": "Identificar si una magnitud es escalar o vectorial", "tip": "Distinguir masa, velocidad, temperatura, fuerza", "niv": 1},
            {"n": 2,  "desc": "Calcular el módulo de un vector dado en componentes (2D)", "tip": "Usar √(Fx²+Fy²)", "niv": 1},
            {"n": 3,  "desc": "Hallar el ángulo que forma un vector con el eje x", "tip": "θ = arctan(Fy/Fx)", "niv": 1},
            {"n": 4,  "desc": "Sumar dos vectores gráficamente (regla del paralelogramo)", "tip": "Colocar cola con cola", "niv": 1},
            {"n": 5,  "desc": "Descomponer un vector en sus componentes cartesianas", "tip": "Fx = F·cos θ, Fy = F·sen θ", "niv": 1},
            {"n": 6,  "desc": "Convertir unidades: km/h → m/s", "tip": "Dividir por 3,6", "niv": 1},
            {"n": 7,  "desc": "Hallar el vector resultante de tres vectores colineales", "tip": "Suma algebraica directa", "niv": 1},
            {"n": 8,  "desc": "Calcular el producto escalar de dos vectores", "tip": "A·B = |A||B|cos α", "niv": 1},
            {"n": 9,  "desc": "Determinar si dos vectores son perpendiculares", "tip": "Verificar que A·B = 0", "niv": 1},
            {"n": 10, "desc": "Hallar el versor de un vector", "tip": "Dividir por su módulo", "niv": 1},
            {"n": 11, "desc": "Sumar dos vectores en ángulo de 60° entre sí", "tip": "Usar ley de cosenos", "niv": 2},
            {"n": 12, "desc": "Descomponer un vector en dirección paralela y perpendicular a un plano inclinado", "tip": "Rotar el sistema de ejes", "niv": 2},
            {"n": 13, "desc": "Determinar el tercer vector para que la resultante sea nula", "tip": "El tercero es opuesto a la suma de los dos primeros", "niv": 2},
            {"n": 14, "desc": "Sumar cuatro vectores no colineales con ángulos dados", "tip": "Sumar componentes x e y por separado", "niv": 2},
            {"n": 15, "desc": "Calcular el trabajo de una fuerza aplicada en ángulo", "tip": "W = F·d·cos θ", "niv": 2},
            {"n": 16, "desc": "Descomponer la velocidad inicial de un proyectil", "tip": "vx = v₀·cos θ, vy = v₀·sen θ", "niv": 2},
            {"n": 17, "desc": "Determinar el ángulo entre dos vectores dado su producto escalar", "tip": "cos α = (A·B)/(|A||B|)", "niv": 2},
            {"n": 18, "desc": "Hallar la resultante de fuerzas en equilibrio estático bidimensional", "tip": "ΣFx = 0 y ΣFy = 0", "niv": 2},
            {"n": 19, "desc": "Calcular el módulo y dirección de la aceleración centrípeta", "tip": "ac = v²/r, apunta al centro", "niv": 2},
            {"n": 20, "desc": "Sumar tres vectores con ángulos no estándar y verificar el balance", "tip": "Convertir a componentes antes de sumar", "niv": 2},
            {"n": 21, "desc": "Problema combinado: vectores + unidades + conversión de ángulos", "tip": "Mezcla de herramientas de la unidad", "niv": 3},
            {"n": 22, "desc": "Hallar el vector diferencia entre velocidad final e inicial", "tip": "Δv = v_f − v_i (vectorialmente)", "niv": 3},
            {"n": 23, "desc": "Calcular la componente de una fuerza en una dirección oblicua arbitraria", "tip": "Proyección vectorial: F_proy = (F·û)", "niv": 3},
            {"n": 24, "desc": "Analizar el equilibrio de un cuerpo con 4 fuerzas en distintas direcciones", "tip": "Cuatro ecuaciones de componentes", "niv": 3},
            {"n": 25, "desc": "Resolver un sistema donde la resultante tiene módulo y ángulo dados", "tip": "Despejar vector desconocido", "niv": 3},
            {"n": 26, "desc": "Calcular la velocidad relativa entre dos móviles en 2D", "tip": "v_rel = v_A − v_B (vectorial)", "niv": 3},
            {"n": 27, "desc": "Determinar el ángulo de lanzamiento óptimo para alcance máximo", "tip": "Máximo en θ = 45°, demostrar con derivada", "niv": 3},
            {"n": 28, "desc": "Resolver vectores en 3D: calcular módulo y ángulos directores", "tip": "Usar tres componentes y arccos", "niv": 3},
            {"n": 29, "desc": "Problema de navegación: corriente de agua + velocidad del bote", "tip": "Composición vectorial de velocidades", "niv": 3},
            {"n": 30, "desc": "Problema integral de vectores con datos ambiguos (múltiples soluciones posibles)", "tip": "Plantear ambas soluciones geométricamente", "niv": 3},
        ]
    },
    {
        "id": 2,
        "nombre": "Cinemática",
        "descripcion": "MRU, MRUV, caída libre, tiro oblicuo, movimiento relativo, MCU. Gráficas x-t y v-t.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular velocidad media dado desplazamiento y tiempo", "tip": "v_m = Δx / Δt", "niv": 1},
            {"n": 2,  "desc": "Determinar posición en MRU dado x₀, v y t", "tip": "x = x₀ + v·t", "niv": 1},
            {"n": 3,  "desc": "Calcular aceleración en MRUV dado v₀, v_f y t", "tip": "a = (v_f − v₀) / t", "niv": 1},
            {"n": 4,  "desc": "Hallar distancia recorrida en MRUV", "tip": "x = v₀t + ½at²", "niv": 1},
            {"n": 5,  "desc": "Identificar tipo de movimiento desde una gráfica x-t", "tip": "Recta = MRU; parábola = MRUV", "niv": 1},
            {"n": 6,  "desc": "Leer velocidad instantánea en una gráfica x-t", "tip": "Pendiente en ese punto", "niv": 1},
            {"n": 7,  "desc": "Calcular tiempo de caída libre desde una altura dada", "tip": "h = ½gt², despejar t", "niv": 1},
            {"n": 8,  "desc": "Hallar velocidad al llegar al suelo en caída libre", "tip": "v² = 2gh", "niv": 1},
            {"n": 9,  "desc": "Calcular periodo y frecuencia en MCU", "tip": "T = 2πr/v, f = 1/T", "niv": 1},
            {"n": 10, "desc": "Determinar la aceleración centrípeta en MCU", "tip": "ac = v²/r = ω²r", "niv": 1},
            {"n": 11, "desc": "Resolver encuentro entre dos móviles en MRU (¿cuándo se encuentran?)", "tip": "Igualar ecuaciones de posición", "niv": 2},
            {"n": 12, "desc": "Calcular x_max y tiempo de vuelo en tiro vertical", "tip": "En x_max: v = 0; tiempo total = 2·t_subida", "niv": 2},
            {"n": 13, "desc": "Problema de tiro oblicuo: hallar alcance y altura máxima", "tip": "X = v₀²·sen2θ/g, H = v₀²·sen²θ/2g", "niv": 2},
            {"n": 14, "desc": "Resolver movimiento relativo: barco en corriente fluvial", "tip": "v_resultante = suma vectorial", "niv": 2},
            {"n": 15, "desc": "Graficar v-t de un movimiento con frenado y aceleración", "tip": "Pendiente = aceleración, área = desplazamiento", "niv": 2},
            {"n": 16, "desc": "Calcular velocidad angular y lineal en MCU dado radio y período", "tip": "ω = 2π/T, v = ω·r", "niv": 2},
            {"n": 17, "desc": "Problema MRUV: vehículo que frena hasta detenerse, calcular distancia de frenado", "tip": "v_f = 0, usar v² = v₀² − 2a·d", "niv": 2},
            {"n": 18, "desc": "Hallar el ángulo de tiro para alcanzar un blanco a distancia y altura conocidas", "tip": "Sistema de ecuaciones paramétricas", "niv": 2},
            {"n": 19, "desc": "Determinar en qué instante y dónde se cruzan dos objetos en MRUV", "tip": "Igualar x₁(t) = x₂(t)", "niv": 2},
            {"n": 20, "desc": "Analizar movimiento en dos fases (MRU luego MRUV)", "tip": "Separar en intervalos, aplicar condición inicial de cada fase", "niv": 2},
            {"n": 21, "desc": "Problema de tiro oblicuo: proyectil debe pasar sobre un obstáculo", "tip": "Evaluar y(t) en el instante en que x = distancia obstáculo", "niv": 3},
            {"n": 22, "desc": "Movimiento relativo en 2D: avión con viento lateral, calcular ángulo de corrección", "tip": "Composición vectorial de velocidades", "niv": 3},
            {"n": 23, "desc": "Gráfica v-t compleja: interpretar fases y calcular desplazamiento total", "tip": "Área bajo la curva (sumar áreas geométricas)", "niv": 3},
            {"n": 24, "desc": "MRUV con aceleración variable en dos tramos: calcular posición final", "tip": "Resolver cada tramo con sus condiciones iniciales", "niv": 3},
            {"n": 25, "desc": "Tiro oblicuo desde altura h: calcular alcance y velocidad de impacto", "tip": "El eje y no empieza en cero", "niv": 3},
            {"n": 26, "desc": "Determinar aceleración desde una gráfica x-t cuadrática", "tip": "a = 2·(coeficiente del t²)", "niv": 3},
            {"n": 27, "desc": "Calcular la velocidad de un objeto en MCU no uniforme (con aceleración tangencial)", "tip": "Separar componentes radial y tangencial", "niv": 3},
            {"n": 28, "desc": "Problema de dos proyectiles lanzados en distintos instantes: ¿se alcanzan?", "tip": "Plantear x₁(t) = x₂(t−t₀)", "niv": 3},
            {"n": 29, "desc": "Analizar la velocidad relativa de dos autos en curva", "tip": "Tener en cuenta cambio de dirección", "niv": 3},
            {"n": 30, "desc": "Problema integrador: movimiento en tres fases con cambio de aceleración", "tip": "Condición de continuidad entre fases", "niv": 3},
        ]
    },
    {
        "id": 3,
        "nombre": "Estática",
        "descripcion": "Equilibrio de cuerpos puntuales y rígidos, torques, centro de masa, condiciones de equilibrio.",
        "ejercicios": [
            {"n": 1,  "desc": "Verificar equilibrio de un punto material con dos fuerzas", "tip": "ΣF = 0", "niv": 1},
            {"n": 2,  "desc": "Calcular la tensión de una cuerda que sostiene un peso", "tip": "T = mg", "niv": 1},
            {"n": 3,  "desc": "Determinar la normal sobre un plano horizontal", "tip": "N = mg (sin inclinación)", "niv": 1},
            {"n": 4,  "desc": "Hallar el torque de una fuerza respecto a un pivote", "tip": "τ = F · d⊥", "niv": 1},
            {"n": 5,  "desc": "Identificar el pivote de un sistema en equilibrio", "tip": "Elegir el punto donde actúa la mayor incógnita", "niv": 1},
            {"n": 6,  "desc": "Calcular el centro de masa de dos objetos sobre una barra", "tip": "x_cm = (m₁x₁ + m₂x₂)/(m₁+m₂)", "niv": 1},
            {"n": 7,  "desc": "Analizar equilibrio de una balanza simple", "tip": "Torque neto = 0 respecto al fulcro", "niv": 1},
            {"n": 8,  "desc": "Determinar si un cuerpo en reposo está en equilibrio estable o inestable", "tip": "Posición del CM respecto al punto de apoyo", "niv": 1},
            {"n": 9,  "desc": "Calcular la fuerza necesaria para mantener equilibrio en palanca de primer género", "tip": "F₁·d₁ = F₂·d₂", "niv": 1},
            {"n": 10, "desc": "Sumar torques de dos fuerzas paralelas respecto al mismo pivote", "tip": "Torques en sentido contrario se restan", "niv": 1},
            {"n": 11, "desc": "Barra apoyada en dos soportes con carga central: hallar reacciones", "tip": "ΣF=0 y Στ=0", "niv": 2},
            {"n": 12, "desc": "Calcular tensión en cuerda oblicua que sostiene una viga horizontal", "tip": "Descomponer T y aplicar ΣFx=0, ΣFy=0", "niv": 2},
            {"n": 13, "desc": "Determinar la posición de una carga para que una viga esté en equilibrio", "tip": "Despejar x en la ecuación de torques", "niv": 2},
            {"n": 14, "desc": "Analizar equilibrio de un cuerpo con 3 fuerzas no paralelas", "tip": "Regla del triángulo de fuerzas", "niv": 2},
            {"n": 15, "desc": "Calcular el centro de masa de un sistema de 4 partículas en 2D", "tip": "Calcular x_cm e y_cm por separado", "niv": 2},
            {"n": 16, "desc": "Escalera apoyada en pared lisa: calcular fuerzas en los apoyos", "tip": "Elegir pivote en la base de la escalera", "niv": 2},
            {"n": 17, "desc": "Grúa con brazo horizontal: hallar la tensión del cable de soporte", "tip": "Στ=0 respecto al pivote del brazo", "niv": 2},
            {"n": 18, "desc": "Calcular el torque neto de un par de fuerzas", "tip": "τ_neto = F · d (independiente del pivote)", "niv": 2},
            {"n": 19, "desc": "Determinar condiciones de equilibrio de un cuerpo sumergido parcialmente", "tip": "Combinar empuje, peso y geometría", "niv": 2},
            {"n": 20, "desc": "Sistema de poleas: hallar fuerza para levantar peso en equilibrio", "tip": "Ventaja mecánica = nro de cuerdas activas", "niv": 2},
            {"n": 21, "desc": "Viga empotrada con carga distribuida: calcular reacción en el empotramiento", "tip": "Modelar la carga distribuida como fuerza puntual en el CM", "niv": 3},
            {"n": 22, "desc": "Equilibrio de estructura en L con múltiples cargas", "tip": "Dos ecuaciones de torques en puntos distintos", "niv": 3},
            {"n": 23, "desc": "Determinar el punto de vuelco de un cajón con fuerza horizontal aplicada", "tip": "El vuelco ocurre cuando τ_vuelco ≥ τ_estabilizador", "niv": 3},
            {"n": 24, "desc": "Sistema articulado: calcular fuerzas internas en cada barra", "tip": "Método de nodos", "niv": 3},
            {"n": 25, "desc": "Hallar el CM de una figura plana con cavidad (técnica de resta)", "tip": "CM_total = CM_llena − CM_hueco (pesados por área)", "niv": 3},
            {"n": 26, "desc": "Grúa con brazo inclinado: calcular tensión y reacción en el pivote", "tip": "Descomponer todas las fuerzas antes de aplicar equilibrio", "niv": 3},
            {"n": 27, "desc": "Problema de puente: distribuir carga entre dos pilares en función de la posición", "tip": "Variable es la distancia al apoyo", "niv": 3},
            {"n": 28, "desc": "Calcular la fuerza de rozamiento estático máxima antes del deslizamiento", "tip": "f_max = μ_e · N", "niv": 3},
            {"n": 29, "desc": "Analizar estabilidad de un cubo en distintas posiciones (cara, arista, vértice)", "tip": "CM y base de sustentación", "niv": 3},
            {"n": 30, "desc": "Problema integrador: estructura con cargas oblicuas en múltiples puntos", "tip": "Resolución sistemática: ΣFx=0, ΣFy=0, Στ=0", "niv": 3},
        ]
    },
    {
        "id": 4,
        "nombre": "Hidrostática",
        "descripcion": "Presión, principio de Pascal, empuje de Arquímedes, flotación, densidad, manómetros.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular la presión en el fondo de un recipiente con agua", "tip": "P = P₀ + ρgh", "niv": 1},
            {"n": 2,  "desc": "Convertir unidades de presión: atm, Pa, mmHg", "tip": "1 atm = 101325 Pa = 760 mmHg", "niv": 1},
            {"n": 3,  "desc": "Calcular la fuerza sobre el fondo de un recipiente", "tip": "F = P · A", "niv": 1},
            {"n": 4,  "desc": "Determinar la presión manométrica de un fluido", "tip": "P_man = P_abs − P_atm", "niv": 1},
            {"n": 5,  "desc": "Calcular la densidad de un sólido a partir de masa y volumen", "tip": "ρ = m/V", "niv": 1},
            {"n": 6,  "desc": "Aplicar el principio de Pascal en un gato hidráulico", "tip": "F₁/A₁ = F₂/A₂", "niv": 1},
            {"n": 7,  "desc": "Calcular el empuje sobre un cubo completamente sumergido", "tip": "E = ρ_f · V · g", "niv": 1},
            {"n": 8,  "desc": "Determinar si un objeto flota o se hunde comparando densidades", "tip": "ρ_obj vs ρ_fluido", "niv": 1},
            {"n": 9,  "desc": "Calcular la masa de líquido desplazado por un objeto que flota", "tip": "m_desplazado = m_objeto (principio de Arquímedes)", "niv": 1},
            {"n": 10, "desc": "Hallar la presión a distintas profundidades en el mar", "tip": "P aumenta ~1 atm cada 10 m", "niv": 1},
            {"n": 11, "desc": "Calcular la fracción sumergida de un iceberg en agua de mar", "tip": "V_sumerj/V_total = ρ_hielo/ρ_agua", "niv": 2},
            {"n": 12, "desc": "Determinar la densidad de un sólido usando la pérdida de peso aparente en agua", "tip": "ρ_obj = m_aire / (m_aire − m_agua) · ρ_agua", "niv": 2},
            {"n": 13, "desc": "Calcular la fuerza que ejerce la tapa lateral de un recipiente a presión", "tip": "F = P_media · A_tapa", "niv": 2},
            {"n": 14, "desc": "Calcular el volumen de un objeto que flota con cierta fracción emergida", "tip": "Despejar V del equilibrio de fuerzas", "niv": 2},
            {"n": 15, "desc": "Gato hidráulico: calcular desplazamiento del pistón pequeño dado desplazamiento del grande", "tip": "A₁·Δh₁ = A₂·Δh₂", "niv": 2},
            {"n": 16, "desc": "Determinar la presión en el interior de una arteria profunda (modelo simplificado)", "tip": "Aplicar P = P₀ + ρgh con ρ_sangre", "niv": 2},
            {"n": 17, "desc": "Calcular el peso aparente de un objeto sumergido en aceite", "tip": "P_aparente = P_real − E", "niv": 2},
            {"n": 18, "desc": "Hallar la altura del fluido en un manómetro de tubo en U con dos líquidos", "tip": "Presiones iguales al nivel de la interfase", "niv": 2},
            {"n": 19, "desc": "Determinar la presión en el punto más profundo de un recipiente con forma irregular", "tip": "Solo importa la profundidad, no la forma", "niv": 2},
            {"n": 20, "desc": "Calcular la densidad de mezcla de dos líquidos inmiscibles", "tip": "Promediar pesado por volumen", "niv": 2},
            {"n": 21, "desc": "Objeto lastrado: calcular masa del lastre para que el conjunto flote al ras", "tip": "E_total = P_total, despejar m_lastre", "niv": 3},
            {"n": 22, "desc": "Calcular la presión en el fondo de un recipiente conectado con distinto nivel de líquido", "tip": "Los vasos comunicantes igualan presiones a igual profundidad", "niv": 3},
            {"n": 23, "desc": "Diseño de un flotador industrial: calcular volumen mínimo para soportar una carga", "tip": "E ≥ P_carga + P_flotador", "niv": 3},
            {"n": 24, "desc": "Prensa hidráulica: calcular número de bombeos necesarios para elevar un peso", "tip": "Combinar Pascal con desplazamiento de volumen", "niv": 3},
            {"n": 25, "desc": "Calcular la presión en un punto dentro de dos fluidos superpuestos", "tip": "Sumar columnas: P = P₀ + ρ₁gh₁ + ρ₂gh₂", "niv": 3},
            {"n": 26, "desc": "Problema de barco: calcular el calado según la carga", "tip": "Equilibrio hidrostático, despejar h", "niv": 3},
            {"n": 27, "desc": "Manómetro con mercurio y otro fluido: calcular la presión desconocida", "tip": "Igualar presiones en la rama de referencia", "niv": 3},
            {"n": 28, "desc": "Globo aerostático: calcular el volumen para elevar una carga", "tip": "E_aire = P_globo + P_carga", "niv": 3},
            {"n": 29, "desc": "Analizar el efecto de la temperatura en la densidad y el empuje", "tip": "ρ disminuye al calentar, E también", "niv": 3},
            {"n": 30, "desc": "Problema integrador: combinar Pascal, Arquímedes y cálculo de presiones en sistema complejo", "tip": "Dividir en subsistemas", "niv": 3},
        ]
    },
    {
        "id": 5,
        "nombre": "Dinámica",
        "descripcion": "Leyes de Newton, diagramas de cuerpo libre, rozamiento, movimiento circular, gravitación, resortes.",
        "ejercicios": [
            {"n": 1,  "desc": "Aplicar la Segunda Ley de Newton: calcular aceleración de un cuerpo", "tip": "a = F_neta / m", "niv": 1},
            {"n": 2,  "desc": "Calcular la fuerza neta sobre un objeto en reposo", "tip": "ΣF = 0", "niv": 1},
            {"n": 3,  "desc": "Determinar la masa de un objeto dada su aceleración y fuerza aplicada", "tip": "m = F/a", "niv": 1},
            {"n": 4,  "desc": "Calcular la fuerza de rozamiento cinético", "tip": "f = μ_c · N", "niv": 1},
            {"n": 5,  "desc": "Hallar la normal sobre un plano horizontal con rozamiento", "tip": "N = mg", "niv": 1},
            {"n": 6,  "desc": "Calcular la tensión de una cuerda en sistema Atwood simple", "tip": "T = 2m₁m₂g/(m₁+m₂)", "niv": 1},
            {"n": 7,  "desc": "Determinar la aceleración en plano inclinado sin rozamiento", "tip": "a = g·sen θ", "niv": 1},
            {"n": 8,  "desc": "Calcular la fuerza centrípeta en movimiento circular uniforme", "tip": "F_c = m·v²/r", "niv": 1},
            {"n": 9,  "desc": "Hallar la fuerza gravitacional entre dos masas", "tip": "F = G·m₁·m₂/r²", "niv": 1},
            {"n": 10, "desc": "Calcular la elongación de un resorte dada una fuerza (Ley de Hooke)", "tip": "F = k·x, despejar x", "niv": 1},
            {"n": 11, "desc": "Plano inclinado con rozamiento: calcular aceleración y normal", "tip": "Descomponer P en paralela y perpendicular al plano", "niv": 2},
            {"n": 12, "desc": "Sistema de dos bloques conectados por una cuerda en plano horizontal", "tip": "Tratar como sistema único, luego hallar T", "niv": 2},
            {"n": 13, "desc": "Determinar la velocidad máxima en una curva (con rozamiento como fuerza centrípeta)", "tip": "f_max = m·v²/r, despejar v", "niv": 2},
            {"n": 14, "desc": "Calcular el peso aparente en un ascensor en aceleración", "tip": "P_ap = m(g±a)", "niv": 2},
            {"n": 15, "desc": "Movimiento circular: calcular período para que un objeto no caiga de un tubo giratorio", "tip": "F_c = mg, despejar ω", "niv": 2},
            {"n": 16, "desc": "Determinar el coeficiente de rozamiento estático máximo en plano inclinado", "tip": "En el límite: f_e = μ_e·N = P·sen θ", "niv": 2},
            {"n": 17, "desc": "Sistema Atwood con masas diferentes: calcular aceleración y tensión", "tip": "a=(m₂−m₁)g/(m₁+m₂)", "niv": 2},
            {"n": 18, "desc": "Fuerza de resorte: sistema masa-resorte con bloque en plano inclinado", "tip": "Equilibrio: k·x = m·g·sen θ", "niv": 2},
            {"n": 19, "desc": "Calcular la velocidad orbital de un satélite a cierta altitud", "tip": "G·M·m/r² = m·v²/r, despejar v", "niv": 2},
            {"n": 20, "desc": "Determinar el período de un satélite usando la Tercera Ley de Kepler", "tip": "T² = (4π²/GM)·r³", "niv": 2},
            {"n": 21, "desc": "Bloque sobre plano inclinado con cuerda y polea: calcular aceleración del sistema", "tip": "Ecuaciones de Newton para cada masa por separado", "niv": 3},
            {"n": 22, "desc": "Calcular la fuerza para arrastrar un cajón con rozamiento estático y cinético", "tip": "Primero superar f_e, luego a = (F−f_c)/m", "niv": 3},
            {"n": 23, "desc": "Movimiento circular vertical: calcular velocidad mínima en la cima del lazo", "tip": "En la cima: N+mg = mv²/r, mínimo con N=0", "niv": 3},
            {"n": 24, "desc": "Sistema con tres bloques y dos cuerdas: calcular tensiones", "tip": "Tres ecuaciones de Newton independientes", "niv": 3},
            {"n": 25, "desc": "Calcular la aceleración de un bloque en plano inclinado con fuerza oblicua externa", "tip": "Descomponer la fuerza externa antes de aplicar Newton", "niv": 3},
            {"n": 26, "desc": "Determinar el radio mínimo de una curva para no derrapar a cierta velocidad", "tip": "r = v² / (μg)", "niv": 3},
            {"n": 27, "desc": "Analizar el movimiento de un objeto sobre plataforma giratoria", "tip": "f_max = μ·m·g ≥ m·ω²·r", "niv": 3},
            {"n": 28, "desc": "Sistema Atwood con plano inclinado en uno de los brazos", "tip": "Proyectar peso del bloque inclinado sobre el eje del movimiento", "niv": 3},
            {"n": 29, "desc": "Calcular la fuerza de contacto entre dos bloques apilados bajo aceleración", "tip": "Analizar bloque superior solo: F_contacto = m_sup·a", "niv": 3},
            {"n": 30, "desc": "Problema integrador: sistema con plano inclinado, rozamiento y resorte", "tip": "Combinar ley de Hooke y Newton en el mismo sistema", "niv": 3},
        ]
    },
    {
        "id": 6,
        "nombre": "Trabajo y energía",
        "descripcion": "Trabajo de una fuerza, energía cinética y potencial, conservación de energía mecánica, potencia, eficiencia.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular el trabajo de una fuerza paralela al desplazamiento", "tip": "W = F·d", "niv": 1},
            {"n": 2,  "desc": "Calcular trabajo de una fuerza en ángulo con el desplazamiento", "tip": "W = F·d·cos θ", "niv": 1},
            {"n": 3,  "desc": "Determinar la energía cinética de un objeto en movimiento", "tip": "Ec = ½m·v²", "niv": 1},
            {"n": 4,  "desc": "Calcular la energía potencial gravitatoria a cierta altura", "tip": "Ep = m·g·h", "niv": 1},
            {"n": 5,  "desc": "Aplicar el Teorema Trabajo-Energía para hallar velocidad final", "tip": "W_neto = ΔEc", "niv": 1},
            {"n": 6,  "desc": "Determinar el trabajo realizado por la gravedad en una caída", "tip": "W_g = m·g·h (siempre positivo en caída)", "niv": 1},
            {"n": 7,  "desc": "Calcular la potencia media de un motor", "tip": "P = W/t", "niv": 1},
            {"n": 8,  "desc": "Determinar el trabajo del rozamiento en un desplazamiento", "tip": "W_f = −f·d (siempre negativo)", "niv": 1},
            {"n": 9,  "desc": "Calcular la energía potencial elástica de un resorte comprimido", "tip": "Ep_e = ½k·x²", "niv": 1},
            {"n": 10, "desc": "Hallar la velocidad usando conservación de energía mecánica", "tip": "E_mec = Ec + Ep = cte (sin rozamiento)", "niv": 1},
            {"n": 11, "desc": "Calcular la velocidad al pie de una rampa usando conservación de energía", "tip": "mgh = ½mv², despejar v", "niv": 2},
            {"n": 12, "desc": "Determinar la altura máxima que alcanza un proyectil usando energía", "tip": "½mv² = mgh, despejar h", "niv": 2},
            {"n": 13, "desc": "Calcular el trabajo de la tensión en un péndulo", "tip": "W_T = 0 (fuerza ⊥ desplazamiento)", "niv": 2},
            {"n": 14, "desc": "Hallar la velocidad mínima para completar un lazo (usando energía)", "tip": "En la cima: Ec_min = ½m·(gr)", "niv": 2},
            {"n": 15, "desc": "Calcular la energía disipada por rozamiento en un plano inclinado", "tip": "W_f = E_mec_inicial − E_mec_final", "niv": 2},
            {"n": 16, "desc": "Calcular la potencia instantánea de un vehículo a cierta velocidad", "tip": "P = F·v", "niv": 2},
            {"n": 17, "desc": "Sistema resorte-masa: calcular velocidad en posición de equilibrio", "tip": "½kx² = ½mv²", "niv": 2},
            {"n": 18, "desc": "Determinar la eficiencia de una máquina comparando trabajo útil y total", "tip": "η = W_útil/W_total × 100%", "niv": 2},
            {"n": 19, "desc": "Calcular la velocidad de un bloque al final de una pista con rozamiento", "tip": "Ec_f = Ec_i + W_gravedad − W_rozamiento", "niv": 2},
            {"n": 20, "desc": "Calcular la compresión de un resorte al impacto de un proyectil", "tip": "½mv² = ½kx²", "niv": 2},
            {"n": 21, "desc": "Péndulo balístico: calcular velocidad de bala", "tip": "Dos etapas: inercia luego energía", "niv": 3},
            {"n": 22, "desc": "Analizar la energía en un montaña rusa con rozamiento en distintos puntos", "tip": "Aplicar balance energético tramo a tramo", "niv": 3},
            {"n": 23, "desc": "Calcular el trabajo de una fuerza variable (lineal) usando área bajo la curva", "tip": "W = área del triángulo en gráfica F-x", "niv": 3},
            {"n": 24, "desc": "Sistema con resorte y plano inclinado: hallar velocidad máxima", "tip": "Máxima v cuando a=0, es decir F_neta=0", "niv": 3},
            {"n": 25, "desc": "Calcular la potencia de una bomba que eleva líquido a cierta altura", "tip": "P = ρ·g·h·Q (Q = caudal en m³/s)", "niv": 3},
            {"n": 26, "desc": "Determinar la distancia de frenado en función de la velocidad inicial", "tip": "W_f = ½mv² → d = mv²/(2f)", "niv": 3},
            {"n": 27, "desc": "Analizar pérdida de energía en choque perfectamente inelástico", "tip": "ΔEc = ½(m₁m₂/(m₁+m₂))·(v₁−v₂)²", "niv": 3},
            {"n": 28, "desc": "Calcular la energía necesaria para poner en órbita un satélite", "tip": "E_orbital = −GMm/(2r)", "niv": 3},
            {"n": 29, "desc": "Problema de cuerpo que sube y baja por rampa con rozamiento diferente en cada tramo", "tip": "Rastrear la energía en cada segmento por separado", "niv": 3},
            {"n": 30, "desc": "Problema integrador: combinar trabajo, energía, potencia y rozamiento en sistema complejo", "tip": "Usar balance energético general: W_neto = ΔEc + ΔEp + E_disipada", "niv": 3},
        ]
    },
]

# ── SISTEMA DE PROMPT ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos un tutor experto en Física CBC-UBA. Tu rol es generar ejercicios de física con datos numéricos concretos y soluciones detalladas paso a paso, en formato pedagógico socrático.

REGLAS ESTRICTAS:
1. Cada ejercicio DEBE tener datos numéricos concretos inventados (coherentes y reales).
2. La solución debe tener entre 4 y 8 pasos claramente enumerados.
3. Cada paso incluye: la fórmula, la sustitución numérica, y el resultado parcial.
4. Usar notación científica correcta. Unidades siempre presentes.
5. El nivel de dificultad debe respetarse: básico (directo), intermedio (dos pasos), avanzado (varias etapas).
6. Responder SOLO con JSON válido, sin texto antes ni después, sin comillas invertidas.

FORMATO JSON de respuesta (un solo objeto):
{
  "id": "U{unidad_id}_E{numero}",
  "unidad": {unidad_id},
  "numero": {numero},
  "nivel": {1|2|3},
  "nivel_label": "Básico"|"Intermedio"|"Avanzado",
  "titulo": "Título corto del ejercicio",
  "enunciado": "Enunciado completo con todos los datos numéricos",
  "datos": {"clave": "valor con unidad", ...},
  "incognita": "Lo que se pide calcular",
  "pasos": [
    {"numero": 1, "titulo": "Identificar datos y fórmula", "desarrollo": "..."},
    {"numero": 2, "titulo": "Sustituir valores", "desarrollo": "..."},
    ...
  ],
  "resultado_final": "Valor numérico con unidades",
  "conclusion": "Interpretación física del resultado (1 oración)",
  "conceptos_clave": ["concepto1", "concepto2"]
}"""

# ── GENERADOR ─────────────────────────────────────────────────────────────────

def nivel_label(n):
    return {1: "Básico", 2: "Intermedio", 3: "Avanzado"}[n]


def generar_ejercicio(client, unidad, ejercicio, intento=1):
    """Llama a la API y devuelve el dict del ejercicio generado."""
    prompt = f"""Generá el ejercicio de Física CBC para:

Unidad {unidad['id']}: {unidad['nombre']}
Contexto temático: {unidad['descripcion']}

Ejercicio #{ejercicio['n']} — Nivel {ejercicio['niv']} ({nivel_label(ejercicio['niv'])})
Tema: {ejercicio['desc']}
Orientación pedagógica: {ejercicio['tip']}

Inventá datos numéricos realistas y generá la solución completa paso a paso en JSON."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    # Limpiar posibles backticks
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())


def cargar_existentes(output_path):
    """Carga el JSON acumulativo si ya existe."""
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {e["id"]: e for e in data.get("ejercicios", [])}
    return {}


def guardar(output_path, ejercicios_dict, meta):
    """Guarda el JSON acumulativo ordenado."""
    lista = sorted(ejercicios_dict.values(), key=lambda e: (e["unidad"], e["numero"]))
    output = {
        "meta": meta,
        "total": len(lista),
        "ejercicios": lista
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Agente FísicaCBC — generador de ejercicios")
    parser.add_argument("--unidad", type=int, default=None, help="Generar solo esta unidad (1-6)")
    parser.add_argument("--desde",  type=int, default=1,    help="Ejercicio inicial dentro de la unidad")
    parser.add_argument("--hasta",  type=int, default=30,   help="Ejercicio final dentro de la unidad")
    parser.add_argument("--dry-run", action="store_true",   help="Mostrar plan sin llamar a la API")
    parser.add_argument("--delay",  type=float, default=1.5, help="Segundos entre llamadas a la API")
    args = parser.parse_args()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "fisica_cbc_ejercicios.json"

    # Filtrar unidades y ejercicios
    unidades_a_procesar = [u for u in UNIDADES if args.unidad is None or u["id"] == args.unidad]
    if not unidades_a_procesar:
        print(f"[ERROR] Unidad {args.unidad} no encontrada.")
        return

    # Plan de ejecución
    plan = []
    for u in unidades_a_procesar:
        for e in u["ejercicios"]:
            if args.unidad is not None and not (args.desde <= e["n"] <= args.hasta):
                continue
            plan.append((u, e))

    total = len(plan)
    print(f"\n{'='*60}")
    print(f"  AGENTE FÍSICACBC — Generador de ejercicios")
    print(f"{'='*60}")
    print(f"  Ejercicios a generar : {total}")
    print(f"  Salida               : {output_path}")
    print(f"  Modelo               : claude-sonnet-4-6")
    print(f"  Delay entre llamadas : {args.delay}s")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("[DRY-RUN] Plan de ejecución:\n")
        for i, (u, e) in enumerate(plan, 1):
            print(f"  {i:3}. U{u['id']} E{e['n']:2} [{nivel_label(e['niv']):11}] {e['desc'][:60]}")
        print(f"\n[DRY-RUN] Total: {total} ejercicios. Sin llamadas a la API.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] Variable ANTHROPIC_API_KEY no encontrada.")
        print("  Ejecutá: $env:ANTHROPIC_API_KEY = 'tu-clave'")
        return

    client = anthropic.Anthropic(api_key=api_key)
    existentes = cargar_existentes(output_path)
    meta = {
        "plataforma": "FísicaCBC",
        "version": "1.0",
        "generado_por": "agente_fisica_cbc.py",
        "ultima_actualizacion": datetime.now().isoformat(),
        "total_unidades": 6,
        "ejercicios_por_unidad": 30
    }

    ok = 0
    errores = 0

    for i, (u, e) in enumerate(plan, 1):
        eid = f"U{u['id']}_E{e['n']}"
        if eid in existentes:
            print(f"  [{i:3}/{total}] {eid} — ya existe, omitido")
            continue

        print(f"  [{i:3}/{total}] Generando {eid} [{nivel_label(e['niv'])}] {e['desc'][:50]}...", end=" ", flush=True)

        for intento in range(1, 4):
            try:
                resultado = generar_ejercicio(client, u, e, intento)
                resultado["id"] = eid  # garantizar id correcto
                existentes[eid] = resultado
                guardar(output_path, existentes, meta)
                print(f"✓")
                ok += 1
                break
            except json.JSONDecodeError as ex:
                if intento < 3:
                    print(f"[JSON error, reintento {intento+1}]", end=" ", flush=True)
                    time.sleep(2)
                else:
                    print(f"✗ JSON inválido tras 3 intentos")
                    errores += 1
            except Exception as ex:
                if intento < 3:
                    print(f"[{ex}, reintento {intento+1}]", end=" ", flush=True)
                    time.sleep(3)
                else:
                    print(f"✗ Error: {ex}")
                    errores += 1

        time.sleep(args.delay)

    print(f"\n{'='*60}")
    print(f"  Completados : {ok}")
    print(f"  Errores     : {errores}")
    print(f"  Total en archivo: {len(existentes)}")
    print(f"  Archivo     : {output_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
