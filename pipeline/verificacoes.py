"""Verificações automáticas de consistência da série exportada.

Motivação (caso ITACOATIARA, ago/2026): a estação teve três referências de
nível distintas e o problema só foi percebido visualmente — e mal — depois de
publicado. Um degrau sustentado de metros entre eras não é hidrologia, é
mudança de datum/régua, e precisa ser detectado mecanicamente a cada rodada,
não por inspeção de gráfico.

`detectar_saltos_referencia` compara a mediana anual de janelas de 3 anos
vizinhas ao longo da série exportada e alerta quando o degrau sustentado é
ANÔMALO PARA A PRÓPRIA ESTAÇÃO: excede max(300 cm, 4x a mediana dos degraus
ano-a-ano típicos dela). O limiar dinâmico evita falsos positivos climáticos
em rios de grande amplitude (cheia recorde do Madeira 2014 e recuperação da
seca de 2024 geram degraus reais de ~4-5 m ano a ano), preservando a detecção
dos degraus de datum de Itacoatiara (~6-11 m, contra variação típica de ~1-2 m).

O alerta é WARNING no log (não bloqueia a publicação): a decisão de cortar
(`ano_inicio` em estacoes.py) é humana e documentada.
"""

from __future__ import annotations

import logging
import statistics

log = logging.getLogger(__name__)

LIMIAR_CM = 300       # piso do limiar (degrau sustentado entre janelas de 3 anos)
FATOR_TIPICO = 4      # limiar dinâmico = FATOR x mediana dos |Δ| ano-a-ano da estação
MIN_DIAS_ANO = 300    # só anos ~completos: mediana de ano parcial (ex.: o corrente,
                      # só com a estação da cheia) é enviesada e gera alerta falso


def _medianas_anuais(anos: dict[str, list], min_dias: int = MIN_DIAS_ANO) -> dict[int, float]:
    medianas = {}
    for chave, serie in anos.items():
        valores = [v for v in serie if v is not None]
        if len(valores) >= min_dias:
            medianas[int(chave)] = statistics.median(valores)
    return medianas


def detectar_saltos_referencia(anos: dict[str, list],
                               limiar_cm: float = LIMIAR_CM) -> list[dict]:
    """Detecta degraus sustentados entre eras na matriz ano -> [366 valores].

    Retorna lista de alertas [{"entre": [anoA, anoB], "dif_mediana_cm": ...}],
    onde a fronteira anoA|anoB separa janelas de 3 anos cujas medianas diferem
    mais que o limiar. Fronteiras consecutivas do mesmo degrau são fundidas na
    de maior diferença.
    """
    medianas = _medianas_anuais(anos)
    ordem = sorted(medianas)
    if len(ordem) < 2:
        return []

    # limiar dinâmico: degraus ano-a-ano típicos da própria estação (só entre
    # anos de fato consecutivos — lacunas de décadas não entram na "típica")
    difs_tipicas = [abs(medianas[ordem[i + 1]] - medianas[ordem[i]])
                    for i in range(len(ordem) - 1) if ordem[i + 1] - ordem[i] <= 2]
    if difs_tipicas:
        limiar_cm = max(limiar_cm, FATOR_TIPICO * statistics.median(difs_tipicas))

    brutos = []  # (índice da fronteira em `ordem`, dif das janelas, salto ano-a-ano)
    for i in range(len(ordem) - 1):
        antes = [medianas[y] for y in ordem[max(0, i - 2):i + 1]]
        depois = [medianas[y] for y in ordem[i + 1:i + 4]]
        dif = statistics.median(depois) - statistics.median(antes)
        if abs(dif) >= limiar_cm:
            salto = medianas[ordem[i + 1]] - medianas[ordem[i]]
            brutos.append((i, dif, salto))

    # um degrau real dispara até 3 janelas consecutivas: agrupa fronteiras de
    # índice adjacente e fica com a de maior salto ano-a-ano (a fronteira real)
    alertas: list[dict] = []
    grupo: list[tuple] = []

    def fechar_grupo():
        if grupo:
            i, dif, _ = max(grupo, key=lambda g: (abs(g[2]), abs(g[1])))
            alertas.append({"entre": [ordem[i], ordem[i + 1]],
                            "dif_mediana_cm": round(dif)})

    for item in brutos:
        if grupo and item[0] > grupo[-1][0] + 1:
            fechar_grupo()
            grupo = []
        grupo.append(item)
    fechar_grupo()
    return alertas


def alertar_saltos(slug: str, anos: dict[str, list]) -> list[dict]:
    """Roda o detector e loga WARNING por alerta. Retorna os alertas."""
    alertas = detectar_saltos_referencia(anos)
    for a in alertas:
        log.warning(
            "%s: POSSÍVEL MUDANÇA DE REFERÊNCIA DE NÍVEL entre %d e %d "
            "(degrau sustentado de %+d cm na mediana anual). Verifique se é "
            "datum/régua e considere ano_inicio em estacoes.py.",
            slug, a["entre"][0], a["entre"][1], a["dif_mediana_cm"],
        )
    return alertas
