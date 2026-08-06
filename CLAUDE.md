# Hidrovias Joaquim

Site estático (GitHub Pages, `docs/` na main) com projeções de cota por analogia para 8 estações
fluviométricas — ITAITUBA, ABUNÃ, PORTO VELHO, TABATINGA, LADÁRIO, PORTO MURTINHO, ITACOATIARA,
MANAUS —, alimentado por pipeline Python local agendado 2x/dia (10h e 14h).

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
  `pipeline/analogia.py` (fonte da verdade das regras, coberta por `tests/test_analogia.py`) e
  `docs/js/analogia.js` (site, intervalo dinâmico). O pipeline **não chama** `pipeline/analogia.py`
  em produção (só os testes) — desde que as exportações passaram a ser geradas no navegador, o
  módulo Python existe só para garantir paridade de regras com o JS.
- Front-end: HTML+JS puro, sem build, Plotly e jsPDF vendorizados em `docs/vendor/` (não usar CDN — o
  site deve ser autocontido para internalização na ANA).
- **Exportações (PDF do conjunto, memória de cálculo em PDF e CSV) são geradas no navegador**
  (`docs/js/exportar_pdf.js`) refletindo o intervalo ajustado pelo usuário — o pipeline não gera PDF.
- **Terminologia da UI: "Intervalo" (nunca "range")** em todo texto visível ao usuário — controles,
  avisos, CSV, memória de cálculo, PDF. Nomes internos de código (`range_valor`, `modo`, `rangeInicial`)
  continuam em inglês/português técnico, sem relação com o texto exibido.
- Estações: definidas apenas em `estacoes.py` (o site lê `docs/dados/indice.json` gerado dali).
- Projeto irmão `[projeto local]` (vazão da UHE Belo Monte Montante) reusa a mesma aparência/
  algoritmo — mudanças em `docs/css`, `docs/js/grafico.js` ou nas regras de `analogia.py`/`.js` devem
  ser espelhadas lá também (ver o CLAUDE.md de lá).

## Comandos

- Atualização completa de uma estação: `atualizar.py --full --estacao itaituba`
- Rodada incremental normal (todas): `atualizar.py`
- Sem push: `--sem-push`
- Teste local do site: `python -m http.server` dentro de `docs/` (fetch não funciona via file://)
- Testes: `python -m pytest tests/ -q`
