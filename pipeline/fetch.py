"""Busca incremental de cotas no data lake da ANA com cache local em parquet.

Estratégia de congelamento (evita re-escanear a série inteira a cada rodada),
com fronteiras INDEPENDENTES para HIDRO e telemetria:
- HIDRO: congela até F_h = max(última data com NivelConsistencia=2,
  1/jan do ano anterior - 1 dia); rodada normal consulta de F_h + 1 em diante.
- Telemetria: congela até F_t = 1/jan do ano anterior - 1 dia (telemetria antiga
  não muda); rodada normal consulta de F_t + 1 em diante. A primeira rodada
  busca a telemetria desde o início do histórico — necessário para estações em
  que o HIDRO parou mas a telemetria continuou (ex.: MANAUS, HIDRO até 2014 e
  telemetria de 2013 em diante).
- Reconsistência/retificação retroativa de períodos congelados só entra com
  --full (recomendado ~1x/ano), que apaga o cache da estação e refaz do zero.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from pipeline import DIR_CACHE
from ana_app import queries

log = logging.getLogger(__name__)

INICIO_HISTORICO = "1900-01-01"


def _caminhos(slug: str) -> tuple[Path, Path, Path]:
    return (DIR_CACHE / f"{slug}_consistido.parquet",
            DIR_CACHE / f"{slug}_telemetria.parquet",
            DIR_CACHE / f"{slug}_meta.json")


def _gravar_atomico(df: pd.DataFrame, caminho: Path) -> None:
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, caminho)


def _gravar_meta(caminho: Path, meta: dict) -> None:
    tmp = caminho.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)


def _limite_congelamento() -> date:
    """Dados até esta data (inclusive) são considerados estáveis."""
    return date(date.today().year - 1, 1, 1) - timedelta(days=1)


def _fronteira_hidro(df_hidro: pd.DataFrame, atual: date | None) -> date | None:
    candidatos = [] if atual is None else [atual]
    if not df_hidro.empty:
        consistido = df_hidro[df_hidro["nivel"] == 2]
        if not consistido.empty:
            candidatos.append(consistido["data"].max().date())
        # bruto antigo (>~19 meses) também congela — raramente muda
        if (df_hidro["data"].dt.date <= _limite_congelamento()).any():
            candidatos.append(_limite_congelamento())
    return max(candidatos) if candidatos else None


def _concat(partes: list[pd.DataFrame], colunas: list[str]) -> pd.DataFrame:
    partes = [df for df in partes if not df.empty]
    if not partes:
        return pd.DataFrame(columns=colunas)
    return pd.concat(partes, ignore_index=True)


def buscar_cotas(conn, estacao: dict, full: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (df_hidro, df_telemetria) completos da estação, usando o cache.

    df_hidro: colunas data, valor, nivel (formato de serie_hidro_diaria).
    df_telemetria: colunas HORDATAHORA, valor (formato de serie_periodo diária).
    """
    slug = estacao["slug"]
    pq_hidro, pq_tele, meta_p = _caminhos(slug)
    amanha = (date.today() + timedelta(days=1)).isoformat()

    if full:
        for p in (pq_hidro, pq_tele, meta_p):
            p.unlink(missing_ok=True)

    meta: dict = {}
    if meta_p.exists():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    fronteira_h = (date.fromisoformat(meta["data_congelada_ate"])
                   if meta.get("data_congelada_ate") else None)
    fronteira_t = (date.fromisoformat(meta["tele_congelada_ate"])
                   if meta.get("tele_congelada_ate") else None)
    congelado_h = (pd.read_parquet(pq_hidro) if pq_hidro.exists()
                   else pd.DataFrame(columns=["data", "valor", "nivel"]))
    congelado_t = (pd.read_parquet(pq_tele) if pq_tele.exists()
                   else pd.DataFrame(columns=["HORDATAHORA", "valor"]))

    # ---- HIDRO (níveis 1 e 2) ----
    ini_h = ((fronteira_h + timedelta(days=1)).isoformat()
             if fronteira_h is not None else INICIO_HISTORICO)
    variavel = estacao.get("variavel", "cota")
    log.info("%s: HIDRO (%s) de %s em diante", slug, variavel, ini_h)
    df_novo_h = queries.serie_hidro_diaria(
        conn, variavel, estacao["codigo_hidroweb"], ini_h, amanha)

    nova_f_h = _fronteira_hidro(df_novo_h, fronteira_h)
    if nova_f_h is not None and (fronteira_h is None or nova_f_h > fronteira_h):
        para_congelar = df_novo_h[df_novo_h["data"].dt.date <= nova_f_h]
        congelado_h = (_concat([congelado_h, para_congelar], ["data", "valor", "nivel"])
                       .drop_duplicates(subset=["nivel", "data"], keep="last")
                       .sort_values(["data", "nivel"]).reset_index(drop=True))
        _gravar_atomico(congelado_h, pq_hidro)
        fronteira_h = nova_f_h
        df_vivo_h = df_novo_h[df_novo_h["data"].dt.date > nova_f_h]
    else:
        df_vivo_h = df_novo_h
    df_hidro = (_concat([congelado_h, df_vivo_h], ["data", "valor", "nivel"])
                .sort_values(["data", "nivel"]).reset_index(drop=True))

    # ---- Telemetria (agregada por dia no servidor) ----
    ini_t = ((fronteira_t + timedelta(days=1)).isoformat()
             if fronteira_t is not None else INICIO_HISTORICO)
    log.info("%s: telemetria (%s) de %s em diante", slug, variavel, ini_t)
    df_novo_t = queries.serie_periodo(
        conn, variavel, estacao["estcodigo_telemetria"], ini_t, amanha,
        agregacao="diaria")[["HORDATAHORA", "valor"]]

    limite = _limite_congelamento()
    tem_antigo = (not df_novo_t.empty
                  and (df_novo_t["HORDATAHORA"].dt.date <= limite).any())
    if tem_antigo and (fronteira_t is None or limite > fronteira_t):
        para_congelar = df_novo_t[df_novo_t["HORDATAHORA"].dt.date <= limite]
        congelado_t = (_concat([congelado_t, para_congelar], ["HORDATAHORA", "valor"])
                       .drop_duplicates(subset="HORDATAHORA", keep="last")
                       .sort_values("HORDATAHORA").reset_index(drop=True))
        _gravar_atomico(congelado_t, pq_tele)
        fronteira_t = limite
        df_vivo_t = df_novo_t[df_novo_t["HORDATAHORA"].dt.date > limite]
    else:
        df_vivo_t = df_novo_t
    df_tele = (_concat([congelado_t, df_vivo_t], ["HORDATAHORA", "valor"])
               .sort_values("HORDATAHORA").reset_index(drop=True))

    consistido = congelado_h[congelado_h["nivel"] == 2] if not congelado_h.empty else congelado_h
    _gravar_meta(meta_p, {
        "data_congelada_ate": fronteira_h.isoformat() if fronteira_h else None,
        "tele_congelada_ate": fronteira_t.isoformat() if fronteira_t else None,
        "ultima_data_consistido": (consistido["data"].max().date().isoformat()
                                   if not consistido.empty else None),
        "ultimo_fetch": pd.Timestamp.now().isoformat(timespec="seconds"),
        "n_linhas_congeladas": int(len(congelado_h) + len(congelado_t)),
    })
    log.info("%s: HIDRO %d dias (%d novos), telemetria %d dias (%d novos)",
             slug, len(df_hidro), len(df_novo_h), len(df_tele), len(df_novo_t))
    return df_hidro, df_tele
