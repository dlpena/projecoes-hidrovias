"""Exporta a série integrada para os JSONs consumidos pelo site.

Formato: matriz ano -> array de 366 posições (calendário fixo com 29/fev;
índice 0 = 1/jan). null = sem dado. Valores inteiros em cm.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline import DIR_DADOS_SITE

# offsets acumulados dos meses num calendário sempre-bissexto (jan=31, fev=29, ...)
OFFSETS_MES = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]


def indice_dia(mes: int, dia: int) -> int:
    """Índice 0..365 no calendário fixo de 366 posições."""
    return OFFSETS_MES[mes - 1] + dia - 1


def _gravar_atomico(caminho: Path, conteudo: str) -> None:
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    os.replace(tmp, caminho)


def _dias_no_ano(ano: int) -> int:
    return pd.Timestamp(ano, 12, 31).dayofyear


def _cobertura_anual(datas: pd.Series) -> dict[str, int]:
    """% de dias com dado por ano: {'1968': 97, ...} (anos sem dado ficam fora)."""
    if datas is None or len(datas) == 0:
        return {}
    datas = pd.to_datetime(datas).dt.normalize().drop_duplicates()
    contagem = datas.dt.year.value_counts().sort_index()
    return {
        str(ano): min(100, round(100 * n / _dias_no_ano(int(ano))))
        for ano, n in contagem.items()
    }


def cobertura_fontes(df_hidro: pd.DataFrame | None,
                     df_tele: pd.DataFrame | None) -> dict:
    """Cobertura anual por fonte, ANTES da integração (para auditoria).

    Telemetria: o pipeline só consulta a janela recente (o histórico coberto
    pelo HIDRO não é re-buscado), então a cobertura dela só aparece nos anos
    consultados.
    """
    fontes: dict[str, dict] = {}
    if df_hidro is not None and not df_hidro.empty:
        fontes["consistido"] = _cobertura_anual(df_hidro.loc[df_hidro["nivel"] == 2, "data"])
        fontes["bruto"] = _cobertura_anual(df_hidro.loc[df_hidro["nivel"] == 1, "data"])
    if df_tele is not None and not df_tele.empty:
        fontes["telemetria"] = _cobertura_anual(df_tele["HORDATAHORA"])
    return {f: c for f, c in fontes.items() if c}


def exportar_estacao(estacao: dict, integrada: pd.DataFrame,
                     df_hidro: pd.DataFrame | None = None,
                     df_tele: pd.DataFrame | None = None) -> dict:
    """Grava docs/dados/{slug}.json e retorna o resumo para o indice.json."""
    anos: dict[str, list] = {}
    fontes_por_ano: dict[str, set] = {}
    for ts, valor, fonte in integrada[["data", "valor", "fonte"]].itertuples(index=False):
        chave = str(ts.year)
        if chave not in anos:
            anos[chave] = [None] * 366
            fontes_por_ano[chave] = set()
        anos[chave][indice_dia(ts.month, ts.day)] = int(round(valor))
        fontes_por_ano[chave].add(fonte)

    ultima = integrada.iloc[-1]
    doc = {
        "slug": estacao["slug"],
        "nome": estacao["nome"],
        "rio": estacao.get("rio"),
        "codigo_hidroweb": estacao["codigo_hidroweb"],
        "estcodigo_telemetria": estacao["estcodigo_telemetria"],
        "unidade": "cm",
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ultima_data": ultima["data"].date().isoformat(),
        "ultimo_valor": int(round(ultima["valor"])),
        "fonte_ultimo_dado": ultima["fonte"],
        "fonte_por_ano": {
            ano: "+".join(sorted(f)) for ano, f in sorted(fontes_por_ano.items())
        },
        "cobertura_fontes": cobertura_fontes(df_hidro, df_tele),
        "anos": {ano: anos[ano] for ano in sorted(anos)},
    }
    caminho = DIR_DADOS_SITE / f"{estacao['slug']}.json"
    _gravar_atomico(caminho, json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    return {
        "slug": estacao["slug"],
        "nome": estacao["nome"],
        "rio": estacao.get("rio"),
        "ultima_data": doc["ultima_data"],
        "ultimo_valor": doc["ultimo_valor"],
        "fonte_ultimo_dado": doc["fonte_ultimo_dado"],
    }


def exportar_indice(resumos: list[dict]) -> None:
    doc = {
        "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "estacoes": resumos,
    }
    _gravar_atomico(
        DIR_DADOS_SITE / "indice.json",
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
    )
