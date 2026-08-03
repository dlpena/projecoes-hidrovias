"""Gera docs/pdf/projecoes.pdf: capa + 1 página A4 paisagem por estação.

Usa o range inicial automático de cada estação (menor ≥10 cm com pelo menos
3 anos análogos) — no site o range segue ajustável. As figuras são as mesmas
do site (mesmo algoritmo, pipeline/analogia.py), exportadas em PNG via kaleido
e montadas com reportlab.
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
        _linha(fig, tj["maior_queda"], datas, f"Maior queda ({r['ano_maior_queda']})",
               CORES["maior"], 2, "dash", legenda=True)
        _linha(fig, tj["menor_queda"], datas, f"Menor queda ({r['ano_menor_queda']})",
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
        for serie, cor in ((tj["maior_queda"], CORES["maior"]),
                           (tj["menor_queda"], CORES["menor"]),
                           (tj["media"], CORES["media"])):
            minimo, data_min = _minimo_trajetoria(serie, datas, r["idx_d"])
            if minimo is not None:
                _marcador(fig, data_min, minimo, str(round(minimo)), cor, "bottom center")

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
    return saida
