"""Testes do algoritmo de analogia: casos sintéticos + paridade Python <-> JS."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pipeline import analogia  # noqa: E402


def serie_constante(valor, ini=0, fim=366, ano=2001):
    s = [None] * 366
    for i in range(ini, fim):
        if i != analogia.IDX_29FEV or analogia.bissexto(ano):
            s[i] = valor
    return s


def doc_base(anos: dict, ultima_data="2026-07-01"):
    return {"slug": "teste", "ultima_data": ultima_data, "anos": anos}


IDX_1JUL = analogia.indice_dia(7, 1)  # 182


def test_selecao_basica_e_deltas():
    """3 anos análogos: quedas de 50, 20 e 80 cm a partir de 1/jul."""
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026)}
    for ano, queda in (("2001", 50), ("2002", 20), ("2003", 80)):
        s = serie_constante(500, ano=int(ano))
        for i in range(IDX_1JUL, 366):
            if s[i] is not None:
                s[i] = 500 - queda  # degrau: mínimo pós-D = 500 - queda
        s[IDX_1JUL] = 500
        anos[ano] = s
    r = analogia.calcular(doc_base(anos), 10, "cm")
    assert r["selecionados"] == [2001, 2002, 2003]
    assert r["ano_maior_queda"] == 2003
    assert r["ano_menor_queda"] == 2002
    deltas = {c["ano"]: c["delta"] for c in r["candidatos"]}
    assert deltas == {2001: 50, 2002: 20, 2003: 80}
    assert r["aviso"] is None


def test_fora_do_range_cm_e_pct():
    anos = {
        "2026": serie_constante(500, 0, IDX_1JUL + 1, 2026),
        "2001": serie_constante(515, ano=2001),  # 15 cm acima
        "2002": serie_constante(505, ano=2002),
    }
    r = analogia.calcular(doc_base(anos), 10, "cm")
    m = {c["ano"]: c["motivo"] for c in r["candidatos"]}
    assert m[2001] == "fora do intervalo"
    assert 2002 in r["selecionados"]
    # modo %: 3% de 500 = 15 cm -> 2001 entra
    r2 = analogia.calcular(doc_base(anos), 3, "pct")
    assert 2001 in r2["selecionados"]


def test_tolerancia_dia_d():
    """Ano sem dado exato em D usa o mais próximo em ±3 dias; >3 dias exclui."""
    s_ok = serie_constante(500, ano=2001)
    s_ok[IDX_1JUL] = s_ok[IDX_1JUL - 1] = None  # dado mais próximo a -2? não: +1
    s_longe = serie_constante(500, ano=2002)
    for d in range(-3, 4):
        s_longe[IDX_1JUL + d] = None
    anos = {
        "2026": serie_constante(500, 0, IDX_1JUL + 1, 2026),
        "2001": s_ok,
        "2002": s_longe,
    }
    r = analogia.calcular(doc_base(anos), 10, "cm")
    c1 = next(c for c in r["candidatos"] if c["ano"] == 2001)
    assert c1["dias_tolerancia"] == 1 and c1["selecionado"]
    c2 = next(c for c in r["candidatos"] if c["ano"] == 2002)
    assert c2["motivo"] == "sem dado no dia D"


def test_empate_tolerancia_prefere_dia_anterior():
    s = serie_constante(500, ano=2001)
    s[IDX_1JUL] = None
    s[IDX_1JUL - 1] = 490
    s[IDX_1JUL + 1] = 510
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026), "2001": s}
    r = analogia.calcular(doc_base(anos), 15, "cm")
    c = next(c for c in r["candidatos"] if c["ano"] == 2001)
    assert c["cota_em_d"] == 490 and c["dias_tolerancia"] == -1


def test_cobertura_insuficiente():
    """Ano com só 50% dos dias pós-D ou sem dado no fim do ano é excluído."""
    s_furada = serie_constante(500, ano=2001)
    pos = [i for i in range(IDX_1JUL, 366) if i != analogia.IDX_29FEV]
    for i in pos[:: 2]:  # remove metade
        s_furada[i] = None
    s_furada[IDX_1JUL] = 500
    s_sem_fim = serie_constante(500, IDX_1JUL - 5, 340, ano=2002)  # nada após 340
    anos = {
        "2026": serie_constante(500, 0, IDX_1JUL + 1, 2026),
        "2001": s_furada,
        "2002": s_sem_fim,
    }
    r = analogia.calcular(doc_base(anos), 10, "cm")
    m = {c["ano"]: c["motivo"] for c in r["candidatos"]}
    assert m[2001] == "série incompleta pós-D"
    assert m[2002] == "série incompleta pós-D"


def test_delta_negativo_ano_que_sobe():
    s = serie_constante(500, ano=2001)
    for i in range(IDX_1JUL, 366):
        if s[i] is not None:
            s[i] = 500 + (i - IDX_1JUL)  # só sobe
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026), "2001": s}
    r = analogia.calcular(doc_base(anos), 10, "cm")
    c = next(c for c in r["candidatos"] if c["ano"] == 2001)
    assert c["selecionado"] and c["delta"] == 0  # mínimo pós-D é o próprio dia D


def test_trajetoria_deslocada_e_interpolada():
    s = serie_constante(490, ano=2001)  # 10 cm abaixo do atual
    s[IDX_1JUL + 5] = None  # lacuna interna
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026), "2001": s}
    r = analogia.calcular(doc_base(anos), 10, "cm")
    traj = r["trajetorias"]["maior_queda"]
    assert traj[IDX_1JUL] == 500  # começa na cota atual (offset +10)
    assert traj[IDX_1JUL + 5] == 500  # interpolado entre vizinhos 500
    assert r["trajetorias"]["maior_queda_interp"][IDX_1JUL + 5] is True
    assert traj[IDX_1JUL - 1] is None  # nada antes do dia D


def test_aviso_poucos_analogos():
    anos = {
        "2026": serie_constante(500, 0, IDX_1JUL + 1, 2026),
        "2001": serie_constante(505, ano=2001),
    }
    r = analogia.calcular(doc_base(anos), 10, "cm")
    assert "1 ano(s)" in r["aviso"]
    r0 = analogia.calcular(doc_base(anos), 1, "cm")
    assert r0["trajetorias"] is None and "Nenhum" in r0["aviso"]


def test_29fev_ano_nao_bissexto_ignorado():
    """Dia D em 28/fev de ano não bissexto: posição 59 não conta na cobertura."""
    idx_28fev = analogia.indice_dia(2, 28)
    anos = {
        "2026": serie_constante(500, 0, idx_28fev + 1, 2026),  # 2026 não bissexto
        "2001": serie_constante(500, ano=2001),  # não bissexto: 59 = None
    }
    r = analogia.calcular(doc_base(anos, "2026-02-28"), 10, "cm")
    c = next(c for c in r["candidatos"] if c["ano"] == 2001)
    assert c["cobertura"] == 1.0 and c["selecionado"]


def test_range_inicial():
    """Menor intervalo (>=50) que contém pelo menos 3 análogos."""
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026)}
    for ano, cota in (("2001", 502), ("2002", 512), ("2003", 577), ("2004", 620)):
        anos[ano] = serie_constante(cota, ano=int(ano))
    # distâncias: 2, 12, 77, 120 -> 3ª menor = 77
    assert analogia.range_inicial(doc_base(anos)) == 77
    # com só 2 anos elegíveis, cobre todos (distâncias 2, 62 -> 62)
    anos2 = {"2026": anos["2026"], "2001": anos["2001"],
             "2002": serie_constante(562, ano=2002)}
    assert analogia.range_inicial(doc_base(anos2)) == 62
    # distâncias pequenas: nunca abaixo de 50
    anos3 = {"2026": anos["2026"],
             "2001": serie_constante(501, ano=2001),
             "2002": serie_constante(503, ano=2002),
             "2003": serie_constante(504, ano=2003)}
    assert analogia.range_inicial(doc_base(anos3)) == 50


@pytest.mark.skipif(shutil.which("node") is None, reason="node não disponível")
def test_paridade_range_inicial():
    real = RAIZ / "docs" / "dados" / "itaituba.json"
    if not real.exists():
        pytest.skip("itaituba.json ausente")
    doc = json.loads(real.read_text(encoding="utf-8"))
    r_py = analogia.range_inicial(doc)
    script = (
        "const A = require(%s);"
        "const doc = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "console.log(JSON.stringify(A.rangeInicial(doc)));"
    ) % json.dumps(str(RAIZ / "docs" / "js" / "analogia.js"))
    out = subprocess.run(["node", "-e", script], input=json.dumps(doc),
                         capture_output=True, text=True, check=True, encoding="utf-8")
    assert json.loads(out.stdout) == r_py


@pytest.mark.skipif(shutil.which("node") is None, reason="node não disponível")
def test_paridade_python_js():
    """Mesmo resultado no Python e no JS para dados reais e sintéticos."""
    docs = []
    real = RAIZ / "docs" / "dados" / "itaituba.json"
    if real.exists():
        docs.append(json.loads(real.read_text(encoding="utf-8")))
    anos = {"2026": serie_constante(500, 0, IDX_1JUL + 1, 2026)}
    for ano in range(2000, 2020):
        s = serie_constante(495 + (ano % 7) * 3, ano=ano)
        for i in range(IDX_1JUL, 366):
            if s[i] is not None:
                s[i] -= (i - IDX_1JUL) * (ano % 5) * 0.2
        if ano % 4 == 1:
            s[IDX_1JUL] = None  # força tolerância
        anos[str(ano)] = s
    docs.append(doc_base(anos))

    for params in ((10, "cm"), (25, "cm"), (2, "pct")):
        for doc in docs:
            r_py = analogia.calcular(doc, *params)
            script = (
                "const A = require(%s);"
                "const doc = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
                "console.log(JSON.stringify(A.calcular(doc, %s, %s)));"
            ) % (
                json.dumps(str(RAIZ / "docs" / "js" / "analogia.js")),
                params[0], json.dumps(params[1]),
            )
            out = subprocess.run(
                ["node", "-e", script], input=json.dumps(doc),
                capture_output=True, text=True, check=True, encoding="utf-8",
            )
            r_js = json.loads(out.stdout)
            assert r_js["selecionados"] == r_py["selecionados"], params
            assert r_js["ano_maior_queda"] == r_py["ano_maior_queda"], params
            assert r_js["ano_menor_queda"] == r_py["ano_menor_queda"], params
            assert r_js["aviso"] == r_py["aviso"], params
            if r_py["trajetorias"] is None:
                assert r_js["trajetorias"] is None
                continue
            for chave in ("maior_queda", "menor_queda", "media"):
                t_py = r_py["trajetorias"][chave]
                t_js = r_js["trajetorias"][chave]
                for i in range(366):
                    a, b = t_py[i], t_js[i]
                    if a is None or b is None:
                        assert a == b, (params, chave, i)
                    else:
                        assert abs(a - b) < 1e-9, (params, chave, i)
