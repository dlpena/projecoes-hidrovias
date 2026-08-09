"""Única fonte da verdade das estações do projeto.

- estcodigo_telemetria: código do equipamento (ESTCODIGO / HORESTACAO em hidroInfoAna).
- codigo_hidroweb: código de 8 dígitos do HidroWeb (EstacaoCodigo nos pivots / ESTCODIGOADICIONAL).
"""

ESTACOES = [
    {"slug": "itaituba", "nome": "ITAITUBA", "rio": "Tapajós",
     "estcodigo_telemetria": 41655580, "codigo_hidroweb": 17730000},
    {"slug": "abuna", "nome": "ABUNÃ", "rio": "Madeira",
     "estcodigo_telemetria": 94265212, "codigo_hidroweb": 15320002},
    {"slug": "porto-velho", "nome": "PORTO VELHO", "rio": "Madeira",
     "estcodigo_telemetria": 84863570, "codigo_hidroweb": 15400000},
    {"slug": "tabatinga", "nome": "TABATINGA", "rio": "Solimões",
     "estcodigo_telemetria": 41469570, "codigo_hidroweb": 10100000},
    {"slug": "ladario", "nome": "LADÁRIO (BASE NAVAL)", "rio": "Paraguai",
     "estcodigo_telemetria": 190057360, "codigo_hidroweb": 66825000},
    {"slug": "porto-murtinho", "nome": "PORTO MURTINHO", "rio": "Paraguai",
     "estcodigo_telemetria": 214257560, "codigo_hidroweb": 67100000},
    # ano_inicio 1997: a era 1927-1944 usa outra referência de nível (zero da
    # régua ~9 m abaixo da atual — máximas de ~1.100 cm vs ~2.100 cm na era
    # moderna). Misturar as duas eras quebraria a média e a analogia.
    {"slug": "itacoatiara", "nome": "ITACOATIARA", "rio": "Amazonas",
     "estcodigo_telemetria": 30858250, "codigo_hidroweb": 16030000,
     "ano_inicio": 1997},
    {"slug": "manaus", "nome": "MANAUS", "rio": "Negro",
     "estcodigo_telemetria": 30659600, "codigo_hidroweb": 14990000},
]

POR_SLUG = {e["slug"]: e for e in ESTACOES}
