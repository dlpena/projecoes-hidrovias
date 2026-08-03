"""Busca incremental de cotas no data lake da ANA com cache local em parquet.

Estratégia de congelamento (evita re-escanear a série inteira a cada rodada):
- Rodada normal consulta o HIDRO só de `data_congelada_ate + 1` em diante e a
  telemetria na mesma janela.
- São congeladas (movidas para o parquet) as linhas até a fronteira
  F = max(última data com NivelConsistencia=2, 1/jan do ano anterior - 1 dia):
  o consistido não muda, e bruto com mais de ~19 meses raramente muda.
- Reconsistência retroativa de períodos já congelados só entra com --full
  (recomendado ~1x/ano), que apaga o cache da estação e refaz do zero.
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


def _caminhos(slug: str) -> tuple[Path, Path]:
    return DIR_CACHE / f"{slug}_consistido.parquet", DIR_CACHE / f"{slug}_meta.json"


def _gravar_atomico(df: pd.DataFrame, caminho: Path) -> None:
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, caminho)


def _gravar_meta(caminho: Path, meta: dict) -> None:
    tmp = caminho.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)


def _fronteira(df_hidro: pd.DataFrame, fronteira_atual: date | None) -> date | None:
    """Nova fronteira de congelamento a partir dos dados disponíveis."""
    candidatos = [] if fronteira_atual is None else [fronteira_atual]
    if not df_hidro.empty:
        consistido = df_hidro[df_hidro["nivel"] == 2]
        if not consistido.empty:
            candidatos.append(consistido["data"].max().date())
        # bruto antigo (>~19 meses) também congela — raramente muda
        limite_bruto = date(date.today().year - 1, 1, 1) - timedelta(days=1)
        if (df_hidro["data"].dt.date <= limite_bruto).any():
            candidatos.append(limite_bruto)
    return max(candidatos) if candidatos else None


def buscar_cotas(conn, estacao: dict, full: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (df_hidro, df_telemetria) completos da estação, usando o cache.

    df_hidro: colunas data, valor, nivel (formato de serie_hidro_diaria).
    df_telemetria: colunas HORDATAHORA, valor (formato de serie_periodo diária).
    """
    slug = estacao["slug"]
    pq, meta_p = _caminhos(slug)
    amanha = (date.today() + timedelta(days=1)).isoformat()

    congelado = pd.DataFrame(columns=["data", "valor", "nivel"])
    fronteira: date | None = None

    if full:
        pq.unlink(missing_ok=True)
        meta_p.unlink(missing_ok=True)
    elif pq.exists() and meta_p.exists():
        congelado = pd.read_parquet(pq)
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        fronteira = date.fromisoformat(meta["data_congelada_ate"])

    if fronteira is None:
        log.info("%s: busca completa do HIDRO desde %s", slug, INICIO_HISTORICO)
        df_novo = queries.serie_hidro_diaria(
            conn, "cota", estacao["codigo_hidroweb"], INICIO_HISTORICO, amanha
        )
    else:
        ini = (fronteira + timedelta(days=1)).isoformat()
        log.info("%s: busca incremental do HIDRO de %s em diante", slug, ini)
        df_novo = queries.serie_hidro_diaria(
            conn, "cota", estacao["codigo_hidroweb"], ini, amanha
        )

    nova_fronteira = _fronteira(df_novo, fronteira)
    if nova_fronteira is not None and (fronteira is None or nova_fronteira > fronteira):
        para_congelar = df_novo[df_novo["data"].dt.date <= nova_fronteira]
        partes = [df for df in (congelado, para_congelar) if not df.empty]
        congelado = (
            pd.concat(partes, ignore_index=True)
            .drop_duplicates(subset=["nivel", "data"], keep="last")
            .sort_values(["data", "nivel"])
            .reset_index(drop=True)
        )
        _gravar_atomico(congelado, pq)
        consistido = congelado[congelado["nivel"] == 2]
        _gravar_meta(meta_p, {
            "data_congelada_ate": nova_fronteira.isoformat(),
            "ultima_data_consistido": (
                consistido["data"].max().date().isoformat() if not consistido.empty else None
            ),
            "ultimo_fetch": pd.Timestamp.now().isoformat(timespec="seconds"),
            "n_linhas_congeladas": int(len(congelado)),
        })
        fronteira = nova_fronteira
        df_vivo = df_novo[df_novo["data"].dt.date > nova_fronteira]
    else:
        df_vivo = df_novo
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            meta["ultimo_fetch"] = pd.Timestamp.now().isoformat(timespec="seconds")
            _gravar_meta(meta_p, meta)

    partes_hidro = [df for df in (congelado, df_vivo) if not df.empty]
    if not partes_hidro:
        partes_hidro = [pd.DataFrame(columns=["data", "valor", "nivel"])]
    df_hidro = (
        pd.concat(partes_hidro, ignore_index=True)
        .sort_values(["data", "nivel"])
        .reset_index(drop=True)
    )

    ini_tele = (
        (fronteira + timedelta(days=1)).isoformat()
        if fronteira is not None
        else date(date.today().year - 1, 1, 1).isoformat()
    )
    log.info("%s: telemetria de %s em diante", slug, ini_tele)
    df_tele = queries.serie_periodo(
        conn, "cota", estacao["estcodigo_telemetria"], ini_tele, amanha, agregacao="diaria"
    )
    log.info(
        "%s: HIDRO %d dias (%d novos), telemetria %d dias",
        slug, len(df_hidro), len(df_novo), len(df_tele),
    )
    return df_hidro, df_tele
