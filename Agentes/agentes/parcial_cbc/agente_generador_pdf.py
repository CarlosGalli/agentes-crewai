"""
Agente 3 — Generador PDF
Recibe el JSON del resolvedor y produce el PDF final con ReportLab + Matplotlib.
Motor gráfico y de estilos extraído del script del parcial 1er cuatrimestre 2025.
"""

import json
import sys
import io
import numpy as np
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak, KeepTogether)
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── fuentes ───────────────────────────────────────────────────────────────────
import sys as _sys
if _sys.platform == "win32":
    FONT_PATH = "C:/Windows/Fonts/"
else:
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/"

def registrar_fuentes():
    pdfmetrics.registerFont(TTFont('DVMono',      FONT_PATH + 'DejaVuSansMono.ttf'))
    pdfmetrics.registerFont(TTFont('DVMono-Bold', FONT_PATH + 'DejaVuSansMono-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('DVSans',      FONT_PATH + 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DVSans-Bold', FONT_PATH + 'DejaVuSans-Bold.ttf'))

# ── colores ───────────────────────────────────────────────────────────────────
C_PURPLE   = colors.HexColor('#534AB7')
C_GREEN    = colors.HexColor('#1D9E75')
C_ORANGE   = colors.HexColor('#D85A30')
C_BLUE_LT  = colors.HexColor('#E6F1FB')
C_GREEN_LT = colors.HexColor('#EAF3DE')
C_GRAY     = colors.HexColor('#888780')
C_DARK     = colors.HexColor('#2C2C2A')
C_BG_STEP  = colors.HexColor('#F8F8F6')
C_BLUE_INF = colors.HexColor('#185FA5')
C_TEAL     = colors.HexColor('#0F6E56')

# ── estilos ───────────────────────────────────────────────────────────────────
def estilos():
    return dict(
        titulo    = ParagraphStyle('titulo',
            fontName='Helvetica-Bold', fontSize=16, textColor=C_DARK,
            spaceAfter=2, leading=20),
        subtitulo = ParagraphStyle('subtitulo',
            fontName='DVSans-Bold', fontSize=12, textColor=C_PURPLE,
            spaceAfter=4, spaceBefore=6, leading=16),
        enunciado = ParagraphStyle('enunciado',
            fontName='DVSans', fontSize=10.5, textColor=C_DARK,
            spaceAfter=0, leading=15,
            borderPadding=(6,8,6,8), backColor=C_BLUE_LT, borderRadius=4),
        idea      = ParagraphStyle('idea',
            fontName='DVSans', fontSize=9.5, textColor=C_BLUE_INF,
            backColor=C_BLUE_LT, borderPadding=(5,8,5,8), borderRadius=4,
            leading=14, spaceAfter=0),
        result    = ParagraphStyle('result',
            fontName='DVSans-Bold', fontSize=11, textColor=C_TEAL,
            backColor=C_GREEN_LT, borderPadding=(8,12,8,12), borderRadius=4,
            alignment=TA_CENTER, leading=16, spaceAfter=8),
        lbl       = ParagraphStyle('lbl',
            fontName='DVSans-Bold', fontSize=8, textColor=C_GRAY, leading=11),
        mono      = ParagraphStyle('mono',
            fontName='DVMono', fontSize=10, textColor=C_DARK, leading=13),
        mono_g    = ParagraphStyle('mono_g',
            fontName='DVMono-Bold', fontSize=10, textColor=C_GREEN, leading=13),
        mono_b    = ParagraphStyle('mono_b',
            fontName='DVMono', fontSize=10, textColor=C_BLUE_INF, leading=13),
    )

# ── MplFigure flowable ────────────────────────────────────────────────────────
class MplFigure(Flowable):
    def __init__(self, fig, width_cm=14, height_cm=9):
        Flowable.__init__(self)
        self.width  = width_cm * cm
        self.height = height_cm * cm
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        buf.seek(0)
        self._data = buf.read()

    def draw(self):
        from reportlab.lib.utils import ImageReader
        self.canv.drawImage(ImageReader(io.BytesIO(self._data)),
                            0, 0, self.width, self.height,
                            preserveAspectRatio=True, anchor='sw')

# ── paso_box ──────────────────────────────────────────────────────────────────
def paso_box(label: str, rows: list, st: dict, bg=C_BG_STEP):
    """rows: [{"label": str, "contenido": str, "color": "green|blue|"}]"""
    tdata = []
    for row in rows:
        hi  = row.get("color", "")
        sty = st['mono_g'] if hi == 'green' else \
              st['mono_b'] if hi == 'blue'  else st['mono']
        tdata.append([
            Paragraph(row.get("label", ""), st['lbl']),
            Paragraph(row.get("contenido", ""), sty)
        ])
    t = Table(tdata, colWidths=[3.2*cm, 12.8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), bg),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
    ]))
    lpar = Paragraph(label, ParagraphStyle('_sl', fontName='DVSans-Bold',
                     fontSize=8, textColor=C_GRAY, leading=11, spaceAfter=2))
    return KeepTogether([lpar, t, Spacer(1, 8)])

# ── generador de gráfico desde JSON ──────────────────────────────────────────
def generar_grafico(grafico: dict):
    """
    Recibe el dict 'grafico' del JSON del resolvedor y devuelve una figura matplotlib.
    Soporta tipos: funcion, ceros_signo, homografica, trigonometrica, circulo_trig.
    """
    tipo = grafico.get("tipo", "funcion")
    funciones = grafico.get("funciones", [])
    puntos = grafico.get("puntos_destacados", [])
    asintotas = grafico.get("asintotas", [])
    xlim = grafico.get("xlim", [-10, 10])
    ylim = grafico.get("ylim", [-10, 10])
    titulo = grafico.get("titulo_grafico", "")

    if tipo == "circulo_trig":
        return _grafico_circulo_trig(grafico)

    if tipo == "ceros_signo":
        return _grafico_ceros_signo(grafico)

    # Para función, homográfica, trigonométrica: plot estándar
    fig, ax = plt.subplots(figsize=(8, 5.5))
    fig.patch.set_facecolor('white')

    x = np.linspace(xlim[0], xlim[1], 800)

    for fn in funciones:
        expr = fn.get("expresion_python", "")
        color = fn.get("color", "#534AB7")
        label = fn.get("label", fn.get("nombre", ""))
        try:
            # Dividir en ramas si hay asíntota vertical
            av_vals = [a["valor"] for a in asintotas if a.get("tipo") == "v"]
            if av_vals:
                # Trazar por tramos evitando las asíntotas verticales
                rangos = []
                prev = xlim[0]
                for av in sorted(av_vals):
                    rangos.append((prev, av - 0.05))
                    prev = av + 0.05
                rangos.append((prev, xlim[1]))
                for i, (x0, x1) in enumerate(rangos):
                    xr = np.linspace(x0, x1, 400)
                    yr = eval(expr, {"np": np, "x": xr})
                    ax.plot(xr, yr, color=color, lw=2,
                            label=label if i == 0 else "")
            else:
                y = eval(expr, {"np": np, "x": x})
                ax.plot(x, y, color=color, lw=2, label=label)
        except Exception as e:
            print(f"  [Graf] Error evaluando '{expr}': {e}")

    # Asíntotas
    for a in asintotas:
        val   = a.get("valor", 0)
        acol  = a.get("color", "#E24B4A")
        albl  = a.get("label", "")
        if a.get("tipo") == "v":
            ax.axvline(val, color=acol, lw=1.5, linestyle='--', label=albl)
        elif a.get("tipo") == "h":
            ax.axhline(val, color=acol, lw=1.5, linestyle='--', label=albl)

    # Puntos destacados
    for p in puntos:
        ax.scatter([p["x"]], [p["y"]], color=p.get("color","#D85A30"),
                   zorder=5, s=65)
        lbl_txt = p.get("label", "")
        if lbl_txt:
            ax.annotate(lbl_txt, xy=(p["x"], p["y"]),
                        xytext=(p["x"] + (xlim[1]-xlim[0])*0.03,
                                p["y"] + (ylim[1]-ylim[0])*0.04),
                        fontsize=9, color=p.get("color","#D85A30"),
                        arrowprops=dict(arrowstyle='->', lw=0.8,
                                        color=p.get("color","#D85A30")))

    ax.axhline(0, color='#888780', lw=0.7)
    ax.axvline(0, color='#888780', lw=0.7)
    ax.set_xlim(xlim); ax.set_ylim(ylim)
    ax.set_xlabel('x', fontsize=10); ax.set_ylabel('y', fontsize=10)
    if any(fn.get("label") for fn in funciones) or asintotas:
        ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.set_title(titulo, fontsize=11, color='#2C2C2A', pad=6)
    fig.tight_layout()
    return fig


def _grafico_circulo_trig(grafico: dict):
    """Gráfico de círculo trigonométrico para ejercicios de ecuaciones trig."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.patch.set_facecolor('white')

    funciones = grafico.get("funciones", [])
    puntos    = grafico.get("puntos_destacados", [])
    xlim      = grafico.get("xlim", [-np.pi, np.pi])
    ylim      = grafico.get("ylim", [-15, 15])
    titulo    = grafico.get("titulo_grafico", "")
    extras    = grafico.get("extras", {})

    # Izq: función
    x = np.linspace(xlim[0], xlim[1], 600)
    for fn in funciones:
        try:
            y = eval(fn["expresion_python"], {"np": np, "x": x})
            ax1.plot(x, y, color=fn.get("color","#534AB7"), lw=2,
                     label=fn.get("label",""))
        except Exception as e:
            print(f"  [Graf trig] Error: {e}")

    for p in puntos:
        ax1.scatter([p["x"]], [p["y"]], color=p.get("color","#D85A30"), zorder=5, s=65)
        if p.get("label"):
            ax1.annotate(p["label"], xy=(p["x"],p["y"]),
                         xytext=(p["x"]+0.15, p["y"]+1.5), fontsize=9,
                         color=p.get("color","#D85A30"),
                         arrowprops=dict(arrowstyle='->', lw=0.8,
                                         color=p.get("color","#D85A30")))

    ax1.axhline(0, color='#888780', lw=0.7)
    ax1.axvline(0, color='#888780', lw=0.7)

    # Marcas en eje x con fracciones de pi
    ticks_raw = extras.get("xticks", [-np.pi, -np.pi/2, 0, np.pi/6,
                                       np.pi/2, 5*np.pi/6, np.pi])
    labels_x  = extras.get("xlabels", ['-π', '-π/2', '0', 'π/6', 'π/2', '5π/6', 'π'])
    ax1.set_xticks(ticks_raw)
    ax1.set_xticklabels(labels_x, fontsize=9)
    ax1.set_xlim(xlim); ax1.set_ylim(ylim)
    ax1.set_xlabel('x', fontsize=10); ax1.set_ylabel('f(x)', fontsize=10)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.2, linestyle='--')
    ax1.set_title(titulo, fontsize=11, color='#2C2C2A', pad=6)

    # Der: círculo trigonométrico
    theta = np.linspace(0, 2*np.pi, 400)
    ax2.plot(np.cos(theta), np.sin(theta), color='#888780', lw=1.2)
    ax2.axhline(0, color='#888780', lw=0.6)
    ax2.axvline(0, color='#888780', lw=0.6)

    # Línea horizontal sen = valor
    sen_val = extras.get("sen_valor", None)
    if sen_val is not None:
        ax2.axhline(sen_val, color='#1D9E75', lw=1.2, linestyle='--',
                    label=f'sen(x) = {sen_val}')

    # Puntos solución en el círculo
    for p in puntos:
        angle = p["x"]
        cx, cy = np.cos(angle), np.sin(angle)
        ax2.scatter([cx], [cy], color=p.get("color","#D85A30"), zorder=5, s=65)
        ax2.plot([0, cx], [0, cy], color='#534AB7', lw=1.2, alpha=0.7)
        ax2.plot([cx, cx], [0, cy], color='#1D9E75', lw=0.8, linestyle=':', alpha=0.7)
        if p.get("label"):
            ax2.annotate(p["label"], xy=(cx, cy),
                         xytext=(cx + 0.12, cy + 0.1), fontsize=8.5,
                         color=p.get("color","#D85A30"),
                         arrowprops=dict(arrowstyle='->', lw=0.7,
                                         color=p.get("color","#D85A30")))

    ax2.set_xlim(-1.5, 1.5); ax2.set_ylim(-1.4, 1.4)
    ax2.set_aspect('equal')
    ax2.legend(fontsize=9, loc='lower right')
    ax2.grid(True, alpha=0.15, linestyle='--')
    ax2.set_title('Círculo trigonométrico', fontsize=11, color='#2C2C2A', pad=6)
    fig.tight_layout(pad=2)
    return fig


def _grafico_ceros_signo(grafico: dict):
    """Gráfico doble: función + línea de signos."""
    funciones = grafico.get("funciones", [])
    puntos    = grafico.get("puntos_destacados", [])
    xlim      = grafico.get("xlim", [-3, 16])
    ylim      = grafico.get("ylim", [-200, 200])
    titulo    = grafico.get("titulo_grafico", "")
    extras    = grafico.get("extras", {})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('white')

    x = np.linspace(xlim[0], xlim[1], 600)
    for fn in funciones:
        try:
            y = eval(fn["expresion_python"], {"np": np, "x": x})
            ax1.plot(x, y, color=fn.get("color","#534AB7"), lw=2,
                     label=fn.get("label",""))
            ax1.fill_between(x, y, 0, where=(y >= 0), alpha=0.15,
                             color='#1D9E75', label='C⁺')
        except Exception as e:
            print(f"  [Graf signo] Error: {e}")

    for p in puntos:
        ax1.scatter([p["x"]], [p["y"]], color=p.get("color","#D85A30"), zorder=5, s=65)
        if p.get("label"):
            ax1.annotate(p["label"], xy=(p["x"],p["y"]),
                         xytext=(p["x"]+0.3, (ylim[1]-ylim[0])*0.12+ylim[0]),
                         fontsize=8, color=p.get("color","#D85A30"),
                         arrowprops=dict(arrowstyle='->', lw=0.7,
                                         color=p.get("color","#D85A30")))

    ax1.axhline(0, color='#888780', lw=0.7)
    ax1.axvline(0, color='#888780', lw=0.7)
    ax1.set_xlim(xlim); ax1.set_ylim(ylim)
    ax1.set_xlabel('x', fontsize=10); ax1.set_ylabel('y', fontsize=10)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.2, linestyle='--')
    ax1.set_title(titulo, fontsize=11, color='#2C2C2A', pad=6)

    # Línea de signos
    ax2.set_xlim(xlim[0]-1, xlim[1]+1); ax2.set_ylim(-1, 4)
    ax2.axhline(2, color='#444441', lw=1.5)
    ax2.set_axis_off()

    zeros_x = [p["x"] for p in puntos]
    for z in zeros_x:
        ax2.plot(z, 2, 'o', color='white', markeredgecolor='#2C2C2A',
                 markersize=9, markeredgewidth=1.5, zorder=5)
        ax2.text(z, 1.5, str(int(z)) if z == int(z) else str(z),
                 ha='center', va='top', fontsize=10, fontweight='bold', color='#2C2C2A')

    intervalos = extras.get("intervalos_signo", [])
    for seg in intervalos:
        x1, x2 = seg["x1"], seg["x2"]
        sg  = seg.get("signo", "+")
        col = '#1D9E75' if sg == '+' else '#E24B4A'
        mid = (x1 + x2) / 2
        ax2.barh(2, x2-x1, left=x1, height=0.15, color=col, alpha=0.3, zorder=3)
        ax2.text(mid, 2.55, sg, ha='center', va='bottom',
                 fontsize=18, fontweight='bold', color=col)
        pt_label = seg.get("punto_prueba_label", "")
        if pt_label:
            ax2.text(mid, 3.1, pt_label, ha='center', va='bottom',
                     fontsize=7.5, color='#5F5E5A')

    ax2.annotate('', xy=(xlim[1]+1.5, 2), xytext=(xlim[1]+0.8, 2),
                 arrowprops=dict(arrowstyle='->', color='#444441', lw=1.5))
    ax2.text(xlim[1]+1.6, 2, 'x', va='center', fontsize=10, color='#2C2C2A')
    ax2.set_title('Línea de signos', fontsize=11, color='#2C2C2A', pad=6)

    fig.tight_layout(pad=2)
    return fig


# ── generador principal del PDF ───────────────────────────────────────────────
def generar_pdf(datos_resolvedor: dict, ruta_salida: str,
                imagen_enunciado: str = None, verbose: bool = False):
    """
    datos_resolvedor: dict con metadata + lista 'resoluciones'
    ruta_salida:      path del PDF a generar
    imagen_enunciado: path opcional a foto/imagen del enunciado original
    """
    registrar_fuentes()
    st = estilos()

    doc = SimpleDocTemplate(ruta_salida, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm,  bottomMargin=2*cm)
    story = []

    def hr(color=C_PURPLE, after=8):
        return [HRFlowable(width='100%', thickness=0.5, color=color, spaceAfter=after)]

    # ── Encabezado ────────────────────────────────────────────────────────
    materia     = datos_resolvedor.get("materia", "Matemática CBC")
    parcial     = datos_resolvedor.get("parcial", "")
    cuatri      = datos_resolvedor.get("cuatrimestre", "")
    tema        = datos_resolvedor.get("tema", "")
    subtitulo_h = " · ".join(filter(None, [parcial, cuatri, tema]))

    story.append(Paragraph(materia.upper(), ParagraphStyle('_h0',
        fontName='Helvetica-Bold', fontSize=18, textColor=C_PURPLE,
        alignment=TA_CENTER, spaceAfter=2)))
    if subtitulo_h:
        story.append(Paragraph(subtitulo_h, ParagraphStyle('_h1',
            fontName='Helvetica', fontSize=11, textColor=C_GRAY,
            alignment=TA_CENTER, spaceAfter=10)))
    story.extend(hr(C_PURPLE, 10))

    # ── Imagen del enunciado original (opcional) ──────────────────────────
    if imagen_enunciado and Path(imagen_enunciado).exists():
        from PIL import Image as PILImage
        from reportlab.platypus import Image as RLImage
        with PILImage.open(imagen_enunciado) as im:
            iw, ih = im.size
        img_w = 17 * cm
        img_h = img_w * (ih / iw)
        story.append(Spacer(1, 10))
        story.append(Paragraph("Enunciado original", ParagraphStyle('_enlbl',
            fontName='Helvetica-Bold', fontSize=9, textColor=C_GRAY,
            spaceAfter=6)))
        story.append(RLImage(imagen_enunciado, width=img_w, height=img_h))
        story.append(Spacer(1, 14))
        story.extend(hr(C_GRAY, 14))

    # ── Ejercicios ────────────────────────────────────────────────────────
    resoluciones = datos_resolvedor.get("resoluciones", [])

    for i, res in enumerate(resoluciones):
        if i > 0:
            story.append(PageBreak())

        titulo_ej = res.get("titulo", f"Ejercicio {res.get('numero','')}")
        story.append(Paragraph(f"Ejercicio {res.get('numero','')} — {titulo_ej}", st['subtitulo']))
        story.extend(hr(C_PURPLE, 6))

        # Enunciado
        story.append(Paragraph(res.get("enunciado_limpio", ""), st['enunciado']))
        story.append(Spacer(1, 8))

        # Idea clave
        idea = res.get("idea_clave", "")
        if idea:
            story.append(Paragraph(f"<b>Idea clave:</b> {idea}", st['idea']))
            story.append(Spacer(1, 10))

        # Pasos
        for paso in res.get("pasos", []):
            titulo_paso = paso.get("titulo_paso", "")
            filas       = paso.get("filas", [])
            story.append(paso_box(titulo_paso, filas, st))

        # Resultado final
        resultado = res.get("resultado_final", "")
        if resultado:
            story.append(Paragraph(resultado, st['result']))

        # Gráfico
        grafico = res.get("grafico")
        if grafico and grafico.get("funciones"):
            try:
                if verbose:
                    print(f"  [PDF] Generando gráfico ej {res.get('numero')}...")
                fig = generar_grafico(grafico)
                story.append(MplFigure(fig, 14, 8.5))
            except Exception as e:
                print(f"  [PDF] Error en gráfico ej {res.get('numero')}: {e}")

    doc.build(story)
    if verbose:
        print(f"[PDF] Generado: {ruta_salida}")


# ── CLI de prueba ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("json_resuelto",  help="JSON del agente resolvedor")
    parser.add_argument("pdf_salida",     help="Ruta del PDF a generar")
    parser.add_argument("--imagen",       help="Imagen del enunciado original (opcional)")
    args = parser.parse_args()

    with open(args.json_resuelto) as f:
        datos = json.load(f)

    generar_pdf(datos, args.pdf_salida, imagen_enunciado=args.imagen, verbose=True)
