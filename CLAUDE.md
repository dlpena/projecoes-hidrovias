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
  `ano_inicio` por estação corta anos não comparáveis com o regime atual — hoje: ITACOATIARA 2009
  (três referências de nível distintas na história) e ABUNÃ 2014 (remanso da UHE Jirau elevou as
  mínimas ~3 m desde o enchimento). O racional de cada corte está comentado no próprio arquivo.
- **Sentinela de referência de nível** (`pipeline/verificacoes.py`): toda rodada compara medianas
  anuais em janelas de 3 anos e loga WARNING se houver degrau sustentado anômalo para a estação
  (max(300 cm, 4x o degrau ano-a-ano típico); só anos com ≥300 dias). Nasceu do caso Itacoatiara
  (ago/2026), em que um degrau de datum de ~8 m só foi percebido visualmente — e tarde. Se o
  alerta disparar, investigar fonte a fonte (consistido vs bruto vs telemetria em sobreposição)
  antes de decidir `ano_inicio`; degrau real de clima/regime não deve ser cortado sem análise.
- **JSON por estação é dividido em dois arquivos**: `{slug}_historico.json` (anos anteriores ao
  corrente; `exportar_json._gravar_se_mudou` só regrava se o conteúdo de fato mudou, para manter o
  blob git/ETag estável e o navegador reaproveitar cache) e `{slug}_atual.json` (só o ano corrente,
  sempre regravado). `docs/js/dados.js` busca e mescla os dois num único `doc` — todo código
  consumidor (`grafico.js`, `analogia.js`, `exportar_pdf.js`, `pagina_historico.js`) trabalha só com
  o `doc` mesclado, sem saber da divisão.
- Duas páginas no site: `index.html` (projeções por analogia, intervalo ajustável) e
  `historico.html` (série completa por estação com média histórica e ano vigente em destaque,
  sem controles/exportações).
- Projeto irmão `[projeto local]` (vazão da UHE Belo Monte Montante) reusa a mesma aparência/
  algoritmo — mudanças em `docs/css`, `docs/js/grafico.js` ou nas regras de `analogia.py`/`.js` devem
  ser espelhadas lá também (ver o CLAUDE.md de lá).

## Comandos

- Atualização completa de uma estação: `atualizar.py --full --estacao itaituba`
- Rodada incremental normal (todas): `atualizar.py`
- Sem push: `--sem-push`
- Teste local do site: `python -m http.server` dentro de `docs/` (fetch não funciona via file://)
- Testes: `python -m pytest tests/ -q`
