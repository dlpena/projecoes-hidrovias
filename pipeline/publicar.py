"""Publica os artefatos do site: git add/commit/push apenas quando há mudança."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime

from pipeline import RAIZ

log = logging.getLogger(__name__)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8"
    )


def publicar() -> bool:
    """Retorna True se houve commit/push nesta rodada."""
    status = _git("status", "--porcelain", "--", "docs")
    if status.returncode != 0:
        raise RuntimeError(f"git status falhou: {status.stderr.strip()}")
    if not status.stdout.strip():
        log.info("Nada a publicar (docs/ sem mudanças).")
        # ainda pode haver commits acumulados de rodadas sem rede
        pendentes = _git("log", "--oneline", "@{u}..HEAD")
    else:
        add = _git("add", "docs")
        if add.returncode != 0:
            raise RuntimeError(f"git add falhou: {add.stderr.strip()}")
        msg = f"dados: atualização {datetime.now():%Y-%m-%d %H:%M}"
        commit = _git("commit", "-m", msg)
        if commit.returncode != 0:
            raise RuntimeError(f"git commit falhou: {commit.stderr.strip()}")
        log.info("Commit criado: %s", msg)
        pendentes = _git("log", "--oneline", "@{u}..HEAD")

    if pendentes.returncode != 0 or not pendentes.stdout.strip():
        # sem upstream configurado ou nada pendente
        if pendentes.returncode != 0:
            log.warning("Sem upstream configurado — pulando push (%s).",
                        pendentes.stderr.strip().splitlines()[0] if pendentes.stderr else "")
        return False

    push = _git("push")
    if push.returncode != 0:
        log.warning("Push falhou (sem rede?): %s — commits ficam para a próxima rodada.",
                    push.stderr.strip().splitlines()[-1] if push.stderr else "")
        return False
    log.info("Push concluído (%d commit(s)).", len(pendentes.stdout.strip().splitlines()))
    return True
