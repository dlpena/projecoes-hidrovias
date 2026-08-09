"""Única fonte da verdade das estações do projeto.

- estcodigo_telemetria: código do equipamento (ESTCODIGO / HORESTACAO em hidroInfoAna).
- codigo_hidroweb: código de 8 dígitos do HidroWeb (EstacaoCodigo nos pivots / ESTCODIGOADICIONAL).
"""

ESTACOES = [
    {"slug": "itaituba", "nome": "ITAITUBA", "rio": "Tapajós",
     "estcodigo_telemetria": 41655580, "codigo_hidroweb": 17730000},
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
    {"slug": "tabatinga", "nome": "TABATINGA", "rio": "Solimões",
     "estcodigo_telemetria": 41469570, "codigo_hidroweb": 10100000},
    {"slug": "ladario", "nome": "LADÁRIO (BASE NAVAL)", "rio": "Paraguai",
     "estcodigo_telemetria": 190057360, "codigo_hidroweb": 66825000},
    {"slug": "porto-murtinho", "nome": "PORTO MURTINHO", "rio": "Paraguai",
     "estcodigo_telemetria": 214257560, "codigo_hidroweb": 67100000},
    # ano_inicio 2009: a estação teve TRÊS referências de nível distintas —
    # 1927-1944 roda ~5 m ABAIXO do datum atual (mediana -497 cm na
    # climatologia mensal), 1997-2007 roda ~8 m ACIMA (era o "andar de cima"
    # nos gráficos), e o datum atual entra no consistido em mar/2008 (bruto
    # realinha em 2010, telemetria em out/2010). 2009 é o primeiro ano civil
    # inteiro no datum atual; misturar eras quebraria a média e a analogia.
    {"slug": "itacoatiara", "nome": "ITACOATIARA", "rio": "Amazonas",
     "estcodigo_telemetria": 30858250, "codigo_hidroweb": 16030000,
     "ano_inicio": 2009},
    {"slug": "manaus", "nome": "MANAUS", "rio": "Negro",
     "estcodigo_telemetria": 30659600, "codigo_hidroweb": 14990000},
]

POR_SLUG = {e["slug"]: e for e in ESTACOES}
