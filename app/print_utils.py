import os
import calendar
from app.i18n import weekdays_short
import platform
import subprocess
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader

from app.config import (
    BASE_DIR,
    DOCS_DIR,
    COR_PRINCIPAL,
    COR_VERMELHO,
    COR_WEEKEND,
    COR_BRANCO,
    COR_LINHA,
    COR_LINHA_INTERNA,
    COR_AZUL_REFEICAO,
    COR_EMENTA,
    COR_OBS,
    MESES_PT,
    TIPOS_WELFARE,
)
from app.db import get_welfares_mes, get_day_offs_mes


PDF_DIR = os.path.join(BASE_DIR, "docs", "exports")


def _hex_color(c):
    return c


def _draw_image(c, path, x, y, w, h):
    if not os.path.exists(path):
        return False
    try:
        c.drawImage(ImageReader(path), x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
        return True
    except Exception:
        return False


def _wrap_text(text, font_name, font_size, max_width):
    if not text:
        return []

    linhas = []
    for original in str(text).splitlines():
        words = original.split()
        if not words:
            linhas.append("")
            continue

        atual = ""
        for word in words:
            teste = word if not atual else f"{atual} {word}"
            if stringWidth(teste, font_name, font_size) <= max_width:
                atual = teste
            else:
                if atual:
                    linhas.append(atual)
                atual = word
        if atual:
            linhas.append(atual)

    return linhas


def _draw_wrapped(c, text, x, y_top, max_width, font_name, font_size, fill, line_gap=1.2, max_lines=None):
    linhas = _wrap_text(text, font_name, font_size, max_width)
    if max_lines is not None:
        linhas = linhas[:max_lines]

    c.setFillColor(fill)
    c.setFont(font_name, font_size)
    line_h = font_size + line_gap

    y = y_top
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= line_h

    return y


def _texto_ementa(welfare):
    prato = (welfare.get("prato") or "").strip()
    sobremesa = (welfare.get("sobremesa") or "").strip()

    if prato and sobremesa:
        return f"{prato}/{sobremesa}"
    if prato:
        return prato
    if sobremesa:
        return sobremesa
    return ""


def _draw_welfare_icons(c, welfare, right_x, top_y, icon_size, gap):
    ficheiros = TIPOS_WELFARE.get(welfare.get("tipo"), [])
    x = right_x - icon_size

    for ficheiro in reversed(ficheiros):
        path = os.path.join(DOCS_DIR, ficheiro)
        ok = _draw_image(c, path, x, top_y - icon_size + 2, icon_size, icon_size)
        if not ok:
            c.setFillColor(COR_VERMELHO)
            c.setFont("Helvetica-Bold", icon_size)
            c.drawCentredString(x + icon_size / 2, top_y - icon_size + 3, "*")
        x -= (icon_size + gap)


def _draw_welfare_block(c, welfare, x, y_top, width, height, compacto=False):
    refeicao = welfare["refeicao"].upper()

    titulo_size = 7.0 if compacto else 8.0
    obs_size = 5.5 if compacto else 6.5
    ementa_size = 5.5 if compacto else 7.0
    icon_size = 9.0 if compacto else 10.5

    c.setFillColor(COR_AZUL_REFEICAO)
    c.setFont("Helvetica-Bold", titulo_size)
    c.drawString(x, y_top, refeicao)

    _draw_welfare_icons(c, welfare, x + width, y_top + 2, icon_size, 2.2)

    obs = (welfare.get("observacao") or "").strip()
    ementa = _texto_ementa(welfare)

    y = y_top - (8 if compacto else 10)
    text_width = max(width - 2, 20)

    if obs:
        y = _draw_wrapped(
            c,
            obs,
            x,
            y,
            text_width,
            "Helvetica-Bold",
            obs_size,
            COR_OBS,
            line_gap=0.8,
            max_lines=2 if compacto else 3,
        )
        y += 1.5 if compacto else -1.5

    if ementa:
        _draw_wrapped(
            c,
            ementa,
            x,
            y,
            text_width,
            "Helvetica",
            ementa_size,
            COR_EMENTA,
            line_gap=0.7,
            max_lines=2 if compacto else 3,
        )


def _draw_day_cell(c, dia, welfares_dia, x, y, w, h, bg, is_day_off=False):
    c.setFillColor(bg)
    c.rect(x, y, w, h, fill=1, stroke=0)

    c.setStrokeColor(COR_LINHA)
    c.setLineWidth(0.35)
    c.rect(x, y, w, h, fill=0, stroke=1)

    if welfares_dia:
        c.setStrokeColor(COR_PRINCIPAL)
        c.setLineWidth(0.75)
        c.rect(x + 0.7, y + 0.7, w - 1.4, h - 1.4, fill=0, stroke=1)

    c.setFillColor("#000000")
    c.setFont("Helvetica-Bold" if welfares_dia else "Helvetica", 6.5)
    c.drawString(x + 3.2, y + h - 8.5, f"{dia} - day off" if is_day_off else str(dia))

    almoco = next((a for a in welfares_dia if a["refeicao"] == "Almoço"), None)
    jantar = next((a for a in welfares_dia if a["refeicao"] == "Jantar"), None)

    if almoco and jantar:
        bloco1_top = y + h * 0.76
        separador_y = y + h * 0.52
        bloco2_top = separador_y - 7

        _draw_welfare_block(c, almoco, x + 5, bloco1_top, w - 10, h * 0.27, compacto=True)

        c.setStrokeColor(COR_LINHA_INTERNA)
        c.setLineWidth(0.35)
        c.line(x + 5, separador_y, x + w - 5, separador_y)

        _draw_welfare_block(c, jantar, x + 5, bloco2_top, w - 10, h * 0.30, compacto=True)
    elif almoco:
        _draw_welfare_block(c, almoco, x + 5, y + h * 0.70, w - 10, h * 0.55, compacto=False)
    elif jantar:
        _draw_welfare_block(c, jantar, x + 5, y + h * 0.70, w - 10, h * 0.55, compacto=False)


def gerar_pdf_mes(ano, mes, output_path=None):
    os.makedirs(PDF_DIR, exist_ok=True)

    nome_mes = MESES_PT[mes]
    if output_path is None:
        output_path = os.path.join(PDF_DIR, f"PRT_Welfare_{ano}_{mes:02d}.pdf")

    page_w, page_h = landscape(A4)
    margem = 5 * mm

    c = canvas.Canvas(output_path, pagesize=landscape(A4))

    left = margem
    bottom = margem
    usable_w = page_w - 2 * margem
    usable_h = page_h - 2 * margem

    sidebar_w = 20 * mm
    header_h = 13 * mm
    legenda_h = 11 * mm

    cal_x = left + sidebar_w
    cal_w = usable_w - sidebar_w
    cal_y = bottom + legenda_h
    cal_h = usable_h - header_h - legenda_h

    dados_mes = get_welfares_mes(ano, mes)
    day_offs_mes = get_day_offs_mes(ano, mes)
    total = sum(len(v) for v in dados_mes.values())

    # Fundo geral
    c.setFillColor(COR_BRANCO)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Barra lateral
    c.setFillColor(COR_PRINCIPAL)
    c.rect(left, bottom, sidebar_w, usable_h, fill=1, stroke=0)

    year_h = 18 * mm
    c.setFillColor(COR_VERMELHO)
    c.rect(left, bottom + usable_h - year_h, sidebar_w, year_h, fill=1, stroke=0)
    c.setFillColor("white")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(left + sidebar_w / 2, bottom + usable_h - year_h / 2 - 4, str(ano))

    c.saveState()
    c.translate(left + sidebar_w / 2, bottom + usable_h / 2)
    c.rotate(90)
    c.setFont("Helvetica", 27)
    c.setFillColor("white")
    c.drawCentredString(0, -7, nome_mes.upper())
    c.restoreState()

    # Header de impressão: só total welfare no canto direito
    c.setFillColor(COR_BRANCO)
    c.rect(cal_x, bottom + usable_h - header_h, cal_w, header_h, fill=1, stroke=0)

    icon_path = os.path.join(DOCS_DIR, "cooking.png")
    total_text = f"Total Welfare: {total}"
    c.setFont("Helvetica-Bold", 8)
    tw = stringWidth(total_text, "Helvetica-Bold", 8)
    tx = cal_x + cal_w - tw - 6 * mm
    ty = bottom + usable_h - header_h / 2 - 2
    _draw_image(c, icon_path, tx - 9, ty - 3, 7, 7)
    c.setFillColor(COR_PRINCIPAL)
    c.drawString(tx, ty, total_text)

    # Cabeçalhos dos dias
    dias_semana = weekdays_short()
    head_h = 10 * mm
    cell_w = cal_w / 7
    grid_h = cal_h - head_h
    cell_h = grid_h / 6

    head_y = cal_y + grid_h
    for i, nome in enumerate(dias_semana):
        x = cal_x + i * cell_w
        c.setFillColor(COR_PRINCIPAL)
        c.rect(x, head_y, cell_w, head_h, fill=1, stroke=0)
        c.setStrokeColor("#000000")
        c.setLineWidth(0.45)
        c.rect(x, head_y, cell_w, head_h, fill=0, stroke=1)
        c.setFillColor("white")
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + cell_w / 2, head_y + head_h / 2 - 3, nome)

    semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(ano, mes)
    while len(semanas) < 6:
        semanas.append([0, 0, 0, 0, 0, 0, 0])

    for row_idx, semana in enumerate(semanas):
        y = cal_y + grid_h - (row_idx + 1) * cell_h
        for col_idx, dia in enumerate(semana):
            x = cal_x + col_idx * cell_w
            data_str = f"{ano}-{mes:02d}-{dia:02d}" if dia else ""
            is_day_off = bool(data_str and data_str in day_offs_mes)
            bg = COR_WEEKEND if (col_idx in [5, 6] or is_day_off) else COR_BRANCO
            if dia == 0:
                c.setFillColor(bg)
                c.rect(x, y, cell_w, cell_h, fill=1, stroke=0)
                c.setStrokeColor(COR_LINHA)
                c.setLineWidth(0.35)
                c.rect(x, y, cell_w, cell_h, fill=0, stroke=1)
            else:
                _draw_day_cell(c, dia, dados_mes.get(data_str, []), x, y, cell_w, cell_h, bg, is_day_off=is_day_off)

    # Legenda
    leg_y = bottom
    c.setFillColor(COR_BRANCO)
    c.rect(cal_x, leg_y, cal_w, legenda_h, fill=1, stroke=0)
    c.setStrokeColor(COR_LINHA)
    c.setLineWidth(0.35)
    c.rect(cal_x, leg_y, cal_w, legenda_h, fill=0, stroke=1)

    c.setFillColor("black")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(cal_x + cal_w * 0.18, leg_y + legenda_h / 2 - 2.5, "NOTAS:")

    legenda = [
        ("Welfare", "cooking.png", 0.35),
        ("Aniversário", "cake.png", 0.50),
        ("Welfare Livre", "star.png", 0.65),
    ]

    for texto, img, pos in legenda:
        lx = cal_x + cal_w * pos
        c.setFont("Helvetica", 7.5)
        c.setFillColor("black")
        texto_y = leg_y + legenda_h / 2 - 2.5
        c.drawString(lx, texto_y, texto)
        icon_size = 6.2
        icon_x = lx + stringWidth(texto, "Helvetica", 7.5) + 4
        icon_y = texto_y - 2.0
        _draw_image(c, os.path.join(DOCS_DIR, img), icon_x, icon_y, icon_size, icon_size)

    c.showPage()
    c.save()

    return output_path


def imprimir_pdf(pdf_path):
    sistema = platform.system().lower()

    try:
        if sistema == "windows":
            os.startfile(pdf_path, "print")
            return True, "Enviado para impressão."
        if sistema == "darwin":
            subprocess.Popen(["open", pdf_path])
            return True, "PDF aberto para impressão."
        subprocess.Popen(["xdg-open", pdf_path])
        return True, "PDF aberto para impressão."
    except Exception as exc:
        return False, str(exc)
