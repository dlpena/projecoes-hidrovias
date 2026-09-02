"""Séries sintéticas (pipeline/sinteticas.py): combinação linear das bases publicadas."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pipeline import analogia, exportar_json, sinteticas  # noqa: E402

COEFS = [0.955, 0.045]
CONST_CM = -215

EST = {
    "slug": "teste-sint", "nome": "TESTE SINTÉTICA", "rio": "Tapajós", "tipo": "sintetica",
    "variavel": "profundidade", "grandeza": "Profundidade", "unidade": "cm",
    "bases": ["itaituba", "santarem"], "coeficientes": COEFS, "constante_m": -2.15,
    "fonte_metodo": "Fonte de teste", "descricao": "Passo de teste.",
}


def serie(valor, ini=0, fim=366):
    s = [None] * 366
    for i in range(ini, fim):
        s[i] = valor
    return s


def docs_bases(ultimo_a=244, ultimo_b=240):
    """Duas bases com 2025 completo e 2026 até índices distintos (2025/2026 não bissextos)."""
    a = {"anos": {"2025": serie(500), "2026": serie(431, 0, ultimo_a + 1)},
         "fonte_por_ano": {"2025": "consistido", "2026": "telemetria"}}
    b = {"anos": {"2025": serie(400), "2026": serie(473, 0, ultimo_b + 1)},
         "fonte_por_ano": {"2025": "bruto", "2026": "telemetria"}}
    return [a, b]


def test_combinacao_linear_exata_sem_arredondar():
    anos = sinteticas.combinar([{"2026": serie(431)}, {"2026": serie(473)}], COEFS, CONST_CM)
    assert anos["2026"][100] == pytest.approx(0.955 * 431 + 0.045 * 473 - 215)  # 217.89


def test_dia_sem_par_vira_none_e_ano_sem_par_fica_fora():
    a = {"2025": serie(500), "2026": serie(431, 0, 200)}
    b = {"2026": serie(473, 100, 366)}
    anos = sinteticas.combinar([a, b], COEFS, CONST_CM)
    assert set(anos) == {"2026"}
    assert anos["2026"][50] is None and anos["2026"][250] is None
    assert anos["2026"][150] is not None


def test_negativo_preservado():
    anos = sinteticas.combinar([{"2026": serie(100)}, {"2026": serie(100)}], COEFS, CONST_CM)
    assert anos["2026"][0] == pytest.approx(-115)


def test_fonte_uniao_das_bases():
    fontes = [{"2026": "bruto+telemetria"}, {"2026": "consistido"}]
    assert sinteticas.fonte_combinada(fontes, "2026") == "bruto+consistido+telemetria"
    assert sinteticas.fonte_combinada([{}, {}], "2026") == "calculada"


def test_serie_integrada_termina_no_ultimo_dia_comum_e_pula_29fev():
    df = sinteticas.serie_integrada(EST, docs_bases(ultimo_a=244, ultimo_b=240))
    assert list(df.columns) == ["data", "valor", "fonte"]
    assert df["data"].iloc[-1] == pd.Timestamp(2026, 8, 28)  # índice 240, não o 244 da base A
    assert (df["data"].dt.year == 2025).sum() == 365  # 29/fev não entra em ano não bissexto
    assert df.loc[df["data"].dt.year == 2025, "fonte"].iloc[0] == "bruto+consistido"
    assert df["valor"].iloc[-1] == pytest.approx(217.89)


def test_exportacao_arredonda_marca_sintetica_e_analogia_roda(tmp_path, monkeypatch):
    monkeypatch.setattr(exportar_json, "DIR_DADOS_SITE", tmp_path)
    df = sinteticas.serie_integrada(EST, docs_bases())
    resumo = exportar_json.exportar_estacao(
        EST, df, meta_extra={"sintetica": sinteticas.meta_sintetica(EST)})

    atual = json.loads((tmp_path / "teste-sint_atual.json").read_text(encoding="utf-8"))
    hist = json.loads((tmp_path / "teste-sint_historico.json").read_text(encoding="utf-8"))
    assert resumo["tipo"] == "sintetica"
    assert atual["ultima_data"] == "2026-08-28" and atual["ultimo_valor"] == 218
    assert atual["codigo_hidroweb"] is None and atual["estcodigo_telemetria"] is None
    assert atual["grandeza"] == "Profundidade" and atual["unidade"] == "cm"
    assert hist["sintetica"] == atual["sintetica"]
    s = atual["sintetica"]
    assert s["constante_cm"] == -215
    assert s["formula_texto"] == (
        "Profundidade (m) = 0,955 × ITAITUBA + 0,045 × SANTARÉM − 2,15 (cotas em m)")
    assert [b["slug"] for b in s["bases"]] == ["itaituba", "santarem"]

    doc = {"slug": EST["slug"], "ultima_data": atual["ultima_data"],
           "anos": {**hist["anos"], **atual["anos"]}}
    r = analogia.calcular(doc, 50.0, "cm")
    assert r["cota_atual"] == 218


def _gravar_bases(dir_dados):
    for slug, doc in zip(["itaituba", "santarem"], docs_bases()):
        (dir_dados / f"{slug}_historico.json").write_text(
            json.dumps({"anos": {"2025": doc["anos"]["2025"]},
                        "fonte_por_ano": {"2025": doc["fonte_por_ano"]["2025"]}}), encoding="utf-8")
        (dir_dados / f"{slug}_atual.json").write_text(
            json.dumps({"anos": {"2026": doc["anos"]["2026"]},
                        "fonte_por_ano": {"2026": doc["fonte_por_ano"]["2026"]}}), encoding="utf-8")


def test_exportar_sinteticas_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(exportar_json, "DIR_DADOS_SITE", tmp_path)
    _gravar_bases(tmp_path)
    resumos, falhas = sinteticas.exportar_sinteticas([EST], dir_dados=tmp_path)
    assert falhas == [] and len(resumos) == 1
    assert resumos[0]["slug"] == "teste-sint" and resumos[0]["ultimo_valor"] == 218
    assert (tmp_path / "teste-sint_historico.json").exists()


def test_base_ausente_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setattr(exportar_json, "DIR_DADOS_SITE", tmp_path)
    resumos, falhas = sinteticas.exportar_sinteticas([EST], dir_dados=tmp_path)
    assert resumos == [] and falhas == ["teste-sint"]
    assert not (tmp_path / "teste-sint_atual.json").exists()
