"""
agente_matematica_cbc.py
Agente generador de contenido para MatemáticaCBC.
Genera soluciones paso a paso en formato JSON para los 180 ejercicios del banco.
Uso: python agente_matematica_cbc.py
      python agente_matematica_cbc.py --unidad 1      (solo una unidad)
      python agente_matematica_cbc.py --desde 11 --hasta 20 --unidad 2  (rango)
      python agente_matematica_cbc.py --dry-run       (ver plan sin llamar a la API)
Requisito: variable de entorno ANTHROPIC_API_KEY
Salida:    outputs/matematica_cbc_ejercicios.json  (acumulativo)
"""

import anthropic
import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── BANCO DE EJERCICIOS ────────────────────────────────────────────────────────

UNIDADES = [
    {
        "id": 1,
        "nombre": "Números reales y álgebra",
        "descripcion": "Conjuntos numéricos, valor absoluto, desigualdades, factorización, ecuaciones e inecuaciones de 1° y 2°, sistemas de ecuaciones, polinomios, números complejos.",
        "ejercicios": [
            {"n": 1,  "desc": "Clasificar un número como natural, entero, racional o irracional", "tip": "Verificar si tiene representación decimal finita o periódica", "niv": 1},
            {"n": 2,  "desc": "Calcular el valor absoluto de una expresión numérica", "tip": "|a| = a si a≥0, -a si a<0", "niv": 1},
            {"n": 3,  "desc": "Resolver una ecuación lineal con una incógnita", "tip": "Despejar x aplicando operaciones inversas", "niv": 1},
            {"n": 4,  "desc": "Resolver una inecuación lineal y representar la solución en la recta", "tip": "Invertir el signo al multiplicar/dividir por negativo", "niv": 1},
            {"n": 5,  "desc": "Factorizar un trinomio cuadrado perfecto", "tip": "Reconocer a²+2ab+b² = (a+b)²", "niv": 1},
            {"n": 6,  "desc": "Aplicar la diferencia de cuadrados para factorizar", "tip": "a²-b² = (a+b)(a-b)", "niv": 1},
            {"n": 7,  "desc": "Resolver una ecuación cuadrática por fórmula resolvente", "tip": "x = (-b ± √(b²-4ac)) / 2a", "niv": 1},
            {"n": 8,  "desc": "Determinar el discriminante e interpretar la cantidad de raíces reales", "tip": "Δ>0: dos raíces, Δ=0: una raíz doble, Δ<0: sin raíces reales", "niv": 1},
            {"n": 9,  "desc": "Simplificar una expresión algebraica con fracciones", "tip": "Buscar denominador común y cancelar factores comunes", "niv": 1},
            {"n": 10, "desc": "Hallar el conjunto solución de una inecuación cuadrática", "tip": "Factorizar y analizar el signo en cada intervalo", "niv": 1},
            {"n": 11, "desc": "Resolver un sistema de dos ecuaciones lineales por sustitución", "tip": "Despejar una variable en una ecuación y sustituir en la otra", "niv": 2},
            {"n": 12, "desc": "Resolver un sistema de dos ecuaciones lineales por eliminación", "tip": "Multiplicar ecuaciones para igualar coeficientes y restar", "niv": 2},
            {"n": 13, "desc": "Resolver una inecuación con valor absoluto |ax+b| ≤ c", "tip": "-c ≤ ax+b ≤ c, resolver la inecuación doble", "niv": 2},
            {"n": 14, "desc": "Resolver una inecuación con valor absoluto |ax+b| > c", "tip": "ax+b > c  o  ax+b < -c (unión de soluciones)", "niv": 2},
            {"n": 15, "desc": "Dividir polinomios por el método de Ruffini", "tip": "Aplicar cuando el divisor es (x-a); usar el valor a como divisor de Ruffini", "niv": 2},
            {"n": 16, "desc": "Aplicar el Teorema del Resto para evaluar un polinomio en un punto", "tip": "p(a) = resto de dividir p(x) por (x-a)", "niv": 2},
            {"n": 17, "desc": "Hallar las raíces racionales de un polinomio usando el Teorema de las Raíces Racionales", "tip": "Candidatas: divisores del término independiente / divisores del coeficiente líder", "niv": 2},
            {"n": 18, "desc": "Resolver un sistema de ecuaciones no lineal (una lineal y una cuadrática)", "tip": "Despejar una variable de la lineal y sustituir en la cuadrática", "niv": 2},
            {"n": 19, "desc": "Operar números complejos: suma, diferencia y producto", "tip": "Usar i²=-1; separar parte real e imaginaria", "niv": 2},
            {"n": 20, "desc": "Calcular el módulo y el argumento de un número complejo", "tip": "|z| = √(a²+b²); θ = arctan(b/a) con ajuste de cuadrante", "niv": 2},
            {"n": 21, "desc": "Dividir números complejos usando el conjugado", "tip": "Multiplicar numerador y denominador por el conjugado del denominador", "niv": 3},
            {"n": 22, "desc": "Expresar un número complejo en forma polar y aplicar De Moivre", "tip": "z^n = r^n · (cos nθ + i·sen nθ)", "niv": 3},
            {"n": 23, "desc": "Resolver una ecuación cuadrática con discriminante negativo en ℂ", "tip": "√(-k) = i√k; las raíces son conjugadas", "niv": 3},
            {"n": 24, "desc": "Resolver una inecuación racional (cociente de polinomios)", "tip": "Llevar a la forma p(x)/q(x) > 0 y analizar signos en cada intervalo", "niv": 3},
            {"n": 25, "desc": "Factorizar un polinomio de grado 3 completamente sobre ℝ", "tip": "Encontrar una raíz racional, aplicar Ruffini y factorizar el cuadrático resultante", "niv": 3},
            {"n": 26, "desc": "Resolver un sistema de tres ecuaciones lineales con tres incógnitas", "tip": "Eliminación gaussiana: triangular el sistema y hacer back-substitution", "niv": 3},
            {"n": 27, "desc": "Calcular las raíces n-ésimas de un número complejo", "tip": "z_k = r^(1/n) · (cos((θ+2πk)/n) + i·sen((θ+2πk)/n)) para k=0,...,n-1", "niv": 3},
            {"n": 28, "desc": "Resolver una inecuación de grado 3 analizando signos", "tip": "Factorizar, identificar raíces y construir tabla de signos", "niv": 3},
            {"n": 29, "desc": "Demostrar la identidad algebraica de Euler para e^(iθ)", "tip": "Usar series de Taylor de e^x, cos x y sen x", "niv": 3},
            {"n": 30, "desc": "Problema integrador: sistema no lineal con inecuación y números complejos", "tip": "Combinar Ruffini, análisis de signos y forma polar de ℂ", "niv": 3},
        ]
    },
    {
        "id": 2,
        "nombre": "Funciones",
        "descripcion": "Concepto de función, dominio e imagen, función lineal, cuadrática, polinómica, racional, exponencial, logarítmica, módulo; composición, inversa, transformaciones.",
        "ejercicios": [
            {"n": 1,  "desc": "Determinar si una relación dada es función (criterio de la línea vertical)", "tip": "Verificar que a cada x le corresponde un único y", "niv": 1},
            {"n": 2,  "desc": "Calcular el dominio natural de una función polinómica", "tip": "Los polinomios tienen dominio ℝ", "niv": 1},
            {"n": 3,  "desc": "Calcular el dominio natural de una función racional", "tip": "Excluir los x que anulan el denominador", "niv": 1},
            {"n": 4,  "desc": "Calcular el dominio natural de una función con raíz cuadrada", "tip": "El radicando debe ser ≥ 0", "niv": 1},
            {"n": 5,  "desc": "Evaluar una función en puntos dados y calcular imagen", "tip": "Sustituir el valor de x en f(x)", "niv": 1},
            {"n": 6,  "desc": "Graficar una función lineal y determinar pendiente y ordenada al origen", "tip": "f(x) = mx + b; m = pendiente, b = corte con eje y", "niv": 1},
            {"n": 7,  "desc": "Determinar vértice, eje de simetría y raíces de una función cuadrática", "tip": "Vértice: x_v = -b/2a; completar cuadrados o fórmula", "niv": 1},
            {"n": 8,  "desc": "Determinar si una función es par, impar o ninguna", "tip": "Par: f(-x)=f(x); Impar: f(-x)=-f(x)", "niv": 1},
            {"n": 9,  "desc": "Calcular el dominio de una función logarítmica", "tip": "El argumento del logaritmo debe ser > 0", "niv": 1},
            {"n": 10, "desc": "Resolver una ecuación exponencial simple usando logaritmos", "tip": "a^x = b → x = log_a(b) = ln(b)/ln(a)", "niv": 1},
            {"n": 11, "desc": "Calcular la composición de dos funciones (f∘g)(x)", "tip": "(f∘g)(x) = f(g(x)); primero aplicar g, luego f", "niv": 2},
            {"n": 12, "desc": "Determinar el dominio de la función compuesta f∘g", "tip": "Dom(f∘g) = {x ∈ Dom(g) : g(x) ∈ Dom(f)}", "niv": 2},
            {"n": 13, "desc": "Hallar la función inversa de una función biyectiva", "tip": "Despejar x en y=f(x), luego intercambiar x e y", "niv": 2},
            {"n": 14, "desc": "Verificar que dos funciones son inversas entre sí", "tip": "f(g(x))=x y g(f(x))=x en sus dominios", "niv": 2},
            {"n": 15, "desc": "Analizar el dominio e imagen de una función racional simple", "tip": "Asíntota vertical donde denominador=0; asíntota horizontal para x→±∞", "niv": 2},
            {"n": 16, "desc": "Resolver una ecuación logarítmica aplicando propiedades de logaritmos", "tip": "log(a·b)=log a+log b; log(a/b)=log a-log b; log(a^n)=n·log a", "niv": 2},
            {"n": 17, "desc": "Graficar una función definida por partes e identificar continuidad", "tip": "Verificar que los valores en los puntos de corte coincidan", "niv": 2},
            {"n": 18, "desc": "Aplicar transformaciones: traslación, reflexión y escalado a f(x)", "tip": "f(x+a): traslación; f(-x): reflexión; cf(x): escalado vertical", "niv": 2},
            {"n": 19, "desc": "Determinar ceros, signo e intervalos de crecimiento de f(x) = |x²-4|", "tip": "Analizar dentro y fuera de las raíces de x²-4=0", "niv": 2},
            {"n": 20, "desc": "Resolver un sistema de ecuaciones usando funciones (intersección de gráficas)", "tip": "Igualar f(x)=g(x) y resolver", "niv": 2},
            {"n": 21, "desc": "Hallar dominio, imagen y asíntotas de una función racional de grado 2/2", "tip": "Asíntota horizontal: cociente de coeficientes líderes cuando grados iguales", "niv": 3},
            {"n": 22, "desc": "Componer tres funciones y determinar dominio resultante", "tip": "Calcular (f∘g∘h)(x) paso a paso filtrando dominios", "niv": 3},
            {"n": 23, "desc": "Encontrar la inversa de una función racional y verificar", "tip": "Despejar x, cuidar restricciones de dominio de la inversa", "niv": 3},
            {"n": 24, "desc": "Analizar el comportamiento de f(x) = a^x vs g(x) = log_a(x) como inversas", "tip": "Son simétricas respecto a y=x; verificar gráficamente", "niv": 3},
            {"n": 25, "desc": "Resolver una ecuación exponencial con bases distintas usando logaritmos", "tip": "Tomar logaritmo de ambos lados y usar propiedades", "niv": 3},
            {"n": 26, "desc": "Hallar parámetros de una función cuadrática dadas condiciones (vértice y punto)", "tip": "Forma vertex: f(x)=a(x-h)²+k; sustituir datos para hallar a", "niv": 3},
            {"n": 27, "desc": "Determinar la biyectividad de una función y restringir dominio si es necesario", "tip": "Inyectiva: línea horizontal corta gráfica a lo sumo una vez", "niv": 3},
            {"n": 28, "desc": "Analizar una función modular compleja: f(x) = |x²-x-6| + |x-3|", "tip": "Identificar raíces de cada expresión dentro del módulo y analizar por tramos", "niv": 3},
            {"n": 29, "desc": "Resolver una inecuación exponencial-logarítmica: a^f(x) > b^g(x)", "tip": "Tomar logaritmo, cuidar el sentido de la desigualdad según la base", "niv": 3},
            {"n": 30, "desc": "Problema integrador: composición, inversa y transformaciones sobre una función racional", "tip": "Encadenar los resultados de dominio, inversa y traslaciones", "niv": 3},
        ]
    },
    {
        "id": 3,
        "nombre": "Trigonometría",
        "descripcion": "Ángulos en radianes y grados, razones trigonométricas, valores exactos, identidades fundamentales, reducción, ángulos dobles y mitad, ecuaciones y sistemas trigonométricos, ley de senos y cosenos.",
        "ejercicios": [
            {"n": 1,  "desc": "Convertir grados a radianes y viceversa", "tip": "π rad = 180°; usar proporciones", "niv": 1},
            {"n": 2,  "desc": "Determinar el cuadrante de un ángulo y el signo de sus razones trigonométricas", "tip": "Regla CAST: C (IV cuad. cos>0), A (I todos>0), S (II sin>0), T (III tan>0)", "niv": 1},
            {"n": 3,  "desc": "Calcular sen, cos y tan de ángulos notables (30°, 45°, 60°, 90°)", "tip": "Memorizar triángulos de 30-60-90 y 45-45-90", "niv": 1},
            {"n": 4,  "desc": "Usar la identidad fundamental sen²θ + cos²θ = 1 para hallar una razón dado otra", "tip": "Si conocés sen θ, despejá cos θ = ±√(1−sen²θ) según cuadrante", "niv": 1},
            {"n": 5,  "desc": "Calcular las razones trigonométricas de un ángulo en posición estándar dado un punto del terminal", "tip": "r = √(x²+y²); sen=y/r, cos=x/r, tan=y/x", "niv": 1},
            {"n": 6,  "desc": "Aplicar reducción al primer cuadrante para ángulos obtusos", "tip": "Usar ángulos de referencia: π−θ, π+θ, 2π−θ", "niv": 1},
            {"n": 7,  "desc": "Verificar una identidad trigonométrica sencilla", "tip": "Trabajar sobre un solo lado, usar identidades básicas para transformar", "niv": 1},
            {"n": 8,  "desc": "Calcular el valor exacto de sen(15°) usando diferencia de ángulos", "tip": "sen(45°−30°) = sen45·cos30 − cos45·sen30", "niv": 1},
            {"n": 9,  "desc": "Resolver una ecuación trigonométrica simple: sen(x) = k", "tip": "x = arcsen(k) + 2πn  o  x = π−arcsen(k) + 2πn", "niv": 1},
            {"n": 10, "desc": "Calcular la longitud de arco y área de sector circular", "tip": "l = r·θ (θ en radianes); A = r²·θ/2", "niv": 1},
            {"n": 11, "desc": "Aplicar la fórmula del ángulo doble: sen(2θ) y cos(2θ)", "tip": "sen(2θ)=2senθcosθ; cos(2θ)=cos²θ−sen²θ", "niv": 2},
            {"n": 12, "desc": "Aplicar la fórmula del ángulo mitad para calcular sen(θ/2) y cos(θ/2)", "tip": "sen(θ/2)=±√((1−cosθ)/2); cos(θ/2)=±√((1+cosθ)/2)", "niv": 2},
            {"n": 13, "desc": "Simplificar una expresión usando identidades de producto a suma", "tip": "senA·cosB = ½[sen(A+B)+sen(A−B)]", "niv": 2},
            {"n": 14, "desc": "Resolver la ecuación: 2cos²x − cosx − 1 = 0 en [0, 2π]", "tip": "Factorizar como polinomio en cosx; resolver cada factor", "niv": 2},
            {"n": 15, "desc": "Resolver la ecuación: sen(2x) = cosx en [0, 2π]", "tip": "Usar sen(2x)=2senxcosx; factorizar cosx", "niv": 2},
            {"n": 16, "desc": "Aplicar la Ley de Senos para hallar un lado desconocido de un triángulo", "tip": "a/senA = b/senB = c/senC", "niv": 2},
            {"n": 17, "desc": "Aplicar la Ley de Cosenos para hallar un ángulo de un triángulo", "tip": "cos A = (b²+c²−a²) / (2bc)", "niv": 2},
            {"n": 18, "desc": "Verificar una identidad trigonométrica de nivel intermedio", "tip": "Expresar todo en términos de sen y cos; simplificar paso a paso", "niv": 2},
            {"n": 19, "desc": "Determinar amplitud, período, fase y desplazamiento de f(x)=A·sen(Bx+C)+D", "tip": "Amplitud=|A|, período=2π/|B|, fase=-C/B, desplazamiento vertical=D", "niv": 2},
            {"n": 20, "desc": "Calcular el área de un triángulo con dos lados y el ángulo comprendido", "tip": "A = ½·a·b·sen C", "niv": 2},
            {"n": 21, "desc": "Resolver una ecuación trigonométrica con ángulo compuesto: sen(2x+π/3) = √2/2", "tip": "Despejar 2x+π/3, luego despejar x; expresar todas las soluciones", "niv": 3},
            {"n": 22, "desc": "Resolver un sistema de ecuaciones trigonométricas", "tip": "Combinar identidades para reducir a una sola incógnita", "niv": 3},
            {"n": 23, "desc": "Demostrar la identidad: tan(A+B) = (tanA+tanB)/(1−tanA·tanB)", "tip": "Partir de sen(A+B)/cos(A+B) y dividir numerador y denominador por cosA·cosB", "niv": 3},
            {"n": 24, "desc": "Calcular el valor exacto de cos(75°) usando suma de ángulos y verificar con ángulo mitad", "tip": "cos(75°)=cos(45°+30°); también cos(75°)=cos(150°/2)", "niv": 3},
            {"n": 25, "desc": "Resolver en ℝ la ecuación: √3·senx + cosx = 1", "tip": "Escribir como R·sen(x+φ)=1; hallar R=√(a²+b²) y φ=arctan(b/a)", "niv": 3},
            {"n": 26, "desc": "Determinar los extremos de f(x)=a·senx + b·cosx", "tip": "f_max=√(a²+b²), f_min=−√(a²+b²)", "niv": 3},
            {"n": 27, "desc": "Aplicar la fórmula de Heron para calcular el área de un triángulo dados tres lados", "tip": "s=(a+b+c)/2; A=√(s(s-a)(s-b)(s-c))", "niv": 3},
            {"n": 28, "desc": "Resolver una inecuación trigonométrica: 2senx > 1 en [0, 2π]", "tip": "Hallar cuando senx > ½ y determinar los intervalos solución", "niv": 3},
            {"n": 29, "desc": "Problema con triángulo oblicuángulo: dos lados y ángulo opuesto (caso ambiguo)", "tip": "Verificar si hay 0, 1 o 2 triángulos posibles usando la Ley de Senos", "niv": 3},
            {"n": 30, "desc": "Problema integrador: identidades, ecuación y aplicación geométrica en un triángulo", "tip": "Encadenar ley de cosenos, identidades dobles y cálculo de área", "niv": 3},
        ]
    },
    {
        "id": 4,
        "nombre": "Límites y continuidad",
        "descripcion": "Límite de una función en un punto y en el infinito, operaciones con límites, límites laterales, indeterminaciones (0/0, ∞/∞, ∞−∞, 0·∞), límites notables, continuidad y clasificación de discontinuidades.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular un límite por sustitución directa en una función polinómica", "tip": "Si f es continua en a, entonces lím f(x) = f(a)", "niv": 1},
            {"n": 2,  "desc": "Calcular el límite de una función racional sin indeterminación", "tip": "Sustituir directamente si el denominador no se anula", "niv": 1},
            {"n": 3,  "desc": "Calcular el límite al infinito de una función polinómica", "tip": "Domina el término de mayor grado; analizar signo del coeficiente líder", "niv": 1},
            {"n": 4,  "desc": "Calcular el límite al infinito de una función racional", "tip": "Dividir numerador y denominador por la mayor potencia del denominador", "niv": 1},
            {"n": 5,  "desc": "Determinar límites laterales y concluir sobre la existencia del límite", "tip": "lím existe ↔ lím⁺ = lím⁻; si difieren, el límite no existe", "niv": 1},
            {"n": 6,  "desc": "Usar el Teorema del Sandwich para calcular un límite", "tip": "Si g(x)≤f(x)≤h(x) y lím g=lím h=L, entonces lím f=L", "niv": 1},
            {"n": 7,  "desc": "Aplicar el límite notable: lím(x→0) senx/x = 1", "tip": "Transformar la expresión para que aparezca la forma senθ/θ", "niv": 1},
            {"n": 8,  "desc": "Determinar la continuidad de una función en un punto dado", "tip": "Verificar: f(a) existe, lím f(x) existe, y lím f(x) = f(a)", "niv": 1},
            {"n": 9,  "desc": "Identificar y clasificar discontinuidades de una función racional", "tip": "Evitable si el factor se cancela; de salto si lím laterales difieren; esencial si algún lím es ±∞", "niv": 1},
            {"n": 10, "desc": "Calcular el límite de una función con raíz cuadrada por sustitución", "tip": "Verificar que el radicando sea no negativo en el límite", "niv": 1},
            {"n": 11, "desc": "Resolver la indeterminación 0/0 factorizando el numerador y denominador", "tip": "Cancelar el factor (x-a) común que causa la indeterminación", "niv": 2},
            {"n": 12, "desc": "Resolver la indeterminación 0/0 racionalizando con conjugado", "tip": "Multiplicar por conjugado de la expresión con raíz", "niv": 2},
            {"n": 13, "desc": "Resolver la indeterminación ∞/∞ en función racional de grado igual", "tip": "Dividir por x^n (mayor grado); resultado = cociente de coeficientes líderes", "niv": 2},
            {"n": 14, "desc": "Calcular el límite notable: lím(x→∞) (1+1/x)^x = e", "tip": "Reconocer la forma (1+a/x)^(bx) = e^(ab)", "niv": 2},
            {"n": 15, "desc": "Analizar la continuidad de una función definida por partes y determinar el valor del parámetro para que sea continua", "tip": "Igualar lím lateral derecho con lím lateral izquierdo en el punto de corte", "niv": 2},
            {"n": 16, "desc": "Calcular el límite de una función trigonométrica con indeterminación 0/0", "tip": "Usar lím(θ→0) senθ/θ = 1 y sus variantes", "niv": 2},
            {"n": 17, "desc": "Determinar las asíntotas verticales, horizontales y oblicuas de una función", "tip": "AV: denominador=0; AH: lím(x→±∞); AO: y=mx+b donde m=lím f(x)/x", "niv": 2},
            {"n": 18, "desc": "Resolver la indeterminación ∞−∞ factorizando o multiplicando por conjugado", "tip": "Buscar factor común o racionalizar para convertir en 0/0 tratable", "niv": 2},
            {"n": 19, "desc": "Aplicar el Teorema del Valor Intermedio para demostrar la existencia de una raíz", "tip": "Si f(a)·f(b)<0 y f es continua en [a,b], existe c con f(c)=0", "niv": 2},
            {"n": 20, "desc": "Calcular un límite usando la regla de L'Hôpital (nivel introductorio)", "tip": "Si 0/0 o ∞/∞: lím f/g = lím f'/g' (derivar numerador y denominador)", "niv": 2},
            {"n": 21, "desc": "Calcular el límite de la forma 0·∞ convirtiéndolo a 0/0 o ∞/∞", "tip": "Reescribir: f·g = f/(1/g) o g/(1/f) y aplicar L'Hôpital", "niv": 3},
            {"n": 22, "desc": "Calcular el límite de la forma 1^∞ usando logaritmos", "tip": "Sea L = lím f^g; calcular lím g·ln(f) = A; entonces L = e^A", "niv": 3},
            {"n": 23, "desc": "Calcular el límite de la forma 0^0 o ∞^0", "tip": "Tomar logaritmo, resolver el límite del exponente y exponenciar", "niv": 3},
            {"n": 24, "desc": "Demostrar la continuidad uniforme en un intervalo cerrado", "tip": "Toda función continua en [a,b] es uniformemente continua (Teorema de Heine)", "niv": 3},
            {"n": 25, "desc": "Calcular el límite de una sucesión recursiva usando punto fijo", "tip": "Si a_{n+1}=f(a_n) y lím a_n=L, entonces L=f(L)", "niv": 3},
            {"n": 26, "desc": "Analizar la continuidad de f(x)=x·sen(1/x) extendida en x=0", "tip": "Usar Sandwich: -|x| ≤ x·sen(1/x) ≤ |x|, lím = 0; definir f(0)=0", "niv": 3},
            {"n": 27, "desc": "Aplicar L'Hôpital múltiples veces para una indeterminación persistente", "tip": "Derivar repetidamente hasta eliminar la indeterminación; verificar la hipótesis antes de cada aplicación", "niv": 3},
            {"n": 28, "desc": "Determinar todos los puntos de discontinuidad de f(x)=sen(1/x) y clasificarlos", "tip": "En x=0 el lím no existe (oscilación): discontinuidad esencial", "niv": 3},
            {"n": 29, "desc": "Calcular el límite de una expresión que combina exponenciales y polinomios: lím(x→∞) x^n/e^x", "tip": "Aplicar L'Hôpital n veces; el exponencial siempre domina al polinomio", "niv": 3},
            {"n": 30, "desc": "Problema integrador: límites laterales, continuidad y clasificación de discontinuidades en una función compleja", "tip": "Analizar en cada punto crítico: existencia de f(a), lím laterales y su igualdad", "niv": 3},
        ]
    },
    {
        "id": 5,
        "nombre": "Derivadas",
        "descripcion": "Definición de derivada como límite, interpretación geométrica y física, reglas de derivación, regla de la cadena, derivada implícita, derivadas de orden superior, aplicaciones: monotonía, extremos, concavidad, puntos de inflexión, optimización, regla de L'Hôpital.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular la derivada de un polinomio usando la regla de la potencia", "tip": "d/dx[x^n] = n·x^(n-1)", "niv": 1},
            {"n": 2,  "desc": "Derivar una suma y diferencia de funciones elementales", "tip": "(f±g)' = f'±g'", "niv": 1},
            {"n": 3,  "desc": "Derivar la función exponencial y logarítmica natural", "tip": "(e^x)' = e^x; (ln x)' = 1/x", "niv": 1},
            {"n": 4,  "desc": "Derivar las funciones trigonométricas básicas: sen, cos, tan", "tip": "(sen x)' = cos x; (cos x)' = -sen x; (tan x)' = sec²x", "niv": 1},
            {"n": 5,  "desc": "Aplicar la regla del producto para derivar f(x)·g(x)", "tip": "(f·g)' = f'g + fg'", "niv": 1},
            {"n": 6,  "desc": "Aplicar la regla del cociente para derivar f(x)/g(x)", "tip": "(f/g)' = (f'g - fg') / g²", "niv": 1},
            {"n": 7,  "desc": "Hallar la ecuación de la recta tangente a una curva en un punto dado", "tip": "m = f'(x₀); y - y₀ = m(x - x₀)", "niv": 1},
            {"n": 8,  "desc": "Determinar en qué puntos la tangente es horizontal (f'(x)=0)", "tip": "Resolver f'(x)=0 y verificar el tipo de punto crítico", "niv": 1},
            {"n": 9,  "desc": "Calcular la derivada de una función exponencial base a: a^x", "tip": "(a^x)' = a^x · ln a", "niv": 1},
            {"n": 10, "desc": "Calcular la derivada de una función logarítmica base a: log_a(x)", "tip": "(log_a x)' = 1/(x·ln a)", "niv": 1},
            {"n": 11, "desc": "Aplicar la regla de la cadena para derivar f(g(x))", "tip": "(f∘g)'(x) = f'(g(x))·g'(x)", "niv": 2},
            {"n": 12, "desc": "Derivar una función compuesta con exponencial: e^(g(x))", "tip": "(e^(g(x)))' = e^(g(x)) · g'(x)", "niv": 2},
            {"n": 13, "desc": "Derivar una función compuesta con logaritmo: ln(g(x))", "tip": "(ln(g(x)))' = g'(x)/g(x)", "niv": 2},
            {"n": 14, "desc": "Calcular derivadas de orden superior (segunda y tercera derivada)", "tip": "Derivar sucesivamente; f''(x) = (f'(x))'", "niv": 2},
            {"n": 15, "desc": "Aplicar derivación implícita para hallar dy/dx", "tip": "Derivar ambos lados respecto a x; tratar y como y(x) y usar regla de la cadena", "niv": 2},
            {"n": 16, "desc": "Determinar los intervalos de crecimiento y decrecimiento usando f'(x)", "tip": "f'>0: creciente; f'<0: decreciente; cambio de signo en puntos críticos", "niv": 2},
            {"n": 17, "desc": "Clasificar máximos y mínimos locales usando el criterio de la segunda derivada", "tip": "f'(a)=0 y f''(a)<0: máximo; f''(a)>0: mínimo; f''(a)=0: indefinido", "niv": 2},
            {"n": 18, "desc": "Determinar concavidad y puntos de inflexión usando f''(x)", "tip": "f''>0: cóncava hacia arriba; f''<0: hacia abajo; PI donde f'' cambia de signo", "niv": 2},
            {"n": 19, "desc": "Problema de optimización: maximizar el área de un rectángulo inscrito en una circunferencia", "tip": "Expresar el área en una variable, derivar e igualar a cero", "niv": 2},
            {"n": 20, "desc": "Aplicar la regla de L'Hôpital para calcular un límite indeterminado", "tip": "lím f/g = lím f'/g' cuando la forma es 0/0 o ∞/∞", "niv": 2},
            {"n": 21, "desc": "Derivar una función de la forma f(x)^g(x) usando logaritmo", "tip": "y = f^g → ln y = g·ln f → derivar implícitamente", "niv": 3},
            {"n": 22, "desc": "Hallar la recta normal a una curva en un punto dado", "tip": "Pendiente normal = -1/f'(x₀)", "niv": 3},
            {"n": 23, "desc": "Realizar el estudio completo de una función racional (dominio, asíntotas, monotonía, extremos, concavidad)", "tip": "Combinar límites, f'=0, f''=0 y analizar signos en cada intervalo", "niv": 3},
            {"n": 24, "desc": "Problema de optimización: minimizar la distancia de un punto a una curva", "tip": "Minimizar d²=(x-a)²+(f(x)-b)²; derivar e igualar a cero", "niv": 3},
            {"n": 25, "desc": "Derivar implícitamente la circunferencia x²+y²=r² y hallar la tangente", "tip": "2x+2y·y'=0 → y'=-x/y; la recta tangente es perpendicular al radio", "niv": 3},
            {"n": 26, "desc": "Aplicar el Teorema de Rolle y el Teorema del Valor Medio", "tip": "Si f continua en [a,b] y derivable en (a,b) con f(a)=f(b): existe c con f'(c)=0 (Rolle)", "niv": 3},
            {"n": 27, "desc": "Problema de razones de cambio relacionadas: escalera resbalando", "tip": "Relacionar variables con la geometría, derivar respecto al tiempo", "niv": 3},
            {"n": 28, "desc": "Determinar la fórmula de Taylor de orden 2 de una función en un punto", "tip": "P₂(x) = f(a) + f'(a)(x-a) + f''(a)/2·(x-a)²", "niv": 3},
            {"n": 29, "desc": "Trazar el gráfico completo de f(x) = x·e^(-x) con todos los elementos del análisis", "tip": "Dom, ceros, asíntotas, f'=0 (extremos), f''=0 (inflexión), comportamiento", "niv": 3},
            {"n": 30, "desc": "Problema integrador: optimización con restricción, derivación implícita y L'Hôpital", "tip": "Usar multiplicadores de Lagrange o sustitución; verificar con derivada segunda", "niv": 3},
        ]
    },
    {
        "id": 6,
        "nombre": "Integrales",
        "descripcion": "Primitiva o antiderivada, integral indefinida, propiedades, métodos de integración (sustitución, por partes, fracciones simples), integral definida, Teorema Fundamental del Cálculo, cálculo de áreas y aplicaciones.",
        "ejercicios": [
            {"n": 1,  "desc": "Calcular la integral de un monomio usando la regla de la potencia", "tip": "∫x^n dx = x^(n+1)/(n+1) + C (n≠-1)", "niv": 1},
            {"n": 2,  "desc": "Calcular la integral de una suma de funciones elementales", "tip": "∫(f+g)dx = ∫f dx + ∫g dx; integrar término a término", "niv": 1},
            {"n": 3,  "desc": "Calcular ∫(1/x)dx y ∫e^x dx", "tip": "∫(1/x)dx = ln|x|+C; ∫e^x dx = e^x+C", "niv": 1},
            {"n": 4,  "desc": "Calcular integrales de funciones trigonométricas básicas", "tip": "∫sen x dx = -cos x+C; ∫cos x dx = sen x+C; ∫sec²x dx = tan x+C", "niv": 1},
            {"n": 5,  "desc": "Verificar una primitiva derivando el resultado", "tip": "F'(x) debe coincidir con f(x); usar las reglas de derivación", "niv": 1},
            {"n": 6,  "desc": "Calcular una integral definida simple usando el Teorema Fundamental del Cálculo", "tip": "∫[a,b] f(x)dx = F(b)-F(a) donde F'=f", "niv": 1},
            {"n": 7,  "desc": "Hallar la constante C de una primitiva dada una condición inicial", "tip": "Sustituir el punto (x₀, y₀) en F(x)+C para hallar C", "niv": 1},
            {"n": 8,  "desc": "Calcular el área bajo la curva de una función positiva en [a,b]", "tip": "A = ∫[a,b] f(x) dx (válido cuando f(x)≥0 en [a,b])", "niv": 1},
            {"n": 9,  "desc": "Aplicar la sustitución u=g(x) para calcular ∫f(g(x))·g'(x)dx", "tip": "Identificar u=g(x), du=g'(x)dx; transformar toda la integral a variable u", "niv": 1},
            {"n": 10, "desc": "Calcular una integral del tipo ∫x·e^(x²)dx por sustitución", "tip": "u=x², du=2x dx; ∫x·e^(x²)dx = ½∫e^u du = ½e^(x²)+C", "niv": 1},
            {"n": 11, "desc": "Aplicar integración por partes: ∫u dv = uv − ∫v du", "tip": "Orden ILATE para elegir u: Inversa trig, Logarítmica, Algebraica, Trigonométrica, Exponencial", "niv": 2},
            {"n": 12, "desc": "Calcular ∫x·senx dx por integración por partes", "tip": "u=x, dv=senx dx → du=dx, v=-cosx", "niv": 2},
            {"n": 13, "desc": "Calcular ∫ln(x)dx por integración por partes", "tip": "u=ln(x), dv=dx → du=1/x dx, v=x", "niv": 2},
            {"n": 14, "desc": "Calcular ∫e^x·cosx dx (requiere aplicar por partes dos veces)", "tip": "Aparece la integral original; despejarla del sistema de ecuaciones", "niv": 2},
            {"n": 15, "desc": "Descomponer una fracción racional en fracciones parciales (factores lineales distintos)", "tip": "p(x)/((x-a)(x-b)) = A/(x-a) + B/(x-b); hallar A y B", "niv": 2},
            {"n": 16, "desc": "Integrar usando fracciones parciales con factor lineal repetido", "tip": "1/(x-a)^2 → A/(x-a) + B/(x-a)²", "niv": 2},
            {"n": 17, "desc": "Calcular el área entre dos curvas: ∫[a,b] |f(x)-g(x)| dx", "tip": "Determinar cuál función es mayor en cada subintervalo; sumar las áreas", "niv": 2},
            {"n": 18, "desc": "Calcular la integral definida con sustitución y cambiar los límites", "tip": "Si u=g(x): cuando x=a → u=g(a); cuando x=b → u=g(b)", "niv": 2},
            {"n": 19, "desc": "Calcular ∫tan(x)dx y ∫cot(x)dx", "tip": "∫tan x dx = -ln|cos x|+C; ∫cot x dx = ln|sen x|+C", "niv": 2},
            {"n": 20, "desc": "Aplicar sustitución trigonométrica para ∫√(a²-x²)dx", "tip": "x = a·senθ; dx = a·cosθ dθ; √(a²-x²) = a·cosθ", "niv": 2},
            {"n": 21, "desc": "Calcular una integral impropia convergente: ∫[1,∞) 1/x² dx", "tip": "lím[b→∞] ∫[1,b] x^(-2) dx = lím[b→∞] [-1/x]₁ᵇ = 1", "niv": 3},
            {"n": 22, "desc": "Determinar la convergencia de una integral impropia y calcularla si converge", "tip": "∫[0,1] x^(-p) dx converge si p<1; ∫[1,∞) x^(-p) dx converge si p>1", "niv": 3},
            {"n": 23, "desc": "Calcular el volumen de revolución usando el método del disco: V=π∫[a,b][f(x)]²dx", "tip": "Girar el área bajo f(x) alrededor del eje x", "niv": 3},
            {"n": 24, "desc": "Calcular el volumen de revolución usando el método de la cáscara cilíndrica", "tip": "V = 2π∫[a,b] x·f(x) dx (girar alrededor del eje y)", "niv": 3},
            {"n": 25, "desc": "Integrar fracción racional con factor cuadrático irreducible en el denominador", "tip": "x²+bx+c irreducible: completar cuadrado y usar arctan", "niv": 3},
            {"n": 26, "desc": "Calcular la longitud de arco de una curva: L=∫[a,b]√(1+[f'(x)]²)dx", "tip": "Derivar f, elevar al cuadrado, sumar 1 y calcular la integral", "niv": 3},
            {"n": 27, "desc": "Aplicar la Regla de Simpson para aproximar una integral definida", "tip": "S = (h/3)[f(x₀)+4f(x₁)+2f(x₂)+...+4f(x_{n-1})+f(x_n)]; h=(b-a)/n", "niv": 3},
            {"n": 28, "desc": "Resolver una ecuación diferencial separable usando integración", "tip": "Separar variables: f(y)dy=g(x)dx; integrar ambos lados", "niv": 3},
            {"n": 29, "desc": "Calcular el área de una región acotada por tres curvas", "tip": "Encontrar intersecciones, dividir en subregiones y sumar integrales", "niv": 3},
            {"n": 30, "desc": "Problema integrador: integral impropia, por partes y fracciones parciales combinados", "tip": "Descomponer en fracciones, integrar por partes cuando haya ln o arctan, analizar convergencia", "niv": 3},
        ]
    },
]

# ── SISTEMA DE PROMPT ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos un tutor experto en Matemática CBC-UBA. Tu rol es generar ejercicios de matemática con datos concretos y soluciones detalladas paso a paso, en formato pedagógico socrático.

REGLAS ESTRICTAS:
1. Cada ejercicio DEBE tener datos concretos (funciones específicas, valores numéricos, parámetros definidos).
2. La solución debe tener entre 4 y 8 pasos claramente enumerados.
3. Cada paso incluye: la propiedad o fórmula aplicada, el desarrollo algebraico y el resultado parcial.
4. Usar notación matemática correcta. Si hay fracciones, raíces o exponentes, mostrarlos claramente en texto.
5. El nivel de dificultad debe respetarse: básico (directo), intermedio (dos o tres pasos), avanzado (varias etapas con justificación).
6. Responder SOLO con JSON válido, sin texto antes ni después, sin comillas invertidas.

FORMATO JSON de respuesta (un solo objeto):
{
  "id": "U{unidad_id}_E{numero}",
  "unidad": {unidad_id},
  "numero": {numero},
  "nivel": {1|2|3},
  "nivel_label": "Básico"|"Intermedio"|"Avanzado",
  "titulo": "Título corto del ejercicio",
  "enunciado": "Enunciado completo con la función o expresión concreta a trabajar",
  "datos": {"clave": "valor o expresión", ...},
  "incognita": "Lo que se pide calcular o demostrar",
  "pasos": [
    {"numero": 1, "titulo": "Identificar la estrategia y fórmula", "desarrollo": "..."},
    {"numero": 2, "titulo": "Desarrollo algebraico", "desarrollo": "..."},
    ...
  ],
  "resultado_final": "Respuesta completa con notación correcta",
  "conclusion": "Interpretación matemática del resultado (1 oración)",
  "conceptos_clave": ["concepto1", "concepto2"]
}"""

# ── GENERADOR ─────────────────────────────────────────────────────────────────

def nivel_label(n):
    return {1: "Básico", 2: "Intermedio", 3: "Avanzado"}[n]


def generar_ejercicio(client, unidad, ejercicio):
    prompt = f"""Generá el ejercicio de Matemática CBC para:

Unidad {unidad['id']}: {unidad['nombre']}
Contexto temático: {unidad['descripcion']}

Ejercicio #{ejercicio['n']} — Nivel {ejercicio['niv']} ({nivel_label(ejercicio['niv'])})
Tema: {ejercicio['desc']}
Orientación pedagógica: {ejercicio['tip']}

Inventá una función o expresión concreta realista y generá la solución completa paso a paso en JSON."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())


def cargar_existentes(output_path):
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {e["id"]: e for e in data.get("ejercicios", [])}
    return {}


def guardar(output_path, ejercicios_dict, meta):
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
    parser = argparse.ArgumentParser(description="Agente MatemáticaCBC — generador de ejercicios")
    parser.add_argument("--unidad", type=int, default=None, help="Generar solo esta unidad (1-6)")
    parser.add_argument("--desde",  type=int, default=1,    help="Ejercicio inicial dentro de la unidad")
    parser.add_argument("--hasta",  type=int, default=30,   help="Ejercicio final dentro de la unidad")
    parser.add_argument("--dry-run", action="store_true",   help="Mostrar plan sin llamar a la API")
    parser.add_argument("--delay",  type=float, default=1.5, help="Segundos entre llamadas a la API")
    args = parser.parse_args()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "matematica_cbc_ejercicios.json"

    unidades_a_procesar = [u for u in UNIDADES if args.unidad is None or u["id"] == args.unidad]
    if not unidades_a_procesar:
        print(f"[ERROR] Unidad {args.unidad} no encontrada.")
        return

    plan = []
    for u in unidades_a_procesar:
        for e in u["ejercicios"]:
            if args.unidad is not None and not (args.desde <= e["n"] <= args.hasta):
                continue
            plan.append((u, e))

    total = len(plan)
    print(f"\n{'='*60}")
    print(f"  AGENTE MATEMÁTICACBC — Generador de ejercicios")
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
        print("  En bash: export ANTHROPIC_API_KEY='tu-clave'")
        return

    client = anthropic.Anthropic(api_key=api_key)
    existentes = cargar_existentes(output_path)
    meta = {
        "plataforma": "MatemáticaCBC",
        "version": "1.0",
        "generado_por": "agente_matematica_cbc.py",
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
                resultado = generar_ejercicio(client, u, e)
                resultado["id"] = eid
                existentes[eid] = resultado
                guardar(output_path, existentes, meta)
                print("✓")
                ok += 1
                break
            except json.JSONDecodeError:
                if intento < 3:
                    print(f"[JSON error, reintento {intento+1}]", end=" ", flush=True)
                    time.sleep(2)
                else:
                    print("✗ JSON inválido tras 3 intentos")
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
