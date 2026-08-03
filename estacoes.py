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
]

POR_SLUG = {e["slug"]: e for e in ESTACOES}
