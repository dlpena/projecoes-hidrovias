"""Única fonte da verdade das estações do projeto.

- estcodigo_telemetria: código do equipamento (ESTCODIGO / HORESTACAO em hidroInfoAna).
- codigo_hidroweb: código de 8 dígitos do HidroWeb (EstacaoCodigo nos pivots / ESTCODIGOADICIONAL).

Ordem da lista = ordem dos painéis no site (via indice.json): agrupada por rio,
de montante para jusante, seguindo o eixo Solimões/Amazonas com cada afluente
encaixado no ponto em que desemboca (Negro em Manaus, Madeira em Itacoatiara,
Tapajós em Santarém); a bacia do Paraguai, separada, fecha a lista.
"""

ESTACOES = [
    # --- Solimões / Amazonas ---
    {"slug": "tabatinga", "nome": "TABATINGA", "rio": "Solimões",
     "estcodigo_telemetria": 41469570, "codigo_hidroweb": 10100000},
    {"slug": "manaus", "nome": "MANAUS", "rio": "Negro",
     "estcodigo_telemetria": 30659600, "codigo_hidroweb": 14990000},
    # ano_inicio 2009: a estação teve TRÊS referências de nível distintas —
    # 1927-1944 lê ~4,5 m ABAIXO do datum atual (a relação Itacoatiara-Manaus,
    # com Manaus no mesmo datum desde 1902 como controle de clima, mudou
    # -447 cm entre as eras, consistente mês a mês), 1997-2007 lê ~8 m ACIMA
    # (era o "andar de cima" nos gráficos), e o datum atual entra no consistido
    # em mar/2008 (bruto realinha em 2010, telemetria em out/2010). 2009 é o
    # primeiro ano civil inteiro no datum atual; misturar eras quebraria a
    # média e a analogia. Recuperar 1927-1944 somando o offset é possível mas
    # não recomendado: incerteza de ±0,5-1 m, sazonalidade na relação e perda
    # de auditabilidade (dado oficial alterado por correção caseira).
    {"slug": "itacoatiara", "nome": "ITACOATIARA", "rio": "Amazonas",
     "estcodigo_telemetria": 30858250, "codigo_hidroweb": 16030000,
     "ano_inicio": 2009},
    # --- Madeira ---
    # ano_inicio 2014: com o enchimento da UHE Jirau (a partir de out/2012) a
    # estação passou a sofrer efeito de remanso — as mínimas de estiagem subiram
    # ~2,5-3 m de forma permanente (pré-2014: 520-740 cm; pós: 806+ cm), sem
    # mudança equivalente nas cheias. Níveis pré-Jirau não são comparáveis com
    # o regime atual; 2013 é ano de transição (enchimento) e também fica fora.
    {"slug": "abuna", "nome": "ABUNÃ", "rio": "Madeira",
     "estcodigo_telemetria": 94265212, "codigo_hidroweb": 15320002,
     "ano_inicio": 2014},
    {"slug": "porto-velho", "nome": "PORTO VELHO", "rio": "Madeira",
     "estcodigo_telemetria": 84863570, "codigo_hidroweb": 15400000},
    # ano_inicio 1968: a série 1931-1948 lê ~7-9 m ABAIXO da referência atual —
    # a relação Humaitá-Manaus (Manaus no mesmo datum desde 1902 como controle
    # de clima) mudou +922 cm entre as eras, separadas por lacuna de 18 anos
    # (1949-1967) que impede verificação por sobreposição. Degrau sustentado
    # dessa magnitude é mudança de régua/datum, não clima. A era 1968+ é
    # internamente consistente (consistido, bruto e telemetria concordam com
    # mediana de diferença 0 cm na sobreposição). 1967 é ano parcial (258 dias);
    # 1968 é o primeiro ano civil completo na referência atual.
    {"slug": "humaita", "nome": "HUMAITÁ", "rio": "Madeira",
     "estcodigo_telemetria": 73063010, "codigo_hidroweb": 15630000,
     "ano_inicio": 1968},
    # --- Tapajós ---
    {"slug": "itaituba", "nome": "ITAITUBA", "rio": "Tapajós",
     "estcodigo_telemetria": 41655580, "codigo_hidroweb": 17730000},
    # Telemetria: equipamento RHN 22454440 (15 min); o CotaOnline 22454441 não
    # tem leituras no data lake.
    {"slug": "santarem", "nome": "SANTARÉM", "rio": "Tapajós",
     "estcodigo_telemetria": 22454440, "codigo_hidroweb": 17900000},
    # --- Paraguai ---
    {"slug": "ladario", "nome": "LADÁRIO (BASE NAVAL)", "rio": "Paraguai",
     "estcodigo_telemetria": 190057360, "codigo_hidroweb": 66825000},
    {"slug": "porto-murtinho", "nome": "PORTO MURTINHO", "rio": "Paraguai",
     "estcodigo_telemetria": 214257560, "codigo_hidroweb": 67100000},
]

POR_SLUG = {e["slug"]: e for e in ESTACOES}
