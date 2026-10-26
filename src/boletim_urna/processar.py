"""Transforma os CSVs do TSE (e a API, onde falta CSV) em Parquet por município.

Tabelas geradas em data/processed/:
- municipios.parquet: de-para TSE → IBGE (exterior sem código IBGE)
- votos_municipio.parquet: votos nominais válidos por candidato, somados sobre zonas
  e voto em trânsito
- votos_partido_municipio.parquet: votos de legenda por partido (proporcionais)
- participacao_municipio.parquet: aptos, comparecimento, abstenções, válidos, brancos, nulos
"""

import logging
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

from . import api_tse, fontes

log = logging.getLogger(__name__)

TEMP = fontes.DADOS / "tmp"


def _extrair_brasil(dataset: str, ano: int) -> Path:
    """Extrai o CSV `_BRASIL` do zip (todas as UFs e cargos) para data/tmp/."""
    zip_path = fontes.caminho_bruto(dataset, ano)
    nome = f"{zip_path.stem}_BRASIL.csv"
    destino = TEMP / nome
    if not destino.exists():
        TEMP.mkdir(parents=True, exist_ok=True)
        log.info("extraindo %s", nome)
        with zipfile.ZipFile(zip_path) as z:
            z.extract(nome, TEMP)
    return destino


def _ler_csv(caminho: Path) -> str:
    # all_varchar evita que CD_MUNICIPIO perca o zero à esquerda; os casts ficam explícitos no SQL.
    return f"read_csv('{caminho.as_posix()}', delim=';', header=true, encoding='latin-1', all_varchar=true)"


def votos_candidato_csv(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    fonte = _ler_csv(_extrair_brasil("votacao_candidato_munzona", ano))
    return con.sql(f"""
        SELECT {ano} AS ano, NR_TURNO::INT AS nr_turno, CD_CARGO::INT AS cd_cargo, SG_UF AS sg_uf,
               lpad(CD_MUNICIPIO, 5, '0') AS cd_municipio,
               SQ_CANDIDATO AS sq_candidato, NR_CANDIDATO::INT AS nr_votavel,
               NM_URNA_CANDIDATO AS nm_votavel, SG_PARTIDO AS sg_partido,
               DS_COMPOSICAO_COLIGACAO AS ds_coligacao, DS_SIT_TOT_TURNO AS ds_situacao,
               sum(QT_VOTOS_NOMINAIS_VALIDOS::BIGINT)::BIGINT AS qt_votos,
               'csv' AS fonte
        FROM {fonte}
        GROUP BY ALL
    """).df()


def votos_partido_csv(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    fonte = _ler_csv(_extrair_brasil("votacao_partido_munzona", ano))
    return con.sql(f"""
        SELECT {ano} AS ano, NR_TURNO::INT AS nr_turno, CD_CARGO::INT AS cd_cargo, SG_UF AS sg_uf,
               lpad(CD_MUNICIPIO, 5, '0') AS cd_municipio,
               NR_PARTIDO::INT AS nr_partido, SG_PARTIDO AS sg_partido, SG_FEDERACAO AS sg_federacao,
               sum(QT_VOTOS_NOMINAIS_VALIDOS::BIGINT)::BIGINT AS qt_votos_nominais,
               sum(QT_TOTAL_VOTOS_LEG_VALIDOS::BIGINT)::BIGINT AS qt_votos_legenda,
               'csv' AS fonte
        FROM {fonte}
        GROUP BY ALL
    """).df()


def participacao_csv(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    fonte = _ler_csv(_extrair_brasil("detalhe_votacao_munzona", ano))
    return con.sql(f"""
        SELECT {ano} AS ano, NR_TURNO::INT AS nr_turno, CD_CARGO::INT AS cd_cargo, SG_UF AS sg_uf,
               lpad(CD_MUNICIPIO, 5, '0') AS cd_municipio,
               sum(QT_APTOS::BIGINT)::BIGINT AS qt_aptos,
               sum(QT_COMPARECIMENTO::BIGINT)::BIGINT AS qt_comparecimento,
               sum(QT_ABSTENCOES::BIGINT)::BIGINT AS qt_abstencoes,
               sum(QT_ELEITORES_SECOES_NAO_INSTALADAS::BIGINT)::BIGINT AS qt_eleitores_secoes_nao_instaladas,
               sum(QT_TOTAL_VOTOS_VALIDOS::BIGINT)::BIGINT AS qt_votos_validos,
               sum(QT_VOTOS_BRANCOS::BIGINT)::BIGINT AS qt_votos_brancos,
               sum(QT_TOTAL_VOTOS_NULOS::BIGINT)::BIGINT AS qt_votos_nulos,
               'csv' AS fonte
        FROM {fonte}
        GROUP BY ALL
    """).df()


def municipios() -> pd.DataFrame:
    """De-para TSE → IBGE a partir do config da API 2026 (1º turno federal lista todos os municípios)."""
    return api_tse.municipios(fontes.ELEICAO_2026[("federal", 1)])


def _falta_turno(df: pd.DataFrame, ano: int, turno: int) -> bool:
    return df.query("ano == @ano and nr_turno == @turno").empty


def _completar_com_api(votos: pd.DataFrame, participacao: pd.DataFrame):
    """Se o CSV de 2026 ainda não tem o 2º turno, completa com a API (Presidente e Governador)."""
    if not _falta_turno(participacao, 2026, 2):
        return votos, participacao
    log.info("2º turno de 2026 ausente no CSV: usando a API de resultados")
    extras_v, extras_p = [], []
    for escopo, cd_cargo in (("federal", 1), ("estadual", 3)):
        v, p = api_tse.resultados_municipais(fontes.ELEICAO_2026[(escopo, 2)], cd_cargo)
        extras_v.append(v)
        extras_p.append(p)
    return pd.concat([votos, *extras_v], ignore_index=True), pd.concat([participacao, *extras_p], ignore_index=True)


def processar(anos=fontes.ANOS) -> None:
    fontes.PROCESSADOS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    votos = pd.concat([votos_candidato_csv(con, a) for a in anos], ignore_index=True)
    partido = pd.concat([votos_partido_csv(con, a) for a in anos], ignore_index=True)
    participacao = pd.concat([participacao_csv(con, a) for a in anos], ignore_index=True)
    votos, participacao = _completar_com_api(votos, participacao)

    municipios().to_parquet(fontes.PROCESSADOS / "municipios.parquet", index=False)
    votos.to_parquet(fontes.PROCESSADOS / "votos_municipio.parquet", index=False)
    partido.to_parquet(fontes.PROCESSADOS / "votos_partido_municipio.parquet", index=False)
    participacao.to_parquet(fontes.PROCESSADOS / "participacao_municipio.parquet", index=False)
