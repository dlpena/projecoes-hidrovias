"""Fonte de último recurso da Marinha (pipeline/marinha.py)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pipeline import DIR_CACHE, marinha  # noqa: E402


def serie(ini, n, valor, fonte=None):
    df = pd.DataFrame({"data": pd.date_range(ini, periods=n, freq="D"), "valor": float(valor)})
    if fonte:
        df["fonte"] = fonte
    return df


def test_complementar_so_preenche_dias_sem_ana():
    ana = serie("2026-01-01", 10, 200, "telemetria")
    mar = serie("2026-01-05", 10, 999)  # 05 a 14/01; 05 a 10 já têm ANA
    out = marinha.complementar(ana, mar)
    assert len(out) == 14
    assert (out.loc[out["data"] <= "2026-01-10", "fonte"] == "telemetria").all()
    assert (out.loc[out["data"] <= "2026-01-10", "valor"] == 200).all()
    assert (out.loc[out["data"] > "2026-01-10", "fonte"] == "marinha").all()
    assert out["data"].is_monotonic_increasing


def test_complementar_sem_dias_novos_devolve_ana():
    ana = serie("2026-01-01", 10, 200, "bruto")
    assert marinha.complementar(ana, serie("2026-01-01", 5, 1)) is ana


def test_verificar_zero_aceita_mesma_regua():
    ana = serie("2025-01-01", 200, 300, "bruto")
    mar = serie("2025-01-01", 230, 301)  # 1 cm de diferença
    assert marinha.verificar_zero("t", ana, mar)


def test_verificar_zero_rejeita_referencia_diferente():
    ana = serie("2025-01-01", 200, 300, "bruto")
    mar = serie("2025-01-01", 230, 380)  # 80 cm: outro zero
    assert not marinha.verificar_zero("t", ana, mar)


def test_verificar_zero_rejeita_pouca_sobreposicao():
    ana = serie("2025-01-01", 10, 300, "bruto")
    assert not marinha.verificar_zero("t", ana, serie("2025-01-01", 10, 300))


PDF = DIR_CACHE / "porto-murtinho_marinha.pdf"


@pytest.mark.skipif(not PDF.exists(), reason="PDF da Marinha ainda não baixado pelo pipeline")
def test_ler_pdf_real():
    df = marinha.ler_pdf(PDF)
    assert not df["data"].duplicated().any()
    anos = df["data"].dt.year
    # anos completos (todos menos o corrente) têm todos os dias
    for ano in sorted(anos.unique())[:-1]:
        assert (anos == ano).sum() == (366 if ano % 4 == 0 else 365), ano
    assert df["valor"].between(-200, 1000).all()
