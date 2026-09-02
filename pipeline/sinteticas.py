"""Estações sintéticas: séries calculadas por combinação linear das cotas JÁ
PUBLICADAS de outras estações (docs/dados/{base}_historico.json + _atual.json),
nunca do data lake nem do cache.

Caso de origem: passos críticos de navegação do Tapajós entre Itaituba e
Santarém, sem régua, para os quais a Marinha publica equações réguas–calado
(profundidade disponível no passo, em m, a partir das duas cotas em m).

Calcular a partir dos JSONs publicados torna a série auditável por qualquer um
com os dados públicos e independente de `--estacao` e de token: roda sempre
depois do loop de fetch em atualizar.main, com o que estiver publicado das
bases. O valor de cada dia só existe quando TODAS as bases têm dado naquele
dia; a última linha da série é, por construção, o último dia comum — assim
`ultima_data` nunca aponta para um dia sem valor.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from estacoes import ESTACOES_SINTETICAS, POR_SLUG
from pipeline import DIR_DADOS_SITE
from pipeline.exportar_json import OFFSETS_MES, exportar_estacao

log = logging.getLogger(__name__)

NOTA_SINAL = "Valores ≤ 0 indicam passo acima do nível d'água (emerso)."


def carregar_doc(slug: str, dir_dados: Path = DIR_DADOS_SITE) -> dict | None:
    """Mescla _historico + _atual como docs/js/dados.js. None se faltar arquivo."""
    hist_p = dir_dados / f"{slug}_historico.json"
    atual_p = dir_dados / f"{slug}_atual.json"
    if not hist_p.exists() or not atual_p.exists():
        return None
    hist = json.loads(hist_p.read_text(encoding="utf-8"))
    atual = json.loads(atual_p.read_text(encoding="utf-8"))
    return {
        **atual,
        "anos": {**hist.get("anos", {}), **atual.get("anos", {})},
        "fonte_por_ano": {**hist.get("fonte_por_ano", {}), **atual.get("fonte_por_ano", {})},
    }


def combinar(anos_bases: list[dict[str, list]], coeficientes: list[float],
             constante_cm: float) -> dict[str, list]:
    """Combinação linear dia a dia sobre as matrizes ano -> [366 valores].

    Só anos presentes em todas as bases; o dia recebe valor (float, sem
    arredondar — o exportador arredonda) apenas quando todas têm dado, senão
    None. Anos sem nenhum dia válido ficam fora.
    """
    anos_comuns = set(anos_bases[0])
    for anos in anos_bases[1:]:
        anos_comuns &= set(anos)
    resultado: dict[str, list] = {}
    for ano in sorted(anos_comuns):
        serie = [None] * 366
        algum = False
        for i in range(366):
            valores = [anos[ano][i] for anos in anos_bases]
            if any(v is None for v in valores):
                continue
            serie[i] = sum(c * v for c, v in zip(coeficientes, valores)) + constante_cm
            algum = True
        if algum:
            resultado[ano] = serie
    return resultado


def fonte_combinada(fontes_bases: list[dict[str, str]], ano: str) -> str:
    """União das fontes das bases no ano, na convenção 'bruto+consistido+telemetria'."""
    fontes: set[str] = set()
    for fpa in fontes_bases:
        rotulo = fpa.get(ano)
        if rotulo:
            fontes.update(rotulo.split("+"))
    return "+".join(sorted(fontes)) if fontes else "calculada"


def _data(ano: int, idx: int) -> pd.Timestamp | None:
    """Índice 0..365 do calendário fixo -> data; None para 29/fev em ano não bissexto."""
    mes = max(m for m in range(12) if OFFSETS_MES[m] <= idx) + 1
    dia = idx - OFFSETS_MES[mes - 1] + 1
    try:
        return pd.Timestamp(ano, mes, dia)
    except ValueError:
        return None


def serie_integrada(est: dict, docs_bases: list[dict]) -> pd.DataFrame:
    """Série diária no mesmo contrato de integrar.serie_integrada: data, valor, fonte."""
    constante_cm = round(est["constante_m"] * 100)
    anos = combinar([d["anos"] for d in docs_bases], est["coeficientes"], constante_cm)
    fontes = [d.get("fonte_por_ano", {}) for d in docs_bases]
    linhas = []
    for ano, serie in anos.items():
        fonte = fonte_combinada(fontes, ano)
        for i, v in enumerate(serie):
            if v is None:
                continue
            ts = _data(int(ano), i)
            if ts is not None:
                linhas.append((ts, float(v), fonte))
    df = pd.DataFrame(linhas, columns=["data", "valor", "fonte"])
    return df.sort_values("data").reset_index(drop=True)


def _num(x: float, casas: int) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def meta_sintetica(est: dict) -> dict:
    """Bloco `sintetica` gravado nos JSONs (fórmula legível, bases, fonte do método)."""
    bases = [POR_SLUG[s] for s in est["bases"]]
    termos = " + ".join(f"{_num(c, 3)} × {b['nome']}" for c, b in zip(est["coeficientes"], bases))
    c = est["constante_m"]
    formula = f"Profundidade (m) = {termos} {'−' if c < 0 else '+'} {_num(abs(c), 2)} (cotas em m)"
    return {
        "bases": [{"slug": b["slug"], "nome": b["nome"],
                   "codigo_hidroweb": b.get("codigo_hidroweb"), "coeficiente": coef}
                  for coef, b in zip(est["coeficientes"], bases)],
        "constante_m": c,
        "constante_cm": round(c * 100),
        "formula_texto": formula,
        "fonte_metodo": est["fonte_metodo"],
        "descricao": est.get("descricao", ""),
        "nota_sinal": NOTA_SINAL,
    }


def exportar_sinteticas(estacoes: list[dict] | None = None,
                        dir_dados: Path = DIR_DADOS_SITE) -> tuple[list[dict], list[str]]:
    """Exporta cada sintética a partir dos JSONs das bases em `dir_dados`.

    Saída vai para exportar_json.DIR_DADOS_SITE (como as demais estações).
    Retorna (resumos, falhas) no formato do loop de atualizar.main; base sem
    JSON ou série vazia contam como falha e mantêm o JSON anterior.
    """
    resumos: list[dict] = []
    falhas: list[str] = []
    for est in (ESTACOES_SINTETICAS if estacoes is None else estacoes):
        try:
            docs = [carregar_doc(s, dir_dados) for s in est["bases"]]
            faltando = [s for s, d in zip(est["bases"], docs) if d is None]
            if faltando:
                raise RuntimeError(f"base(s) sem JSON publicado: {', '.join(faltando)}")
            serie = serie_integrada(est, docs)
            if serie.empty:
                raise RuntimeError("nenhum dia com dado em todas as bases")
            resumos.append(exportar_estacao(est, serie, meta_extra={"sintetica": meta_sintetica(est)}))
            log.info("%s: sintética exportada (última data %s, %d dias)",
                     est["slug"], resumos[-1]["ultima_data"], len(serie))
        except Exception:
            log.exception("%s: falha — mantendo JSON anterior", est["slug"])
            falhas.append(est["slug"])
    return resumos, falhas
