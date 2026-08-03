"""Pipeline de dados do Hidrovias Joaquim.

Injeta o projeto "app bancos ANA" no sys.path para reusar a infraestrutura de
conexão (ana_datalake) e as queries (ana_app.queries) — regra: nunca reimplementar.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP_BANCOS = RAIZ.parent / "app bancos ANA"

if str(APP_BANCOS) not in sys.path:
    sys.path.insert(0, str(APP_BANCOS))

DIR_CACHE = RAIZ / "dados" / "cache"
DIR_DOCS = RAIZ / "docs"
DIR_DADOS_SITE = DIR_DOCS / "dados"
DIR_PDF = DIR_DOCS / "pdf"
DIR_LOGS = RAIZ / "logs"
