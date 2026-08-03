# Hidrovias Joaquim — Projeções de cota por analogia

Site estático com projeções de nível d'água para 6 estações fluviométricas
(Itaituba, Abunã, Porto Velho, Tabatinga, Ladário e Porto Murtinho), alimentado
pelo data lake da ANA via pipeline local.

## Como funciona

1. **Pipeline** (`atualizar.py`, agendado 2x/dia): busca as cotas no Azure Synapse
   da ANA (série integrada: HIDRO consistido > bruto > telemetria), de forma
   **incremental** — o histórico já consolidado fica congelado em
   `dados/cache/*.parquet` e cada rodada consulta só a janela recente.
2. Gera `docs/dados/{estacao}.json` (matriz ano × dia, cm) + `docs/pdf/projecoes.pdf`
   e faz `git push` — o GitHub Pages (branch main, pasta `/docs`) publica o site.
3. **Site** (`docs/`): HTML+JS puro com Plotly vendorizado — o cálculo da analogia
   roda no navegador, então o range (± cm ou %) é ajustável com resposta imediata.
   Cada gráfico exporta um CSV de memória de cálculo auditável.

## Metodologia da projeção

A partir do último dado do ano corrente (dia D), selecionam-se os anos históricos
cuja cota no mesmo dia/mês está dentro do range (default ±10 cm; tolerância de ±3
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
# rodada normal (incremental, todas as estações, com PDF e push)
python atualizar.py

# opções
python atualizar.py --full --estacao itaituba   # refaz o cache de uma estação
python atualizar.py --sem-pdf --sem-push        # só dados

# testes (inclui paridade Python <-> JS do algoritmo)
python -m pytest tests/ -q

# site local
python -m http.server --directory docs
```

O projeto usa o venv do "app bancos ANA" (`[caminho local removido]`), que tem a
conexão autenticada (Entra ID/MSAL) com o data lake. Se o token expirar, renove com:

```bash
python -c "from ana_datalake import connect; connect('hidro')"
```

## Agendamento (2x/dia)

```powershell
powershell -ExecutionPolicy Bypass -File agendamento\registrar_tarefa.ps1
```

Cria a tarefa `HidroviasJoaquim-Atualizar` (10:00 e 14:00). Requer usuário logado
(o token MSAL é do perfil). Logs em `logs\`.

## Internalização no ambiente ANA

A pasta `docs/` é 100% autocontida (sem CDN): para internalizar, basta copiá-la
para qualquer servidor web interno.
