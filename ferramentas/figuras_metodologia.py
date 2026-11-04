# -*- coding: utf-8 -*-
"""Figuras da página de metodologia (docs/metodologia.html).

Rodado à mão, fora da rodada agendada:
    python ferramentas/figuras_metodologia.py

O mesmo arquivo serve aos dois painéis (Hidrovias Joaquim e Belo Monte): o exemplo é
escolhido pelo JSON presente em docs/dados/. As figuras usam os dados publicados, com o
ano corrente cortado no dia D de cada exemplo (simula o painel naquele dia, com o
intervalo inicial automático e a projeção até 31/dez). Todo número que aparece numa
figura é calculado aqui, pelo mesmo pipeline/analogia.py que o site espelha.

Saída: docs/img/metodologia/{analogos,trajetorias,ciclo,regimes}.png
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from pipeline import analogia as an  # noqa: E402

DADOS = RAIZ / "docs" / "dados"
SAIDA = RAIZ / "docs" / "img" / "metodologia"

if (DADOS / "belo-monte-montante.json").exists():
    EXEMPLO = {"slug": "belo-monte-montante", "nome": "Belo Monte Montante",
               "d_descida": date(2026, 8, 1), "d_subida": date(2026, 11, 4)}
else:
    EXEMPLO = {"slug": "itaituba", "nome": "Itaituba",
               "d_descida": date(2026, 10, 1), "d_subida": date(2026, 11, 4)}

COR = {"obs": "#1a1a1a", "inferior": "#D55E00", "superior": "#0072B2", "media": "#009E73",
       "analogo": "#b5b5b5", "fora": "#e6e6e6", "faixa": "#7a5cc4", "d": "#888888"}
NOME_CRIT = {"maior_queda": "Maior queda", "menor_queda": "Menor queda",
             "menor_subida": "Menor subida", "maior_subida": "Maior subida"}

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#eeeeec", "grid.linewidth": 0.8,
    "axes.edgecolor": "#999999", "axes.titlesize": 10.5, "axes.titleweight": "bold",
    "legend.frameon": False, "legend.fontsize": 8.5,
})


def carregar() -> dict:
    slug = EXEMPLO["slug"]
    unico = DADOS / f"{slug}.json"
    if unico.exists():
        return json.loads(unico.read_text(encoding="utf-8"))
    h = json.loads((DADOS / f"{slug}_historico.json").read_text(encoding="utf-8"))
    a = json.loads((DADOS / f"{slug}_atual.json").read_text(encoding="utf-8"))
    doc = {**h, **{k: v for k, v in a.items() if k != "anos"}}
    doc["anos"] = {**h["anos"], **a["anos"]}
    return doc


def cortar(doc: dict, d: date) -> dict:
    """Doc como estaria no dia D: o ano corrente sem nada depois de D."""
    anos = dict(doc["anos"])
    s = list(anos[str(d.year)])
    for k in range(an.indice_dia(d.month, d.day) + 1, 366):
        s[k] = None
    anos[str(d.year)] = s
    return {**doc, "anos": anos, "ultima_data": d.isoformat()}


def num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def br(d: date | str) -> str:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%d/%m/%Y")


def serie_calendario(doc: dict, ano: int, ano_eixo: int):
    """(datas no ano do eixo, valores) do ano `ano`, dia a dia, sem 29/fev inexistente."""
    s = doc["anos"].get(str(ano))
    x, y = [], []
    t = date(ano_eixo, 1, 1)
    while t.year == ano_eixo:
        if not (t.month == 2 and t.day == 29 and not an.bissexto(ano)):
            v = s[an.indice_dia(t.month, t.day)] if s else None
            x.append(t)
            y.append(v)
        t += timedelta(days=1)
    return x, y


def observado(doc: dict, ini: date, fim: date):
    x, y = [], []
    t = ini
    while t <= fim:
        s = doc["anos"].get(str(t.year))
        x.append(t)
        y.append(None if s is None or (t.month == 2 and t.day == 29 and not an.bissexto(t.year))
                 else s[an.indice_dia(t.month, t.day)])
        t += timedelta(days=1)
    return x, y


def rodar(doc: dict, d: date) -> tuple[dict, dict]:
    dc = cortar(doc, d)
    r = an.calcular(dc, an.range_inicial(dc), "cm")
    return dc, r


def eixo_datas(ax, mensal=True):
    ax.xaxis.set_major_locator(mdates.MonthLocator() if mensal else mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    for rot in ax.get_xticklabels():
        rot.set_text(rot.get_text().lower())


MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def fmt_mes(x, _pos=None):
    d = mdates.num2date(x)
    return MESES[d.month - 1]


def fmt_mes_ano(x, _pos=None):
    d = mdates.num2date(x)
    return f"{MESES[d.month - 1]}/{d.strftime('%y')}"


def curvas_extremas(r: dict):
    tj = r["trajetorias"]
    return [(tj["inferior"], r["ano_inferior"], r["criterio_inferior"], COR["inferior"]),
            (tj["superior"], r["ano_superior"], r["criterio_superior"], COR["superior"])]


def delta_txt(r: dict, ano: int, criterio: str, u: str) -> str:
    c = next(c for c in r["candidatos"] if c["ano"] == ano)
    v = c["subida"] if criterio.endswith("subida") else c["delta"]
    return f"{'subida' if criterio.endswith('subida') else 'queda'} {num(v)} {u}"


def fig_analogos(doc, u, g):
    d = EXEMPLO["d_descida"]
    dc, r = rodar(doc, d)
    sel = set(r["selecionados"])
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for c in r["candidatos"]:
        x, y = serie_calendario(dc, c["ano"], d.year)
        ax.plot(x, y, color=COR["analogo"] if c["ano"] in sel else COR["fora"],
                lw=1.1 if c["ano"] in sel else 0.7, zorder=2 if c["ano"] in sel else 1)
    x, y = observado(dc, date(d.year, 1, 1), d)
    ax.plot(x, y, color=COR["obs"], lw=2.2, zorder=4, label=f"Observado {d.year} até D")
    lim = r["limite_cm"]
    ax.errorbar([d], [r["cota_atual"]], yerr=[[lim], [lim]], fmt="o", color=COR["faixa"],
                ms=5, capsize=5, lw=2, zorder=5,
                label=f"Intervalo em D: {num(r['cota_atual'])} ± {num(lim)} {u}")
    for c in r["candidatos"]:
        if c["ano"] in sel:
            ax.plot([d], [c["cota_em_d"]], "o", color="#555555", ms=3.5, zorder=4)
    ax.axvline(d, color=COR["d"], ls=":", lw=1)
    ax.plot([], [], color=COR["analogo"], lw=1.1, label=f"Anos análogos ({len(sel)})")
    ax.plot([], [], color=COR["fora"], lw=1.5, label="Demais anos do histórico")
    ax.set_title(f"1. {EXEMPLO['nome']}, dia D = {br(d)}: anos com {g.lower()} dentro do intervalo neste mesmo dia",
                 loc="left")
    ax.set_ylabel(f"{g} ({u})")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_mes))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: num(v)))
    ax.set_xlim(date(d.year, 1, 1), date(d.year, 12, 31))
    ax.legend(loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig(SAIDA / "analogos.png", dpi=150)
    plt.close(fig)
    return r


def fig_trajetorias(doc, u, g):
    d = EXEMPLO["d_descida"]
    dc, r = rodar(doc, d)
    xp = [date.fromisoformat(s) for s in r["datas_proj"]]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for traj in r["trajetorias"]["todas"].values():
        ax.plot(xp, traj, color=COR["analogo"], lw=0.9)
    for serie, ano, crit, cor in curvas_extremas(r):
        ax.plot(xp, serie, color=cor, lw=2, label=f"{NOME_CRIT[crit]} ({ano}, {delta_txt(r, ano, crit, u)})")
    ax.plot(xp, r["trajetorias"]["media"], color=COR["media"], lw=2, ls=(0, (2, 1.5)),
            label=f"Média dos {len(r['selecionados'])} análogos")
    ini = d - timedelta(days=75)
    x, y = observado(dc, ini, d)
    ax.plot(x, y, color=COR["obs"], lw=2.2, label="Observado até D")
    ax.plot([], [], color=COR["analogo"], lw=0.9, label="Cada análogo, deslocado")
    ax.axvline(d, color=COR["d"], ls=":", lw=1)
    ax.set_title(f"2. Trajetórias dos análogos depois de D, deslocadas para partir do valor atual "
                 f"({num(r['cota_atual'])} {u})", loc="left")
    ax.set_ylabel(f"{g} ({u})")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_mes))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: num(v)))
    ax.set_xlim(ini, date(d.year, 12, 31))
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SAIDA / "trajetorias.png", dpi=150)
    plt.close(fig)


def fig_ciclo(doc, u, g):
    d = EXEMPLO["d_subida"]
    dc, r = rodar(doc, d)
    cic = r["ciclo"]
    linhas = sorted((c for c in r["candidatos"] if c["selecionado"] and c["dia_min_ciclo"] is not None),
                    key=lambda c: c["dia_min_ciclo"])
    alt = max(3.2, 1.2 + 0.2 * len(linhas))
    fig, ax = plt.subplots(figsize=(10, alt))
    ini, fim = d - timedelta(days=an.CICLO_MEIO_DIAS), d + timedelta(days=an.CICLO_MEIO_DIAS)
    for i, c in enumerate(linhas):
        ax.plot([ini, fim], [i, i], color="#dddddd", lw=1, zorder=1)
        ax.plot([d + timedelta(days=c["dia_min_ciclo"])], [i], "v", color=COR["inferior"], ms=6, zorder=3)
        ax.plot([d + timedelta(days=c["dia_max_ciclo"])], [i], "^", color=COR["superior"], ms=6, zorder=3)
    dmin, dmax = date.fromisoformat(cic["data_media_min"]), date.fromisoformat(cic["data_media_max"])
    ax.axvline(dmin, color=COR["inferior"], ls="--", lw=1.4)
    ax.axvline(dmax, color=COR["superior"], ls="--", lw=1.4)
    ax.axvline(d, color=COR["obs"], ls=":", lw=1.4)
    topo = len(linhas) - 0.4
    ax.text(dmin, topo, f" data média do\n mínimo: {br(dmin)}", color=COR["inferior"], va="top",
            ha="right" if dmin < d else "left", fontsize=8.5)
    ax.text(dmax, topo, f" data média do\n máximo: {br(dmax)}", color=COR["superior"], va="top",
            ha="left" if dmax < fim - timedelta(days=60) else "right", fontsize=8.5)
    ax.text(d, -1.1, f"dia D\n{br(d)}", ha="center", va="top", fontsize=8.5)
    ax.plot([], [], "v", color=COR["inferior"], label="Mínimo do ciclo de cada análogo")
    ax.plot([], [], "^", color=COR["superior"], label="Máximo do ciclo de cada análogo")
    ax.set_yticks(range(len(linhas)), [str(c["ano"]) for c in linhas], fontsize=7.5)
    ax.set_ylim(-2.2, len(linhas) + 0.6)
    ax.set_xlim(ini, fim)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_mes_ano))
    ax.grid(axis="y", visible=False)
    proximo = "máximo (regime de subida)" if r["regime"] == "subida" else "mínimo (regime de descida)"
    ax.set_title(f"3. Ciclo de 365 dias em torno de D ({cic['n']} análogos): depois de D, o próximo "
                 f"extremo médio é o {proximo}", loc="left")
    fig.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(SAIDA / "ciclo.png", dpi=150)
    plt.close(fig)


def fig_regimes(doc, u, g):
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4), sharey=False)
    fim_obs = date.fromisoformat(doc["ultima_data"])
    for ax, d in zip(eixos, (EXEMPLO["d_descida"], EXEMPLO["d_subida"])):
        dc, r = rodar(doc, d)
        xp = [date.fromisoformat(s) for s in r["datas_proj"]]
        for traj in r["trajetorias"]["todas"].values():
            ax.plot(xp, traj, color=COR["analogo"], lw=0.8)
        for serie, ano, crit, cor in curvas_extremas(r):
            ax.plot(xp, serie, color=cor, lw=2, label=f"{NOME_CRIT[crit]} ({ano}, {delta_txt(r, ano, crit, u)})")
        ax.plot(xp, r["trajetorias"]["media"], color=COR["media"], lw=2, ls=(0, (2, 1.5)), label="Média")
        ini = d - timedelta(days=60)
        x, y = observado(dc, ini, d)
        ax.plot(x, y, color=COR["obs"], lw=2.2, label="Observado até D")
        if fim_obs > d:
            x, y = observado(doc, d, fim_obs)
            ax.plot(x, y, color=COR["obs"], lw=1.6, ls="--",
                    label=f"Observado depois de D (até {br(fim_obs)})")
        ax.axvline(d, color=COR["d"], ls=":", lw=1)
        cic = r["ciclo"]
        quando = "ainda não chegou" if r["regime"] == "descida" else "já passou"
        ax.set_title(f"D = {br(d)}: regime de {r['regime']}\n"
                     f"data média do mínimo {br(cic['data_media_min'])} ({quando})", loc="left")
        ax.set_xlim(ini, date(d.year, 12, 31))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_mes))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _p: num(v)))
        ax.set_ylabel(f"{g} ({u})")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=7.8)
    fig.suptitle(f"4. {EXEMPLO['nome']}: curvas destacadas em cada regime", x=0.01, ha="left",
                 fontweight="bold", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(SAIDA / "regimes.png", dpi=150)
    plt.close(fig)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    doc = carregar()
    u = doc.get("unidade", "cm")
    g = doc.get("grandeza", "Cota")
    fig_analogos(doc, u, g)
    fig_trajetorias(doc, u, g)
    fig_ciclo(doc, u, g)
    fig_regimes(doc, u, g)
    for d in (EXEMPLO["d_descida"], EXEMPLO["d_subida"]):
        _, r = rodar(doc, d)
        print(f"{EXEMPLO['nome']} {br(d)}: regime {r['regime']}, {len(r['selecionados'])} análogos, "
              f"intervalo ±{num(r['limite_cm'])} {u}, mínimo médio {r['ciclo']['data_media_min']}, "
              f"máximo médio {r['ciclo']['data_media_max']}")
    print("figuras em", SAIDA)


if __name__ == "__main__":
    main()
