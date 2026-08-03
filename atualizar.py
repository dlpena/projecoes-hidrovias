"""Orquestrador do pipeline: fetch incremental -> série integrada -> JSONs -> PDF -> push.

Uso:
    atualizar.py [--full] [--estacao SLUG] [--sem-pdf] [--sem-push]

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
from estacoes import ESTACOES, POR_SLUG

LOCK = DIR_CACHE / ".lock"
LOCK_VALIDADE_S = 2 * 3600

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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", action="store_true", help="refaz o cache da(s) estação(ões) do zero")
    p.add_argument("--estacao", metavar="SLUG", help="processa só esta estação")
    p.add_argument("--sem-pdf", action="store_true")
    p.add_argument("--sem-push", action="store_true")
    args = p.parse_args()

    configurar_log()
    alvos = [POR_SLUG[args.estacao]] if args.estacao else ESTACOES
    if args.estacao and args.estacao not in POR_SLUG:
        log.error("Estação desconhecida: %s (válidas: %s)", args.estacao, ", ".join(POR_SLUG))
        return 1

    if not adquirir_lock():
        return 1
    try:
        from ana_datalake import connect
        try:
            conn = connect("hidro", interactive=False)
        except Exception as exc:  # token expirado / sem cache MSAL
            log.error(
                "Falha de autenticação no Synapse: %s\n"
                "Renove o token com: python -c \"from ana_datalake import connect; connect('hidro')\"",
                exc,
            )
            return 2

        from pipeline import fetch, integrar, exportar_json

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

        if resumos:
            exportar_json.exportar_indice(mesclar_indice(resumos))

        if resumos and not args.sem_pdf:
            try:
                from pipeline import gerar_pdf
                gerar_pdf.gerar()
                log.info("PDF gerado.")
            except ImportError:
                log.warning("gerar_pdf ainda não disponível — pulando PDF.")
            except Exception:
                log.exception("Falha na geração do PDF — seguindo sem ele.")

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
