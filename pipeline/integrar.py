"""Recomposição da série integrada (consistido > bruto > telemetria)."""

from __future__ import annotations

import pandas as pd

from ana_app import queries


def serie_integrada(df_hidro: pd.DataFrame, df_tele: pd.DataFrame) -> pd.DataFrame:
    """Série diária integrada. Colunas: data (Timestamp normalizado), valor, fonte."""
    df = queries.compor_serie_integrada(df_hidro, df_tele)
    df = df.rename(columns={"HORDATAHORA": "data"})
    return df.sort_values("data").reset_index(drop=True)
