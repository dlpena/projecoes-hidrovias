# Hidrovias Joaquim

Site estático (GitHub Pages, `docs/` na main) com projeções de cota por analogia para 6 estações
fluviométricas, alimentado por pipeline Python local agendado 2x/dia.

## Regras do projeto

- **Nunca reimplementar a conexão com o data lake da ANA.** Reusar `ana_datalake` e `ana_app.queries`
  do projeto `..\app bancos ANA` (o `pipeline/__init__.py` faz o `sys.path.insert`). Rodar sempre com o
  venv de lá: `[caminho local removido]\Scripts\python.exe`.
- Cota em **cm** (HIDRO e telemetria). Série integrada: consistido (nível 2) > bruto (nível 1) > telemetria,
  resolvida dia a dia (`compor_serie_integrada`).
- Nos pivots do HIDRO usar apenas `cota_data`/`cota_val` (`Data`/`Hora` estão quebradas no serverless)
  e `MediaDiaria=1`. Sempre filtrar estação + período (custo por dados escaneados).
- Cache incremental em `dados/cache/` (parquet consistido congelado + meta.json). O consistido não muda;
  bruto e telemetria são re-buscados a cada rodada a partir de `ultima_data_consistido+1`.
- O algoritmo de analogia existe em **dois espelhos que devem permanecer idênticos**:
  `pipeline/analogia.py` (fonte da verdade, usada no PDF) e `docs/js/analogia.js` (site, range dinâmico).
  Qualquer mudança de regra deve ser aplicada nos dois e coberta por `tests/test_analogia.py`.
- Front-end: HTML+JS puro, sem build, Plotly vendorizado em `docs/vendor/` (não usar CDN — o site deve
  ser autocontido para internalização na ANA).
- Estações: definidas apenas em `estacoes.py` (o site lê `docs/dados/indice.json` gerado dali).

## Comandos

- Atualização completa de uma estação: `atualizar.py --full --estacao itaituba`
- Rodada incremental normal (todas): `atualizar.py`
- Sem push / sem PDF: `--sem-push`, `--sem-pdf`
- Teste local do site: `python -m http.server` dentro de `docs/` (fetch não funciona via file://)
- Testes: `python -m pytest tests/ -q`
