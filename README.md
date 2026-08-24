# Hidrovias Joaquim — Projeções de cota por analogia

Site estático com projeções de nível d'água para 9 estações fluviométricas
(Itaituba, Abunã, Porto Velho, Humaitá, Tabatinga, Ladário, Porto Murtinho,
Itacoatiara e Manaus), alimentado pelo data lake da ANA via pipeline local.

## Como funciona

1. **Pipeline** (`atualizar.py`, agendado 2x/dia): busca as cotas no Azure Synapse
   da ANA (série integrada: HIDRO consistido > bruto > telemetria), de forma
   **incremental** — o histórico já consolidado fica congelado em
   `dados/cache/*.parquet` e cada rodada consulta só a janela recente.
2. Gera, por estação, `docs/dados/{estacao}_historico.json` (todos os anos
   anteriores ao corrente — só é regravado quando o conteúdo realmente muda) e
   `docs/dados/{estacao}_atual.json` (só o ano corrente, pequeno, sempre
   regravado a cada rodada). Isso permite que o navegador reaproveite o cache
   do histórico entre visitas, baixando de fato só o que mudou. Depois faz
   `git push` — o GitHub Pages (branch main, pasta `/docs`) publica o site.
3. **Site** (`docs/`): HTML+JS puro com Plotly e jsPDF vendorizados —
   `docs/js/dados.js` busca e mescla os dois arquivos de cada estação num único
   objeto, consumido igualmente pelas duas páginas do site:
   - **Projeções** (`index.html`): o cálculo da analogia roda no navegador, então
     o intervalo (± cm ou %) é ajustável com resposta imediata. Todas as
     exportações são geradas na hora, refletindo o que está na tela — PDF do
     conjunto (capa + todos os gráficos como visualizados), memória de cálculo em PDF
     por estação (parâmetros, cobertura por fonte, anos candidatos, projeções e
     série dia a dia) e CSV.
   - **Histórico completo** (`historico.html`): todos os anos de cada estação
     sobrepostos, com a média histórica e o ano vigente em destaque (valor mais
     recente marcado no gráfico).

## Metodologia da projeção

A partir do último dado do ano corrente (dia D), selecionam-se os anos históricos
cuja cota no mesmo dia/mês está dentro do intervalo escolhido em torno da cota
atual (inicial: o menor ≥50 cm com pelo menos 3 anos análogos; tolerância de ±3
dias quando falta o dado exato; exige-se ≥80% de cobertura entre D e 31/dez e dado
nos últimos 10 dias do ano). Desse universo saem 3 trajetórias até 31/dez,
deslocadas para coincidir com a cota atual: a do ano de **maior queda**
(cota em D − mínimo pós-D), a do de **menor queda** e a **média** de todos os
análogos. Com menos de 3 análogos o gráfico exibe aviso.

> Nota (rio Paraguai — Ladário e Porto Murtinho): a vazante pode se estender além
> de dezembro; como a projeção termina em 31/dez, o mínimo da estiagem pode
> ocorrer fora do horizonte projetado.

## Uso

```bash
# testes (inclui paridade Python <-> JS do algoritmo)
python -m pytest tests/ -q

# site local
python -m http.server --directory docs
```

A execução do pipeline (`atualizar.py`) requer acesso autenticado ao data lake
da ANA e ambiente interno — as instruções operacionais ficam em documentação
local, fora deste repositório.

## Internalização no ambiente ANA

A pasta `docs/` é 100% autocontida (sem CDN): para internalizar, basta copiá-la
para qualquer servidor web interno.
