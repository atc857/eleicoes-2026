"""Endereços das fontes oficiais (TSE e IBGE) e caminhos locais."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data"
BRUTOS = DADOS / "raw"
PROCESSADOS = DADOS / "processed"

ANOS = (2022, 2026)

CDN_ODSELE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
CKAN_TSE = "https://dadosabertos.tse.jus.br/api/3/action/package_show"
API_RESULTADOS = "https://resultados.tse.jus.br/oficial"

# Códigos de eleição da API de divulgação 2026 (config/ele-c.json).
ELEICAO_2026 = {
    ("federal", 1): 6257,
    ("federal", 2): 6258,
    ("estadual", 1): 6259,
    ("estadual", 2): 6260,
}

CARGOS = {
    1: "Presidente",
    3: "Governador",
    5: "Senador",
    6: "Deputado Federal",
    7: "Deputado Estadual",
    8: "Deputado Distrital",
}

# Datasets do Dados Abertos usados no nível municipal: {nome: padrão do arquivo}.
DATASETS_MUNZONA = {
    "votacao_candidato_munzona": "votacao_candidato_munzona_{ano}.zip",
    "votacao_partido_munzona": "votacao_partido_munzona_{ano}.zip",
    "detalhe_votacao_munzona": "detalhe_votacao_munzona_{ano}.zip",
    "consulta_cand": "consulta_cand_{ano}.zip",
}


def url_odsele(dataset: str, ano: int) -> str:
    return f"{CDN_ODSELE}/{dataset}/{DATASETS_MUNZONA[dataset].format(ano=ano)}"


def caminho_bruto(dataset: str, ano: int) -> Path:
    return BRUTOS / dataset / DATASETS_MUNZONA[dataset].format(ano=ano)
