"""Algoritmo de projeção por analogia — FONTE DA VERDADE das regras.

Espelhado em docs/js/analogia.js (site). Qualquer mudança de regra deve ser
aplicada nos dois arquivos e coberta por tests/test_analogia.py.

Regras (confirmadas com o usuário):
- Dia D = última data com dado do ano corrente; cota atual = valor em D.
- Horizonte H (meses inteiros, o mês de D não conta): a projeção vai de D até o
  último dia do H-ésimo mês após o mês de D, podendo atravessar a virada do ano.
  Sem H (None), o horizonte termina em 31/dez do ano corrente (regra original).
- Candidatos = todos os anos exceto o corrente. O análogo do ano A acompanha o
  calendário: a data t da janela corresponde a (t.ano + A - ano_corrente, t.mes,
  t.dia), ou seja, um horizonte que entra no ano seguinte usa os dados de A+1.
- Cota do candidato em D: valor na data análoga a D; se ausente, o dado mais
  próximo em ±3 dias (mais próximo primeiro; empate -> dia anterior); sem dado
  -> excluído.
- Seleção: |cota_candidato - cota_atual| <= range (cm) ou <= range% da cota atual.
- Cobertura: >=80% dos dias da janela D..fim com dado E pelo menos um dado nos
  últimos 10 dias da janela; senão excluído ("série incompleta pós-D"). Um
  análogo cujo ano seguinte não existe (ou ainda não chegou ao fim da janela)
  cai nesta regra.
- Queda = cota_em_D_do_ano - min(valores da janela); subida = max(valores da
  janela) - cota_em_D_do_ano. Valores <= 0 permanecem.
- Regime (decidido pelo conjunto de análogos selecionados; o delta continua
  individual, por curva): para cada análogo, no ciclo de 365 dias centrado na
  data análoga a D (D-182 a D+182, com >= 70% de dias com dado), localiza o dia do
  mínimo e o dia do máximo (empate -> o primeiro). Data média do mínimo e data
  média do máximo = média circular desses dias (período de 365 dias), com o
  desvio-padrão circular de cada uma (o desvio é só informativo).
    descida -> o próximo extremo médio a partir de D é o mínimo (a data média
               do mínimo ainda não passou, ou já passou a do máximo depois dela);
    subida  -> o próximo extremo médio é o máximo (a data média do mínimo já
               passou), mesmo que alguns análogos ainda desçam antes de subir.
  Critério único: as duas curvas são sempre do mesmo tipo. Sem nenhum análogo
  com ciclo completo: descida (regra original).
- Curvas extremas (inferior / superior):
    descida -> maior queda / menor queda
    subida  -> menor subida / maior subida
  Empates: na queda, desempata pela subida (maior queda -> menor subida; menor
  queda -> maior subida); na subida, pela queda (menor subida -> maior queda;
  maior subida -> menor queda). Empate remanescente: o ano mais antigo.
- Trajetórias: série análoga na janela deslocada por (cota_atual -
  cota_do_ano_em_D); lacunas internas interpoladas linearmente (marcadas).
  Média = média ponto a ponto das trajetórias deslocadas (já interpoladas) de
  todos os selecionados.
- <3 selecionados -> aviso; 0 -> sem projeção.

Representação: os dados chegam na matriz ano -> 366 posições (29/fev = índice
59). As trajetórias saem alinhadas a `datas_proj` (lista ISO de D ao fim do
horizonte, uma posição por dia do calendário real). 29/fev na janela de ano
não bissexto do análogo não tem data análoga: não conta na cobertura e é
preenchido pela interpolação.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

TOLERANCIA_DIAS = 3
COBERTURA_MINIMA = 0.8
DIAS_FIM_JANELA = 10
MIN_ANALOGOS = 3
CICLO_MEIO_DIAS = 182              # ciclo de 365 dias centrado em D
CICLO_COBERTURA_MINIMA = 0.7
PERIODO_CICLO = 365

OFFSETS_MES = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
IDX_29FEV = 59


def indice_dia(mes: int, dia: int) -> int:
    return OFFSETS_MES[mes - 1] + dia - 1


def bissexto(ano: int) -> bool:
    return ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)


def fim_horizonte(ultima_data: str, meses: int | None) -> str:
    """Último dia do mês que fica `meses` meses após o mês de D (o mês de D não
    conta). Sem `meses`, 31/dez do ano de D (regra original)."""
    d = date.fromisoformat(ultima_data)
    if meses is None:
        return date(d.year, 12, 31).isoformat()
    m = d.month + meses            # mês 1-based, pode passar de 12
    ano, mes = d.year + (m - 1) // 12, (m - 1) % 12 + 1
    primeiro_seguinte = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return (primeiro_seguinte - timedelta(days=1)).isoformat()


def _data_analoga(t: date, desloc: int) -> date | None:
    """Mesmo dia/mês `desloc` anos adiante (ou atrás); None se 29/fev inexistente."""
    try:
        return date(t.year + desloc, t.month, t.day)
    except ValueError:
        return None


def _valor(anos: dict, d: date | None) -> float | None:
    if d is None:
        return None
    serie = anos.get(str(d.year))
    if serie is None:
        return None
    v = serie[indice_dia(d.month, d.day)]
    return None if v is None else float(v)


def _cota_em_d(anos: dict, d0: date, desloc: int) -> tuple[float | None, int | None]:
    """Valor na data análoga a D com tolerância de ±N dias. Retorna (valor, desvio)."""
    for desvio in range(TOLERANCIA_DIAS + 1):
        for delta in ((-desvio, desvio) if desvio else (0,)):
            v = _valor(anos, _data_analoga(d0 + timedelta(days=delta), desloc))
            if v is not None:
                return v, delta
    return None, None


def _extremos_ciclo(anos: dict, d0: date, desloc: int) -> tuple[int | None, int | None]:
    """Dias (relativos a D) do mínimo e do máximo do análogo no ciclo centrado em D.

    Empate -> o primeiro. Menos de 70% de dias com dado -> (None, None).
    """
    vals = []
    for k in range(-CICLO_MEIO_DIAS, CICLO_MEIO_DIAS + 1):
        v = _valor(anos, _data_analoga(d0 + timedelta(days=k), desloc))
        if v is not None:
            vals.append((k, v))
    if len(vals) < CICLO_COBERTURA_MINIMA * (2 * CICLO_MEIO_DIAS + 1):
        return None, None
    k_min, v_min = vals[0]
    k_max, v_max = vals[0]
    for k, v in vals[1:]:
        if v < v_min:
            k_min, v_min = k, v
        if v > v_max:
            k_max, v_max = k, v
    return k_min, k_max


def _media_circular(dias: list) -> tuple[float, float]:
    """Média e desvio-padrão circulares (em dias) de posições num ciclo de 365 dias."""
    w = 2 * math.pi / PERIODO_CICLO
    s = c = 0.0
    for d in dias:
        s += math.sin(w * d)
        c += math.cos(w * d)
    s /= len(dias)
    c /= len(dias)
    r = min(math.hypot(s, c), 1.0)
    media = math.atan2(s, c) / w
    if r >= 1.0 - 1e-12:            # ruído de arredondamento: análogos concordam
        desvio = 0.0
    elif r > 1e-12:
        desvio = math.sqrt(-2.0 * math.log(r)) / w
    else:
        desvio = math.inf
    return media, desvio


def _arred(x: float) -> int:
    """Arredondamento meio para cima (igual a Math.round do JS)."""
    return math.floor(x + 0.5)


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


def range_inicial(doc: dict, min_analogos: int = MIN_ANALOGOS, minimo: float = 50.0,
                  horizonte_meses: int | None = None) -> float:
    """Menor range inteiro (cm, >= minimo) que seleciona pelo menos min_analogos anos.

    Se nem com range infinito há min_analogos anos elegíveis, retorna o range que
    inclui todos os elegíveis (ou o mínimo, se não houver nenhum).
    """
    r = calcular(doc, float("inf"), "cm", horizonte_meses)
    dists = sorted(
        abs(c["cota_em_d"] - r["cota_atual"])
        for c in r["candidatos"] if c["selecionado"]
    )
    if not dists:
        return minimo
    alvo = dists[min_analogos - 1] if len(dists) >= min_analogos else dists[-1]
    return max(minimo, float(math.ceil(alvo)))


def calcular(doc: dict, range_valor: float = 10.0, modo: str = "cm",
             horizonte_meses: int | None = None) -> dict:
    """Calcula a analogia sobre o JSON da estação.

    doc: dicionário no formato de docs/dados/{slug}.json.
    range_valor: meia-largura do range (cm se modo="cm", % se modo="pct").
    horizonte_meses: meses inteiros após o mês de D (None = até 31/dez).
    """
    anos = doc["anos"]
    d0 = date.fromisoformat(doc["ultima_data"])
    ano_atual = d0.year
    idx_d = indice_dia(d0.month, d0.day)
    cota_atual = float(anos[str(ano_atual)][idx_d])

    fim_iso = fim_horizonte(doc["ultima_data"], horizonte_meses)
    n_dias = (date.fromisoformat(fim_iso) - d0).days + 1
    datas = [d0 + timedelta(days=k) for k in range(n_dias)]

    limite = range_valor if modo == "cm" else abs(cota_atual) * range_valor / 100.0

    candidatos = []
    janelas = {}  # ano -> valores da janela (sem deslocamento)
    for chave in sorted(anos):
        ano = int(chave)
        if ano == ano_atual:
            continue
        desloc = ano - ano_atual
        cand = {
            "ano": ano, "cota_em_d": None, "dias_tolerancia": None,
            "cobertura": None, "min_pos_d": None, "delta": None,
            "max_pos_d": None, "subida": None,
            "dia_min_ciclo": None, "dia_max_ciclo": None,
            "selecionado": False, "motivo": None,
        }
        cota_d, desvio = _cota_em_d(anos, d0, desloc)
        if cota_d is None:
            cand["motivo"] = "sem dado no dia D"
            candidatos.append(cand)
            continue
        cand["cota_em_d"] = cota_d
        cand["dias_tolerancia"] = desvio

        analogas = [_data_analoga(t, desloc) for t in datas]
        valores = [_valor(anos, da) for da in analogas]
        pos = [k for k, da in enumerate(analogas) if da is not None]
        com_dado = [k for k in pos if valores[k] is not None]
        cand["cobertura"] = len(com_dado) / len(pos) if pos else 0.0
        if com_dado:
            minimo = min(valores[k] for k in com_dado)
            maximo = max(valores[k] for k in com_dado)
            cand["min_pos_d"] = minimo
            cand["delta"] = cota_d - minimo
            cand["max_pos_d"] = maximo
            cand["subida"] = maximo - cota_d

        if abs(cota_d - cota_atual) > limite:
            cand["motivo"] = "fora do intervalo"
            candidatos.append(cand)
            continue

        fim_janela = [k for k in com_dado if k >= n_dias - DIAS_FIM_JANELA]
        if cand["cobertura"] < COBERTURA_MINIMA or not fim_janela:
            cand["motivo"] = "série incompleta pós-D"
            candidatos.append(cand)
            continue

        cand["selecionado"] = True
        cand["dia_min_ciclo"], cand["dia_max_ciclo"] = _extremos_ciclo(anos, d0, desloc)
        candidatos.append(cand)
        janelas[ano] = valores

    selecionados = [c for c in candidatos if c["selecionado"]]

    resultado = {
        "ano_atual": ano_atual,
        "dia_d": doc["ultima_data"],
        "idx_d": idx_d,
        "cota_atual": cota_atual,
        "range_valor": range_valor,
        "modo": modo,
        "limite_cm": limite,
        "horizonte_meses": horizonte_meses,
        "fim_horizonte": fim_iso,
        "datas_proj": [t.isoformat() for t in datas],
        "candidatos": candidatos,
        "selecionados": [c["ano"] for c in selecionados],
        "regime": None,
        "ciclo": None,
        "ano_inferior": None,
        "criterio_inferior": None,
        "ano_superior": None,
        "criterio_superior": None,
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

    # regime pelo conjunto: data média do mínimo e do máximo dos ciclos
    ciclos = [c for c in selecionados if c["dia_min_ciclo"] is not None]
    regime = "descida"
    if ciclos:
        m_min, dp_min = _media_circular([c["dia_min_ciclo"] for c in ciclos])
        m_max, dp_max = _media_circular([c["dia_max_ciclo"] for c in ciclos])

        def proximo(m):
            return m if m > 0 else m + PERIODO_CICLO

        regime = "descida" if proximo(m_min) < proximo(m_max) else "subida"
        resultado["ciclo"] = {
            "n": len(ciclos),
            "media_min": m_min, "desvio_min": dp_min,
            "data_media_min": (d0 + timedelta(days=_arred(m_min))).isoformat(),
            "media_max": m_max, "desvio_max": dp_max,
            "data_media_max": (d0 + timedelta(days=_arred(m_max))).isoformat(),
        }

    def chave_queda(c):
        return (c["delta"], -c["subida"])

    def chave_subida(c):
        return (c["subida"], -c["delta"])

    if regime == "descida":
        inferior, crit_inf = max(selecionados, key=chave_queda), "maior_queda"
        superior, crit_sup = min(selecionados, key=chave_queda), "menor_queda"
    else:
        inferior, crit_inf = min(selecionados, key=chave_subida), "menor_subida"
        superior, crit_sup = max(selecionados, key=chave_subida), "maior_subida"
    resultado["regime"] = regime
    resultado["ano_inferior"] = inferior["ano"]
    resultado["criterio_inferior"] = crit_inf
    resultado["ano_superior"] = superior["ano"]
    resultado["criterio_superior"] = crit_sup

    # trajetórias deslocadas + interpoladas de todos os selecionados
    por_ano = {}
    for c in selecionados:
        offset = cota_atual - c["cota_em_d"]
        bruta = [None if v is None else v + offset for v in janelas[c["ano"]]]
        por_ano[c["ano"]] = _interpolar(bruta)

    media = [None] * n_dias
    for k in range(n_dias):
        vals = [t[0][k] for t in por_ano.values() if t[0][k] is not None]
        if vals:
            media[k] = sum(vals) / len(vals)

    resultado["trajetorias"] = {
        "inferior": por_ano[inferior["ano"]][0],
        "inferior_interp": por_ano[inferior["ano"]][1],
        "superior": por_ano[superior["ano"]][0],
        "superior_interp": por_ano[superior["ano"]][1],
        "media": media,
        "todas": {str(a): t[0] for a, t in por_ano.items()},
    }
    return resultado
