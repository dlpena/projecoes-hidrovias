"""Orquestrador do pipeline: fetch incremental -> série integrada -> JSONs -> push.

Os PDFs (conjunto e memórias de cálculo) são gerados no navegador, refletindo o
range ajustado pelo usuário — o pipeline só publica os dados.

Uso:
    atualizar.py [--full] [--estacao SLUG] [--sem-push] [--sem-login]

Login no data lake: o refresh token é renovado sozinho a cada rodada, mas o
tenant da ANA exige novo login interativo periodicamente (~60 dias). Para não
haver interrupção, a rodada agendada (que só roda com o usuário logado):
  - aos LIMIAR_RENOVACAO_DIAS do último login, abre o navegador para renovar
    proativamente (com aviso por notificação do Windows); se ninguém responder
    em TIMEOUT_LOGIN_S, a rodada segue com o token atual e tenta de novo na próxima;
  - se o token já expirou, faz a mesma tentativa em vez de só falhar.
`--sem-login` desliga isso (modo somente-cache, comportamento antigo).

Exit codes: 0 ok · 1 falha geral · 2 token expirado (renove com:
    python -c "from ana_datalake import connect; connect('hidro')")
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from pipeline import DIR_CACHE, DIR_DADOS_SITE, DIR_LOGS
from estacoes import ESTACOES, ESTACOES_REAIS, ESTACOES_SINTETICAS, POR_SLUG

LOCK = DIR_CACHE / ".lock"
LOCK_VALIDADE_S = 2 * 3600
LIMIAR_RENOVACAO_DIAS = 50   # tenant da ANA obriga novo login em ~60 dias (observado)
TIMEOUT_LOGIN_S = 5 * 60     # quanto o navegador fica aberto esperando o login

log = logging.getLogger("atualizar")


def configurar_log() -> None:
    DIR_LOGS.mkdir(parents=True, exist_ok=True)
    arquivo = DIR_LOGS / f"atualizar_{datetime.now():%Y%m}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(arquivo, encoding="utf-8")],
    )


def _processo_vivo(pid: int) -> bool:
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def adquirir_lock() -> bool:
    import os
    if LOCK.exists():
        idade = time.time() - LOCK.stat().st_mtime
        dono = None
        try:
            dono = int(LOCK.read_text(encoding="utf-8").split(";")[0])
        except (ValueError, OSError):
            pass
        if dono is not None and not _processo_vivo(dono):
            log.warning("Lock órfão (processo %d morto) — ignorando.", dono)
        elif idade < LOCK_VALIDADE_S:
            log.error("Outra rodada em andamento (lock com %.0f min). Abortando.", idade / 60)
            return False
        else:
            log.warning("Lock antigo (%.1f h) — ignorando.", idade / 3600)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(f"{os.getpid()};{datetime.now().isoformat()}", encoding="utf-8")
    return True


def mesclar_indice(resumos_novos: list[dict]) -> list[dict]:
    """Preserva no indice.json as estações não processadas nesta rodada."""
    existentes: dict[str, dict] = {}
    caminho = DIR_DADOS_SITE / "indice.json"
    if caminho.exists():
        for e in json.loads(caminho.read_text(encoding="utf-8")).get("estacoes", []):
            existentes[e["slug"]] = e
    for r in resumos_novos:
        existentes[r["slug"]] = r
    ordem = [e["slug"] for e in ESTACOES]
    return [existentes[s] for s in ordem if s in existentes]


def _pedir_login(motivo: str) -> bool:
    """Abre o navegador para login interativo (com aviso por toast) e espera até TIMEOUT_LOGIN_S."""
    from ana_datalake.auth import renovar_login_interativo
    from pipeline import notificar

    log.warning("%s — abrindo navegador para login (até %d min).", motivo, TIMEOUT_LOGIN_S // 60)
    notificar.toast(
        "Hidrovias Joaquim: login necessário",
        f"{motivo}. Conclua o login da ANA na janela do navegador (até {TIMEOUT_LOGIN_S // 60} min).",
    )
    ok = renovar_login_interativo(timeout=TIMEOUT_LOGIN_S)
    if ok:
        log.info("Login interativo concluído — token renovado.")
    else:
        log.warning("Login interativo não concluído (sem resposta ou cancelado).")
    return ok


def conectar(permitir_login: bool):
    """Conexão com o data lake, renovando o login no navegador quando preciso.

    Retorna None (e loga o erro) se não houver token e não for possível renovar.
    """
    from ana_datalake import connect
    from ana_datalake.auth import dias_desde_login

    if permitir_login:
        idade = dias_desde_login()
        if idade is not None and idade >= LIMIAR_RENOVACAO_DIAS:
            # Proativo: o token ainda funciona, mas está perto de o tenant exigir novo
            # login. Se ninguém responder, a rodada segue normalmente com o token atual.
            _pedir_login(f"Último login há {idade:.0f} dias")

    try:
        return connect("hidro", interactive=False)
    except Exception as exc:  # token expirado / sem cache MSAL
        if permitir_login and _pedir_login("Token do data lake expirou"):
            try:
                return connect("hidro", interactive=False)
            except Exception as exc2:
                exc = exc2
        log.error(
            "Falha de autenticação no Synapse: %s\n"
            "Renove o token com: python -c \"from ana_datalake import connect; connect('hidro')\"",
            exc,
        )
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", action="store_true", help="refaz o cache da(s) estação(ões) do zero")
    p.add_argument("--estacao", metavar="SLUG", help="processa só esta estação")
    p.add_argument("--sem-push", action="store_true")
    p.add_argument("--sem-login", action="store_true",
                   help="nunca abre o navegador: falha (exit 2) se o token do cache expirou")
    args = p.parse_args()

    configurar_log()
    if args.estacao and args.estacao not in POR_SLUG:
        log.error("Estação desconhecida: %s (válidas: %s)", args.estacao, ", ".join(POR_SLUG))
        return 1
    # Sintéticas nunca vão ao data lake: são recalculadas dos JSONs publicados
    # das bases depois do loop, em toda rodada. `--estacao <sintética>` só refaz
    # essa sintética, sem precisar de conexão/token.
    alvo = POR_SLUG[args.estacao] if args.estacao else None
    if alvo is None:
        alvos, sinteticas_alvo = ESTACOES_REAIS, ESTACOES_SINTETICAS
    elif alvo.get("tipo") == "sintetica":
        alvos, sinteticas_alvo = [], [alvo]
    else:
        alvos, sinteticas_alvo = [alvo], ESTACOES_SINTETICAS

    if not adquirir_lock():
        return 1
    try:
        conn = None
        if alvos:
            conn = conectar(permitir_login=not args.sem_login)
            if conn is None:
                return 2

        from pipeline import fetch, integrar, exportar_json, sinteticas

        resumos, falhas = [], []
        for est in alvos:
            try:
                df_hidro, df_tele = fetch.buscar_cotas(conn, est, full=args.full)
                integrada = integrar.serie_integrada(df_hidro, df_tele)
                if integrada.empty:
                    raise RuntimeError("série integrada vazia")
                resumos.append(exportar_json.exportar_estacao(est, integrada, df_hidro, df_tele))
                log.info("%s: JSON exportado (última data %s)", est["slug"], resumos[-1]["ultima_data"])
            except Exception:
                log.exception("%s: falha — mantendo JSON anterior", est["slug"])
                falhas.append(est["slug"])

        resumos_sint, falhas_sint = sinteticas.exportar_sinteticas(sinteticas_alvo)
        resumos.extend(resumos_sint)
        falhas.extend(falhas_sint)

        if resumos:
            exportar_json.exportar_indice(mesclar_indice(resumos))

        if resumos and not args.sem_push:
            try:
                from pipeline import publicar
                publicar.publicar()
            except ImportError:
                log.warning("publicar ainda não disponível — pulando push.")
            except Exception:
                log.exception("Falha na publicação — commits ficam para a próxima rodada.")

        if falhas:
            log.error("Rodada concluída com falhas: %s", ", ".join(falhas))
            return 1
        log.info("Rodada concluída com sucesso (%d estação(ões)).", len(resumos))
        return 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
