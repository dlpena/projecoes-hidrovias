"""Exporta a série integrada para os JSONs consumidos pelo site.

Formato: matriz ano -> array de 366 posições (calendário fixo com 29/fev;
índice 0 = 1/jan). null = sem dado. Valores inteiros em cm.

Cada estação vira DOIS arquivos, para o navegador poder cachear o que não muda:
- `{slug}_historico.json`: todos os anos ANTERIORES ao corrente (dado que já
  não muda de uma rodada para outra). Só é regravado quando o conteúdo
  realmente muda (ex.: reconsistência retroativa via --full) — assim o blob
  git e o ETag do Pages ficam estáveis, e o navegador reaproveita o cache em
  vez de rebaixar dezenas de anos a cada visita.
- `{slug}_atual.json`: só o ano corrente (o que de fato muda a cada rodada).
  Pequeno, sempre regravado.
O site (`docs/js/dados.js`) busca os dois e mescla num único objeto `doc` com
o mesmo formato que os módulos de gráfico/analogia sempre esperaram.
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


def _gravar_atomico(caminho: Path, doc: dict) -> None:
    conteudo = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    os.replace(tmp, caminho)


def _gravar_se_mudou(caminho: Path, doc: dict, ignorar: tuple[str, ...] = ("gerado_em",)) -> bool:
    """Só regrava o arquivo se o conteúdo (fora os campos em `ignorar`) mudou.

    Mantém o blob git e o ETag do Pages estáveis quando nada de fato mudou,
    para o navegador reaproveitar o cache. Retorna True se regravou.
    """
    if caminho.exists():
        try:
            existente = json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existente = None
        if existente is not None:
            comparavel_novo = {k: v for k, v in doc.items() if k not in ignorar}
            comparavel_velho = {k: v for k, v in existente.items() if k not in ignorar}
            if comparavel_novo == comparavel_velho:
                return False
    _gravar_atomico(caminho, doc)
    return True


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


def _filtrar_cobertura(cobertura: dict, incluir_ano) -> dict:
    filtrada = {
        fonte: {a: p for a, p in cob.items() if incluir_ano(int(a))}
        for fonte, cob in cobertura.items()
    }
    return {f: c for f, c in filtrada.items() if c}


def exportar_estacao(estacao: dict, integrada: pd.DataFrame,
                     df_hidro: pd.DataFrame | None = None,
                     df_tele: pd.DataFrame | None = None) -> dict:
    """Grava docs/dados/{slug}_historico.json e {slug}_atual.json.

    Retorna o resumo para o indice.json.
    """
    anos: dict[str, list] = {}
    fontes_por_ano: dict[str, set] = {}
    for ts, valor, fonte in integrada[["data", "valor", "fonte"]].itertuples(index=False):
        chave = str(ts.year)
        if chave not in anos:
            anos[chave] = [None] * 366
            fontes_por_ano[chave] = set()
        anos[chave][indice_dia(ts.month, ts.day)] = int(round(valor))
        fontes_por_ano[chave].add(fonte)
    fontes_por_ano_str = {ano: "+".join(sorted(f)) for ano, f in fontes_por_ano.items()}

    ultima = integrada.iloc[-1]
    ano_atual = int(ultima["data"].year)
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    cobertura = cobertura_fontes(df_hidro, df_tele)

    meta = {
        "slug": estacao["slug"],
        "nome": estacao["nome"],
        "rio": estacao.get("rio"),
        "codigo_hidroweb": estacao["codigo_hidroweb"],
        "estcodigo_telemetria": estacao["estcodigo_telemetria"],
        "variavel": estacao.get("variavel", "cota"),
        "grandeza": estacao.get("grandeza", "Cota"),
        "unidade": estacao.get("unidade", "cm"),
    }

    historico = {
        **meta,
        "gerado_em": agora,
        "fonte_por_ano": {a: f for a, f in sorted(fontes_por_ano_str.items()) if int(a) != ano_atual},
        "cobertura_fontes": _filtrar_cobertura(cobertura, lambda a: a != ano_atual),
        "anos": {a: anos[a] for a in sorted(anos) if int(a) != ano_atual},
    }
    atual = {
        **meta,
        "gerado_em": agora,
        "ultima_data": ultima["data"].date().isoformat(),
        "ultimo_valor": int(round(ultima["valor"])),
        "fonte_ultimo_dado": ultima["fonte"],
        "fonte_por_ano": {a: f for a, f in fontes_por_ano_str.items() if int(a) == ano_atual},
        "cobertura_fontes": _filtrar_cobertura(cobertura, lambda a: a == ano_atual),
        "anos": {str(ano_atual): anos[str(ano_atual)]},
    }

    _gravar_se_mudou(DIR_DADOS_SITE / f"{estacao['slug']}_historico.json", historico)
    _gravar_atomico(DIR_DADOS_SITE / f"{estacao['slug']}_atual.json", atual)

    return {
        "slug": estacao["slug"],
        "nome": estacao["nome"],
        "rio": estacao.get("rio"),
        "ultima_data": atual["ultima_data"],
        "ultimo_valor": atual["ultimo_valor"],
        "fonte_ultimo_dado": atual["fonte_ultimo_dado"],
    }


def exportar_indice(resumos: list[dict]) -> None:
    doc = {
        "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "estacoes": resumos,
    }
    _gravar_atomico(DIR_DADOS_SITE / "indice.json", doc)
