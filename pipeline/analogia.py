"""Algoritmo de projeção por analogia — FONTE DA VERDADE das regras.

Espelhado em docs/js/analogia.js (site). Qualquer mudança de regra deve ser
aplicada nos dois arquivos e coberta por tests/test_analogia.py.

Regras (confirmadas com o usuário):
- Dia D = última data com dado do ano corrente; cota atual = valor em D.
- Candidatos = todos os anos exceto o corrente.
- Cota do candidato em D: valor no índice de D; se ausente, o dado mais próximo
  em ±3 dias (mais próximo primeiro; empate -> dia anterior); sem dado -> excluído.
- Seleção: |cota_candidato - cota_atual| <= range (cm) ou <= range% da cota atual.
- Cobertura pós-D: >=80% dos dias-calendário com dado entre D e 31/dez E pelo
  menos um dado nos últimos 10 dias do ano; senão excluído.
- Delta de queda = cota_em_D_do_ano - min(valores de D a 31/dez). Delta <= 0
  (ano que só sobe) permanece.
- Trajetórias (maior queda, menor queda): série do ano de D a 31/dez deslocada
  por (cota_atual - cota_do_ano_em_D); lacunas internas interpoladas linearmente
  (marcadas). Média = média ponto a ponto das trajetórias deslocadas (já
  interpoladas) de todos os selecionados.
- <3 selecionados -> aviso; 0 -> sem projeção.

Calendário fixo de 366 posições (29/fev tem índice 59); em anos não bissextos a
posição 59 é ignorada nos cálculos.
"""

from __future__ import annotations

import math

TOLERANCIA_DIAS = 3
COBERTURA_MINIMA = 0.8
DIAS_FIM_ANO = 10
MIN_ANALOGOS = 3

OFFSETS_MES = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
IDX_29FEV = 59


def indice_dia(mes: int, dia: int) -> int:
    return OFFSETS_MES[mes - 1] + dia - 1


def bissexto(ano: int) -> bool:
    return ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)


def _posicoes_validas(ano: int, ini: int, fim: int = 366) -> list[int]:
    """Índices de dias-calendário existentes no ano, no intervalo [ini, fim)."""
    return [i for i in range(ini, fim) if i != IDX_29FEV or bissexto(ano)]


def _cota_em_d(serie: list, idx_d: int, ano: int) -> tuple[float | None, int | None]:
    """Valor no dia D com tolerância de ±N dias. Retorna (valor, desvio_em_dias)."""
    for desvio in range(TOLERANCIA_DIAS + 1):
        for delta in ((-desvio, desvio) if desvio else (0,)):
            i = idx_d + delta
            if 0 <= i < 366 and (i != IDX_29FEV or bissexto(ano)):
                v = serie[i]
                if v is not None:
                    return float(v), delta
    return None, None


def _interpolar(valores: list) -> tuple[list, list]:
    """Interpola lacunas internas (entre o primeiro e o último dado).

    Retorna (valores_preenchidos, flags_interpolado). Fora do trecho com dado,
    permanece None.
    """
    n = len(valores)
    out = list(valores)
    flags = [False] * n
    com_dado = [i for i, v in enumerate(valores) if v is not None]
    if len(com_dado) < 2:
        return out, flags
    for a, b in zip(com_dado, com_dado[1:]):
        if b - a > 1:
            va, vb = float(valores[a]), float(valores[b])
            for i in range(a + 1, b):
                out[i] = va + (vb - va) * (i - a) / (b - a)
                flags[i] = True
    return out, flags


def range_inicial(doc: dict, min_analogos: int = MIN_ANALOGOS, minimo: float = 10.0) -> float:
    """Menor range inteiro (cm, >= minimo) que seleciona pelo menos min_analogos anos.

    Se nem com range infinito há min_analogos anos elegíveis, retorna o range que
    inclui todos os elegíveis (ou o mínimo, se não houver nenhum).
    """
    r = calcular(doc, float("inf"), "cm")
    dists = sorted(
        abs(c["cota_em_d"] - r["cota_atual"])
        for c in r["candidatos"] if c["selecionado"]
    )
    if not dists:
        return minimo
    alvo = dists[min_analogos - 1] if len(dists) >= min_analogos else dists[-1]
    return max(minimo, float(math.ceil(alvo)))


def calcular(doc: dict, range_valor: float = 10.0, modo: str = "cm") -> dict:
    """Calcula a analogia sobre o JSON da estação.

    doc: dicionário no formato de docs/dados/{slug}.json.
    range_valor: meia-largura do range (cm se modo="cm", % se modo="pct").
    """
    anos = doc["anos"]
    ano_atual = int(doc["ultima_data"][:4])
    mes_d, dia_d = int(doc["ultima_data"][5:7]), int(doc["ultima_data"][8:10])
    idx_d = indice_dia(mes_d, dia_d)
    serie_atual = anos[str(ano_atual)]
    cota_atual = float(serie_atual[idx_d])

    limite = range_valor if modo == "cm" else abs(cota_atual) * range_valor / 100.0

    candidatos = []
    for chave in sorted(anos):
        ano = int(chave)
        if ano == ano_atual:
            continue
        serie = anos[chave]
        cand = {
            "ano": ano, "cota_em_d": None, "dias_tolerancia": None,
            "cobertura": None, "min_pos_d": None, "delta": None,
            "selecionado": False, "motivo": None,
        }
        cota_d, desvio = _cota_em_d(serie, idx_d, ano)
        if cota_d is None:
            cand["motivo"] = "sem dado no dia D"
            candidatos.append(cand)
            continue
        cand["cota_em_d"] = cota_d
        cand["dias_tolerancia"] = desvio

        pos = _posicoes_validas(ano, idx_d)
        com_dado = [i for i in pos if serie[i] is not None]
        cand["cobertura"] = len(com_dado) / len(pos) if pos else 0.0
        if com_dado:
            minimo = min(float(serie[i]) for i in com_dado)
            cand["min_pos_d"] = minimo
            cand["delta"] = cota_d - minimo

        if abs(cota_d - cota_atual) > limite:
            cand["motivo"] = "fora do intervalo"
            candidatos.append(cand)
            continue

        fim_ano = [i for i in com_dado if i >= 366 - DIAS_FIM_ANO]
        if cand["cobertura"] < COBERTURA_MINIMA or not fim_ano:
            cand["motivo"] = "série incompleta pós-D"
            candidatos.append(cand)
            continue

        cand["selecionado"] = True
        candidatos.append(cand)

    selecionados = [c for c in candidatos if c["selecionado"]]

    resultado = {
        "ano_atual": ano_atual,
        "dia_d": doc["ultima_data"],
        "idx_d": idx_d,
        "cota_atual": cota_atual,
        "range_valor": range_valor,
        "modo": modo,
        "limite_cm": limite,
        "candidatos": candidatos,
        "selecionados": [c["ano"] for c in selecionados],
        "ano_maior_queda": None,
        "ano_menor_queda": None,
        "trajetorias": None,
        "aviso": None,
    }
    if not selecionados:
        resultado["aviso"] = "Nenhum ano análogo no intervalo — amplie o intervalo."
        return resultado
    if len(selecionados) < MIN_ANALOGOS:
        resultado["aviso"] = (
            f"Apenas {len(selecionados)} ano(s) análogo(s) — amplie o intervalo."
        )

    maior = max(selecionados, key=lambda c: c["delta"])
    menor = min(selecionados, key=lambda c: c["delta"])
    resultado["ano_maior_queda"] = maior["ano"]
    resultado["ano_menor_queda"] = menor["ano"]

    # trajetórias deslocadas + interpoladas de todos os selecionados
    por_ano = {}
    for c in selecionados:
        serie = anos[str(c["ano"])]
        offset = cota_atual - c["cota_em_d"]
        bruta = [None] * 366
        for i in range(idx_d, 366):
            if serie[i] is not None:
                bruta[i] = float(serie[i]) + offset
        cheia, flags = _interpolar(bruta)
        por_ano[c["ano"]] = (cheia, flags)

    media = [None] * 366
    for i in range(idx_d, 366):
        vals = [t[0][i] for t in por_ano.values() if t[0][i] is not None]
        if vals:
            media[i] = sum(vals) / len(vals)

    resultado["trajetorias"] = {
        "maior_queda": por_ano[maior["ano"]][0],
        "maior_queda_interp": por_ano[maior["ano"]][1],
        "menor_queda": por_ano[menor["ano"]][0],
        "menor_queda_interp": por_ano[menor["ano"]][1],
        "media": media,
        "todas": {str(a): t[0] for a, t in por_ano.items()},
    }
    return resultado
