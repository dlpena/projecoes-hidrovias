"""Gera os PDFs publicados no site:

- docs/pdf/projecoes.pdf — capa + 1 página A4 paisagem por estação;
- docs/pdf/memoria_{slug}.pdf — memória de cálculo auditável por estação
  (parâmetros, heatmap de cobertura por fonte, anos candidatos, projeções
  e série dia a dia), baixada com um clique no site.

Usa o range inicial automático de cada estação (menor ≥10 cm com pelo menos
3 anos análogos) — no site o range segue ajustável (o CSV cobre o range
ajustado). As figuras são as mesmas do site (mesmo algoritmo,
pipeline/analogia.py), exportadas em PNG via kaleido e montadas com reportlab.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import plotly.graph_objects as go

from pipeline import DIR_DADOS_SITE, DIR_PDF
from pipeline import analogia
from estacoes import ESTACOES

MODO_DEFAULT = "cm"

CORES = {
    "observado": "#1a1a1a",
    "maior": "#D55E00",
    "menor": "#0072B2",
    "media": "#009E73",
    "analogo": "#b5b5b5",
    "comum": "#e4e4e4",
    "dia_d": "#888888",
}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]


def _datas_do_ano(ano: int) -> list:
    """datas[i] = date do índice i no calendário fixo (None p/ 29/fev inexistente)."""
    datas = [None] * 366
    d = date(ano, 1, 1)
    while d.year == ano:
        datas[analogia.indice_dia(d.month, d.day)] = d
        d = date.fromordinal(d.toordinal() + 1)
    return datas


def _linha(fig, serie, datas, nome, cor, largura, tracejado=None, legenda=False):
    x = [datas[i] for i in range(366) if datas[i] is not None]
    y = [serie[i] for i in range(366) if datas[i] is not None]
    fig.add_trace(go.Scatter(
        x=x, y=y, name=nome, mode="lines",
        line={"color": cor, "width": largura, "dash": tracejado},
        showlegend=legenda, connectgaps=False, hoverinfo="skip",
    ))


def _rotulo_queda(r: dict, ano: int) -> str:
    c = next((c for c in r["candidatos"] if c["ano"] == ano), None)
    if c is None or c["delta"] is None:
        return ""
    if c["delta"] >= 0:
        return f" · queda {round(c['delta'])} cm"
    return f" · subida {round(-c['delta'])} cm"


def _faixa_y(doc: dict, r: dict) -> float:
    valores = []

    def varre(serie):
        valores.extend(v for v in serie if v is not None)

    varre(doc["anos"][str(r["ano_atual"])])
    if r["trajetorias"]:
        for serie in r["trajetorias"]["todas"].values():
            varre(serie)
        varre(r["trajetorias"]["maior_queda"])
        varre(r["trajetorias"]["menor_queda"])
    return (max(valores) - min(valores)) if len(valores) > 1 else 1.0


def _posicionar_rotulos(minimos: list, amplitude_y: float) -> list:
    """Espelho de posicionarRotulos (grafico.js): evita rótulos sobrepostos."""
    lim_y = amplitude_y * 0.07
    pos = ["bottom center"] * len(minimos)
    for i in range(len(minimos)):
        for j in range(i + 1, len(minimos)):
            d_dias = abs((minimos[i][0] - minimos[j][0]).days)
            if d_dias < 20 and abs(minimos[i][1] - minimos[j][1]) < lim_y:
                cima = i if minimos[i][1] >= minimos[j][1] else j
                pos[cima] = "middle right" if pos[cima] == "top center" else "top center"
    return pos


def _minimo_trajetoria(serie: list, datas: list, idx_d: int) -> tuple:
    minimo, data_min = None, None
    for i in range(idx_d, 366):
        if datas[i] is not None and serie[i] is not None:
            if minimo is None or serie[i] < minimo:
                minimo, data_min = serie[i], datas[i]
    return minimo, data_min


def _marcador(fig, x, y, texto, cor, posicao):
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode="markers+text", text=[texto], textposition=posicao,
        marker={"color": cor, "size": 8}, textfont={"size": 12, "color": cor},
        cliponaxis=False, hoverinfo="skip", showlegend=False,
    ))


def figura_estacao(doc: dict, resultado: dict) -> go.Figure:
    """Mesma figura do site (grafico.js), em plotly Python."""
    r = resultado
    datas = _datas_do_ano(r["ano_atual"])
    fig = go.Figure()

    if r["trajetorias"]:
        tj = r["trajetorias"]
        # trajetórias deslocadas dos análogos, apenas após o dia D (fundo)
        for ano, serie in tj["todas"].items():
            _linha(fig, serie, datas, str(ano), CORES["analogo"], 1)
        _linha(fig, tj["maior_queda"], datas,
               f"Maior queda ({r['ano_maior_queda']}{_rotulo_queda(r, r['ano_maior_queda'])})",
               CORES["maior"], 2, "dash", legenda=True)
        _linha(fig, tj["menor_queda"], datas,
               f"Menor queda ({r['ano_menor_queda']}{_rotulo_queda(r, r['ano_menor_queda'])})",
               CORES["menor"], 2, "dash", legenda=True)
        _linha(fig, tj["media"], datas, f"Média ({len(r['selecionados'])} anos)",
               CORES["media"], 2, legenda=True)
    _linha(fig, doc["anos"][str(r["ano_atual"])], datas,
           f"Observado {r['ano_atual']}", CORES["observado"], 2.5, legenda=True)

    # marcadores com valores: último dado e mínimos das 3 projeções
    _marcador(fig, date.fromisoformat(r["dia_d"]), r["cota_atual"],
              str(round(r["cota_atual"])), CORES["observado"], "top center")
    if r["trajetorias"]:
        tj = r["trajetorias"]
        minimos = []
        for serie, cor in ((tj["maior_queda"], CORES["maior"]),
                           (tj["menor_queda"], CORES["menor"]),
                           (tj["media"], CORES["media"])):
            minimo, data_min = _minimo_trajetoria(serie, datas, r["idx_d"])
            if minimo is not None:
                minimos.append((data_min, minimo, cor))
        posicoes = _posicionar_rotulos(minimos, _faixa_y(doc, r))
        for (data_min, minimo, cor), pos in zip(minimos, posicoes):
            _marcador(fig, data_min, minimo, str(round(minimo)), cor, pos)

    dia_d = date.fromisoformat(r["dia_d"])
    fig.add_shape(type="line", x0=dia_d, x1=dia_d, y0=0, y1=1, yref="paper",
                  line={"color": CORES["dia_d"], "width": 1, "dash": "dot"})
    fig.add_annotation(x=dia_d, y=1, yref="paper", yanchor="bottom", xanchor="left",
                       text=f"último dado {dia_d:%d/%m/%Y}", showarrow=False,
                       font={"size": 11, "color": CORES["dia_d"]})

    ano = r["ano_atual"]
    fig.update_layout(
        margin={"l": 60, "r": 20, "t": 30, "b": 40},
        paper_bgcolor="white", plot_bgcolor="white",
        font={"family": "Segoe UI, sans-serif", "size": 13, "color": "#555"},
        separators=",.",
        xaxis={
            "tickvals": [date(ano, m, 1) for m in range(1, 13)],
            "ticktext": MESES,
            "gridcolor": "#efefec",
            "range": [date(ano, 1, 1), date(ano, 12, 31)],
        },
        yaxis={"title": "Cota (cm)", "gridcolor": "#efefec", "zeroline": False},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0,
                "font": {"size": 12, "color": "#1a1a1a"}},
    )
    return fig


def _fmt_br(v, casas: int = 1) -> str:
    if v is None:
        return ""
    return f"{v:.{casas}f}".replace(".", ",")


def _cor_cobertura(pct: float):
    """Espelho de corCobertura (grafico.js): 0% vermelho -> 50% amarelo -> 100% verde."""
    from reportlab.lib.colors import Color

    def mistura(a, b, t):
        return [v + (w - v) * t for v, w in zip(a, b)]

    vermelho, amarelo, verde = (192, 57, 43), (232, 195, 75), (46, 125, 50)
    rgb = (mistura(vermelho, amarelo, pct / 50) if pct <= 50
           else mistura(amarelo, verde, (pct - 50) / 50))
    return Color(*[v / 255 for v in rgb])


def _tabela_heatmap(doc: dict, largura_util):
    """Heatmap de cobertura anual por fonte como Table (1 célula por ano)."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table

    cf = doc.get("cobertura_fontes") or {}
    if not cf:
        return None
    rotulos = {"consistido": "HIDRO consistido", "bruto": "HIDRO bruto",
               "telemetria": "Telemetria"}
    anos_com_dado = [int(a) for cob in cf.values() for a in cob]
    ano_min, ano_max = min(anos_com_dado), max(anos_com_dado)
    anos = list(range(ano_min, ano_max + 1))
    n = len(anos)

    dados, estilo = [], [
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 4),
    ]
    lin = 0
    for fonte in ("consistido", "bruto", "telemetria"):
        cob = cf.get(fonte)
        if not cob:
            continue
        dados.append([rotulos[fonte]] + [""] * n)
        for col, ano in enumerate(anos, start=1):
            pct = cob.get(str(ano))
            if pct is not None:
                estilo.append(("BACKGROUND", (col, lin), (col, lin), _cor_cobertura(pct)))
        lin += 1
    # eixo: rótulo de década com SPAN de 10 colunas
    eixo = [""] * (n + 1)
    for col, ano in enumerate(anos, start=1):
        if ano % 10 == 0:
            eixo[col] = str(ano)
            fim = min(col + 9, n)
            estilo.append(("SPAN", (col, lin), (fim, lin)))
    dados.append(eixo)
    estilo.append(("FONTSIZE", (1, lin), (-1, lin), 5.5))
    estilo.append(("TEXTCOLOR", (1, lin), (-1, lin), colors.HexColor("#777777")))

    larg_rotulo = 26 * mm
    larg_cel = (largura_util - larg_rotulo) / n
    tabela = Table(dados, colWidths=[larg_rotulo] + [larg_cel] * n,
                   rowHeights=[4.5 * mm] * lin + [3.5 * mm])
    tabela.setStyle(estilo)
    return tabela


def _memoria_estacao(doc: dict, r: dict, saida: Path) -> None:
    """Gera memoria_{slug}.pdf com Platypus (paginação automática das tabelas)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    margem = 15 * mm
    largura_util = A4[0] - 2 * margem
    titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=15, leading=19)
    secao = ParagraphStyle("secao", fontName="Helvetica-Bold", fontSize=11.5,
                           leading=15, spaceBefore=12, spaceAfter=4)
    corpo = ParagraphStyle("corpo", fontName="Helvetica", fontSize=9, leading=12,
                           textColor=colors.HexColor("#333333"))
    nota = ParagraphStyle("nota", fontName="Helvetica", fontSize=7.5, leading=10,
                          textColor=colors.HexColor("#666666"))

    grade = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f1ee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]

    ultima = datetime.fromisoformat(doc["ultima_data"])
    story = [
        Paragraph("Memória de cálculo — projeção por analogia", titulo),
        Paragraph(
            f"<b>{doc['nome']}</b> · rio {doc.get('rio') or '—'} · "
            f"HidroWeb {doc['codigo_hidroweb']} · equip. {doc['estcodigo_telemetria']} · "
            f"gerado em {datetime.now():%d/%m/%Y %H:%M}", corpo),
        Paragraph("1. Parâmetros", secao),
    ]
    params = Table([
        ["Dia D (último dado)", f"{ultima:%d/%m/%Y} ({doc['fonte_ultimo_dado']})",
         "Cota atual", f"{_fmt_br(r['cota_atual'], 0)} cm"],
        ["Range", f"±{_fmt_br(r['range_valor'], 0)} cm (inicial automático)",
         "Anos análogos", str(len(r["selecionados"]))],
    ], colWidths=[largura_util * f for f in (0.22, 0.38, 0.18, 0.22)])
    params.setStyle(grade + [("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                             ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                             ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                             ("BACKGROUND", (0, 0), (-1, 0), colors.white)])
    story += [params, Spacer(0, 2 * mm), Paragraph(
        "Regras: cota do candidato no dia D com tolerância de ±3 dias (mais próximo primeiro; "
        "empate favorece o dia anterior); seleção se |cota − cota atual| ≤ range; exige-se ≥80% "
        "de cobertura entre D e 31/dez e dado nos últimos 10 dias do ano; delta de queda = cota "
        "em D − mínimo pós-D; trajetórias deslocadas para coincidir com a cota atual em D; "
        "lacunas internas interpoladas linearmente (marcadas na seção 5). O range inicial é o "
        "menor (≥10 cm) que contém pelo menos 3 anos análogos; no site o range é ajustável e o "
        "CSV exportado reflete o range ajustado.", nota)]
    if r["aviso"]:
        story.append(Paragraph(f"<b>Aviso:</b> {r['aviso']}", nota))

    heatmap = _tabela_heatmap(doc, largura_util)
    if heatmap is not None:
        story += [Paragraph("2. Cobertura por fonte da série integrada", secao), heatmap,
                  Spacer(0, 1.5 * mm), Paragraph(
            "Cor = % de dias do ano com dado na fonte (verde 100% · amarelo 50% · vermelho 0%; "
            "branco = sem dado). A série integrada usa, dia a dia, a fonte de maior prioridade "
            "disponível (consistido &gt; bruto &gt; telemetria). A telemetria é consultada apenas "
            "na janela recente ainda não coberta pelo histórico congelado do HIDRO.", nota)]

    story.append(Paragraph("3. Universo de anos candidatos", secao))
    cab = ["Ano", "Fonte", "Cota em D\n(cm)", "Tolerância\n(dias)", "Cobertura\npós-D (%)",
           "Mín. pós-D\n(cm)", "Delta queda\n(cm)", "Selecionado", "Motivo de exclusão"]
    linhas = [cab]
    estilo_cand = list(grade) + [("ALIGN", (2, 1), (6, -1), "RIGHT")]
    fonte_por_ano = doc.get("fonte_por_ano") or {}
    for i, c in enumerate(r["candidatos"], start=1):
        linhas.append([
            str(c["ano"]), fonte_por_ano.get(str(c["ano"]), ""),
            _fmt_br(c["cota_em_d"], 0),
            "" if c["dias_tolerancia"] is None else str(c["dias_tolerancia"]),
            "" if c["cobertura"] is None else _fmt_br(c["cobertura"] * 100, 0),
            _fmt_br(c["min_pos_d"], 0), _fmt_br(c["delta"], 0),
            "sim" if c["selecionado"] else "não", c["motivo"] or "",
        ])
        if c["selecionado"]:
            estilo_cand.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#eef5fb")))
    larguras = [largura_util * f for f in (0.07, 0.15, 0.09, 0.09, 0.10, 0.09, 0.10, 0.09, 0.22)]
    tab_cand = Table(linhas, colWidths=larguras, repeatRows=1)
    tab_cand.setStyle(estilo_cand)
    story.append(tab_cand)

    story.append(Paragraph("4. Projeções resultantes", secao))
    if r["trajetorias"]:
        tj = r["trajetorias"]
        datas = _datas_do_ano(r["ano_atual"])
        linhas_proj = [["Curva", "Ano de referência", "Mínimo projetado (cm)",
                        "Data do mínimo", "Queda desde a cota atual (cm)"]]
        for nome, serie, ano in (
            ("Maior queda", tj["maior_queda"], str(r["ano_maior_queda"])),
            ("Menor queda", tj["menor_queda"], str(r["ano_menor_queda"])),
            ("Média", tj["media"], f"{len(r['selecionados'])} anos"),
        ):
            minimo, data_min = _minimo_trajetoria(serie, datas, r["idx_d"])
            linhas_proj.append([
                nome, ano, _fmt_br(minimo, 0),
                f"{data_min:%d/%m/%Y}" if data_min else "",
                _fmt_br(None if minimo is None else r["cota_atual"] - minimo, 0),
            ])
        tab_proj = Table(linhas_proj, colWidths=[largura_util * f
                                                 for f in (0.16, 0.20, 0.22, 0.18, 0.24)])
        tab_proj.setStyle(grade + [("ALIGN", (2, 1), (2, -1), "RIGHT"),
                                   ("ALIGN", (4, 1), (4, -1), "RIGHT")])
        story.append(tab_proj)
    else:
        story.append(Paragraph("Sem projeção (nenhum ano análogo no range).", nota))

    story.append(Paragraph(f"5. Série dia a dia ({r['ano_atual']})", secao))
    obs = doc["anos"][str(r["ano_atual"])]
    tj = r["trajetorias"]
    datas = _datas_do_ano(r["ano_atual"])
    linhas_serie = [["Data", "Observado (cm)", "Proj. maior queda (cm)",
                     "Proj. menor queda (cm)", "Proj. média (cm)", "Interpolado"]]
    for i in range(366):
        if datas[i] is None:
            continue
        tem_obs = obs[i] is not None
        tem_proj = tj is not None and i >= r["idx_d"]
        if not tem_obs and not tem_proj:
            continue
        interp = tem_proj and (tj["maior_queda_interp"][i] or tj["menor_queda_interp"][i])
        linhas_serie.append([
            f"{datas[i]:%d/%m/%Y}",
            _fmt_br(obs[i], 0) if tem_obs else "",
            _fmt_br(tj["maior_queda"][i]) if tem_proj else "",
            _fmt_br(tj["menor_queda"][i]) if tem_proj else "",
            _fmt_br(tj["media"][i]) if tem_proj else "",
            "sim" if interp else "",
        ])
    tab_serie = Table(linhas_serie, colWidths=[largura_util / 6] * 6, repeatRows=1)
    tab_serie.setStyle(grade + [("ALIGN", (1, 1), (4, -1), "RIGHT")])
    story += [tab_serie, Spacer(0, 3 * mm), Paragraph(
        "Fonte: data lake da ANA (banco HIDRO e telemetria) · série integrada "
        "(consistido &gt; bruto &gt; telemetria).", nota)]

    tmp = saida.with_suffix(".pdf.tmp")
    SimpleDocTemplate(
        str(tmp), pagesize=A4, leftMargin=margem, rightMargin=margem,
        topMargin=margem, bottomMargin=margem,
        title=f"Memória de cálculo — {doc['nome']}",
    ).build(story)
    os.replace(tmp, saida)


def gerar(caminho_saida: Path | None = None) -> Path:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    saida = caminho_saida or (DIR_PDF / "projecoes.pdf")
    DIR_PDF.mkdir(parents=True, exist_ok=True)
    largura_pg, altura_pg = landscape(A4)

    docs, resultados = [], []
    for est in ESTACOES:
        caminho = DIR_DADOS_SITE / f"{est['slug']}.json"
        if not caminho.exists():
            continue
        doc = json.loads(caminho.read_text(encoding="utf-8"))
        docs.append(doc)
        rng = analogia.range_inicial(doc)
        resultados.append(analogia.calcular(doc, rng, MODO_DEFAULT))

    tmp_pdf = saida.with_suffix(".pdf.tmp")
    c = canvas.Canvas(str(tmp_pdf), pagesize=landscape(A4))

    # ---- capa ----
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(largura_pg / 2, altura_pg - 45 * mm,
                        "Projeções de Nível — Estações-Chave para Hidrovias")
    c.setFont("Helvetica", 13)
    c.drawCentredString(largura_pg / 2, altura_pg - 56 * mm,
                        "Projeção por analogia · série integrada (HIDRO consistido > bruto > telemetria) · cotas em cm")
    c.drawCentredString(largura_pg / 2, altura_pg - 64 * mm,
                        f"Gerado em {datetime.now():%d/%m/%Y %H:%M} · range por estação: "
                        f"menor (≥10 cm) com pelo menos 3 anos análogos (ajustável na versão web)")
    y = altura_pg - 85 * mm
    c.setFont("Helvetica-Bold", 11)
    colunas = [25 * mm, 95 * mm, 135 * mm, 172 * mm, 207 * mm, 245 * mm]
    for x, titulo in zip(colunas, ["Estação", "Rio", "Último dado", "Cota (cm)",
                                   "Range (±cm)", "Anos análogos"]):
        c.drawString(x, y, titulo)
    c.setFont("Helvetica", 11)
    for doc, r in zip(docs, resultados):
        y -= 7 * mm
        ultima = datetime.fromisoformat(doc["ultima_data"])
        for x, texto in zip(colunas, [
            doc["nome"], doc.get("rio") or "—", f"{ultima:%d/%m/%Y}",
            str(doc["ultimo_valor"]), f"{r['range_valor']:.0f}",
            str(len(r["selecionados"])),
        ]):
            c.drawString(x, y, texto)
    c.setFont("Helvetica", 9)
    c.drawCentredString(largura_pg / 2, 20 * mm,
                        "Fonte: data lake da ANA (banco HIDRO e telemetria) · "
                        "memória de cálculo exportável na versão web")
    c.showPage()

    # ---- uma página por estação ----
    with tempfile.TemporaryDirectory() as tmp:
        for doc, r in zip(docs, resultados):
            fig = figura_estacao(doc, r)
            png = Path(tmp) / f"{doc['slug']}.png"
            fig.write_image(str(png), width=1400, height=680, scale=2)

            c.setFont("Helvetica-Bold", 16)
            c.drawString(15 * mm, altura_pg - 15 * mm, doc["nome"])
            c.setFont("Helvetica", 10)
            c.drawString(15 * mm, altura_pg - 21 * mm,
                         f"rio {doc.get('rio') or '—'} · HidroWeb {doc['codigo_hidroweb']} · "
                         f"equip. {doc['estcodigo_telemetria']} · último dado "
                         f"{datetime.fromisoformat(doc['ultima_data']):%d/%m/%Y} "
                         f"({doc['ultimo_valor']} cm, {doc['fonte_ultimo_dado']})")

            img = ImageReader(str(png))
            larg_img = largura_pg - 30 * mm
            alt_img = larg_img * 680 / 1400
            c.drawImage(img, 15 * mm, altura_pg - 28 * mm - alt_img,
                        width=larg_img, height=alt_img)

            c.setFont("Helvetica", 9)
            base = 14 * mm
            if r["selecionados"]:
                anos_txt = ", ".join(str(a) for a in r["selecionados"])
                c.drawString(15 * mm, base + 4 * mm,
                             f"Anos análogos (±{r['limite_cm']:.0f} cm da cota atual "
                             f"{r['cota_atual']:.0f} cm em {datetime.fromisoformat(r['dia_d']):%d/%m}): "
                             f"{anos_txt}")
            if r["aviso"]:
                c.drawString(15 * mm, base, f"Aviso: {r['aviso']}")
            c.drawString(15 * mm, base - 4 * mm,
                         "Regras: tolerância ±3 dias no dia D · cobertura pós-D ≥80% "
                         "e dado nos últimos 10 dias do ano · trajetórias deslocadas para a cota atual.")
            c.showPage()

    c.save()
    os.replace(tmp_pdf, saida)

    # memórias de cálculo por estação (download direto no site)
    for doc, r in zip(docs, resultados):
        _memoria_estacao(doc, r, DIR_PDF / f"memoria_{doc['slug']}.pdf")
    return saida
