"""Fonte de último recurso: cotas diárias publicadas pela Marinha (CHN-6, Ladário).

O Centro de Hidrografia e Navegação do Oeste publica, em dias úteis (por volta de
07h50 de Brasília), um PDF por régua com as cotas diárias em metros do ano corrente
e dos cinco anteriores, uma página por ano (tabela dia × mês):

    https://assets.marinha.mil.br/chn-6/sites/www.marinha.mil.br.chn-6/files/PORTO%20MURTINHO_DD.pdf

`DD` é o dia do mês da publicação, e o arquivo é sobrescrito no mês seguinte; nem
todo dia tem arquivo novo. Como cada PDF traz a série inteira, basta achar, entre os
últimos dias, o de modificação mais recente.

Uso no pipeline: precedência consistido > bruto > telemetria > marinha, dia a dia —
a Marinha só preenche dias sem nenhum dado da ANA. Antes de usar, `verificar_zero`
confere que a régua da Marinha continua com o mesmo zero da estação da ANA
(mediana da diferença na sobreposição recente); se não, a fonte é descartada na rodada.

Validação inicial (13/10/2026, PORTO MURTINHO, 2021 a 06/09/2026, 2.070 dias em
comum): mediana da diferença ANA − Marinha = 0 cm em todos os anos, inclusive nos
anos de HIDRO consistido (2021–2023); média anual entre −0,4 e +0,9 cm. As diferenças
acima de 5 cm (85 dias) concentram-se em subidas rápidas (ex.: mar/2023), coerentes
com horário de leitura diferente, não com mudança de referência.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

from pipeline import DIR_CACHE

log = logging.getLogger(__name__)

BASE_URL = "https://assets.marinha.mil.br/chn-6/sites/www.marinha.mil.br.chn-6/files/"
DIAS_PROCURA = 10           # quantos dias para trás procurar o PDF mais recente
TIMEOUT_S = 60
JANELA_ZERO_DIAS = 365      # sobreposição usada na conferência do zero da régua
MIN_SOBREPOSICAO = 30       # dias em comum mínimos para a conferência valer
LIMITE_MEDIANA_CM = 3       # |mediana(ANA − Marinha)| acima disso => zero diferente
_UA = {"User-Agent": "HidroviasJoaquim/1.0 (pipeline ANA; leitura de cotas públicas)"}

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def _url(arquivo: str, dia: int) -> str:
    return BASE_URL + urllib.parse.quote(f"{arquivo}_{dia:02d}.pdf")


def _last_modified(url: str) -> datetime | None:
    req = urllib.request.Request(url, method="HEAD", headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            if r.status != 200 or "pdf" not in r.headers.get("Content-Type", ""):
                return None
            lm = r.headers.get("Last-Modified")
            return parsedate_to_datetime(lm) if lm else None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def localizar_pdf_recente(arquivo: str, hoje: date | None = None) -> tuple[str, datetime] | None:
    """URL e data de modificação do PDF mais recente entre os últimos DIAS_PROCURA dias."""
    hoje = hoje or date.today()
    melhores: list[tuple[datetime, str]] = []
    for k in range(DIAS_PROCURA):
        url = _url(arquivo, (hoje - timedelta(days=k)).day)
        lm = _last_modified(url)
        if lm is not None:
            melhores.append((lm, url))
    if not melhores:
        return None
    lm, url = max(melhores)
    return url, lm


def ler_pdf(caminho: Path) -> pd.DataFrame:
    """Tabela dia × mês do PDF -> DataFrame (data, valor em cm).

    Lê por coordenada: cada valor vai para o mês cujo cabeçalho está mais próximo no
    eixo x e para o dia cuja âncora (número na 1ª coluna) está mais próxima no eixo y.
    (O texto corrido desalinha as linhas com células vazias.)
    """
    import pdfplumber

    registros: list[tuple[date, float]] = []
    with pdfplumber.open(caminho) as pdf:
        for pg in pdf.pages:
            m = re.search(r"(\d{4})", pg.extract_text() or "")
            if not m:
                continue
            ano = int(m.group(1))
            ws = pg.extract_words()
            cab = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in ws if w["text"] in MESES}
            if len(cab) != 12:
                raise ValueError(f"PDF da Marinha {ano}: cabeçalho de meses inesperado {sorted(cab)}")
            y_cab = min(w["top"] for w in ws if w["text"] in MESES)
            corpo = [w for w in ws if w["top"] > y_cab + 2]
            x_dia = min(w["x0"] for w in corpo)
            ancoras = [w for w in corpo
                       if w["x0"] < x_dia + 15 and re.fullmatch(r"\d{1,2}", w["text"])]
            for w in corpo:
                if w in ancoras or not re.fullmatch(r"-?\d+,\d{2}", w["text"]):
                    continue
                a = min(ancoras, key=lambda a: abs(a["top"] - w["top"]))
                if abs(a["top"] - w["top"]) > 4:
                    continue  # rodapé (máx./médio/mín. do período)
                xc = (w["x0"] + w["x1"]) / 2
                mes = min(cab, key=lambda k: abs(cab[k] - xc))
                if abs(cab[mes] - xc) > 15:
                    raise ValueError(f"PDF da Marinha {ano}: valor {w['text']} fora das colunas")
                try:
                    d = date(ano, MESES.index(mes) + 1, int(a["text"]))
                except ValueError:
                    raise ValueError(f"PDF da Marinha: data inválida {a['text']}/{mes}/{ano}")
                registros.append((d, float(w["text"].replace(",", ".")) * 100))
    df = pd.DataFrame(registros, columns=["data", "valor"])
    if df["data"].duplicated().any():
        raise ValueError("PDF da Marinha: dia duplicado na leitura")
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values("data").reset_index(drop=True)


def buscar(slug: str, arquivo: str) -> pd.DataFrame | None:
    """Baixa (se mudou) e lê o PDF mais recente. Retorna None se indisponível.

    O PDF usado fica em dados/cache/{slug}_marinha.pdf, com URL e data de modificação
    em {slug}_marinha.json — proveniência de cada rodada.
    """
    achado = localizar_pdf_recente(arquivo)
    if achado is None:
        log.warning("%s: nenhum PDF da Marinha nos últimos %d dias.", slug, DIAS_PROCURA)
        return None
    url, lm = achado
    pdf_local = DIR_CACHE / f"{slug}_marinha.pdf"
    meta_local = DIR_CACHE / f"{slug}_marinha.json"
    meta_ant = {}
    if meta_local.exists():
        meta_ant = json.loads(meta_local.read_text(encoding="utf-8"))
    if not (pdf_local.exists() and meta_ant.get("url") == url
            and meta_ant.get("last_modified") == lm.isoformat()):
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            conteudo = r.read()
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        tmp = pdf_local.with_suffix(".tmp")
        tmp.write_bytes(conteudo)
        tmp.replace(pdf_local)
        meta_local.write_text(json.dumps({
            "url": url, "last_modified": lm.isoformat(),
            "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    df = ler_pdf(pdf_local)
    log.info("%s: Marinha %d dias até %s (PDF %s, modificado %s)", slug, len(df),
             df["data"].max().date(), url.rsplit("/", 1)[-1], lm.astimezone().strftime("%d/%m %H:%M"))
    return df


def verificar_zero(slug: str, integrada_ana: pd.DataFrame, df_marinha: pd.DataFrame) -> bool:
    """Confere que a régua da Marinha tem o mesmo zero da série da ANA.

    Usa os últimos JANELA_ZERO_DIAS de sobreposição. Sem sobreposição suficiente
    (ex.: ANA parada há mais de um ano), recorre a toda a sobreposição disponível.
    """
    ana = integrada_ana.set_index("data")["valor"]
    mar = df_marinha.set_index("data")["valor"]
    comum = ana.index.intersection(mar.index)
    if len(comum) < MIN_SOBREPOSICAO:
        log.warning("%s: só %d dias em comum ANA × Marinha — fonte da Marinha descartada.",
                    slug, len(comum))
        return False
    recente = comum[comum >= comum.max() - pd.Timedelta(days=JANELA_ZERO_DIAS)]
    if len(recente) >= MIN_SOBREPOSICAO:
        comum = recente
    dif = ana.loc[comum] - mar.loc[comum]
    mediana = float(dif.median())
    ok = abs(mediana) <= LIMITE_MEDIANA_CM
    (log.info if ok else log.error)(
        "%s: zero da régua ANA × Marinha — mediana %+.1f cm em %d dias (%s a %s)%s",
        slug, mediana, len(comum), comum.min().date(), comum.max().date(),
        "" if ok else f" > {LIMITE_MEDIANA_CM} cm: fonte da Marinha DESCARTADA nesta rodada",
    )
    return ok


def complementar(integrada_ana: pd.DataFrame, df_marinha: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta à série integrada da ANA os dias que só a Marinha tem (fonte 'marinha')."""
    faltam = df_marinha[~df_marinha["data"].isin(integrada_ana["data"])]
    if faltam.empty:
        return integrada_ana
    extra = faltam.assign(fonte="marinha")[["data", "valor", "fonte"]]
    return (pd.concat([integrada_ana, extra], ignore_index=True)
            .sort_values("data").reset_index(drop=True))
