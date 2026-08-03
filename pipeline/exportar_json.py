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


def exportar_estacao(estacao: dict, integrada: pd.DataFrame) -> dict:
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
