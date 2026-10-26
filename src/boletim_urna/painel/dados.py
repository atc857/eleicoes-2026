"""Carga de dados do painel, com cache do Streamlit."""

import pandas as pd
import shapely
import streamlit as st

from .. import comparacao, fontes, malha

PROC = fontes.PROCESSADOS


@st.cache_data(show_spinner=False)
def municipios() -> pd.DataFrame:
    return pd.read_parquet(PROC / "municipios.parquet")


@st.cache_data(show_spinner=False)
def comparacao_presidente() -> pd.DataFrame:
    return pd.read_parquet(PROC / "comparacao_presidente.parquet")


@st.cache_data(show_spinner=False)
def indicadores_presidente() -> pd.DataFrame:
    """Formato longo (uma linha por ano/turno/unidade) — base da visão nacional."""
    filtro = [("cd_cargo", "==", 1)]
    votos = pd.read_parquet(PROC / "votos_municipio.parquet", filters=filtro)
    participacao = pd.read_parquet(PROC / "participacao_municipio.parquet", filters=filtro)
    df = comparacao.indicadores_por_ano(votos, participacao)
    return df.merge(municipios()[["cd_municipio", "cd_municipio_ibge", "nm_municipio"]], on="cd_municipio", how="left")


@st.cache_data(show_spinner=False)
def votos_presidente() -> pd.DataFrame:
    return pd.read_parquet(PROC / "votos_municipio.parquet", filters=[("cd_cargo", "==", 1)])


@st.cache_data(show_spinner=False)
def votos_municipio(cd_municipio: str) -> pd.DataFrame:
    return pd.read_parquet(PROC / "votos_municipio.parquet", filters=[("cd_municipio", "==", cd_municipio)])


@st.cache_data(show_spinner=False)
def participacao_municipio(cd_municipio: str) -> pd.DataFrame:
    return pd.read_parquet(PROC / "participacao_municipio.parquet", filters=[("cd_municipio", "==", cd_municipio)])


@st.cache_data(show_spinner=False)
def geo_municipios() -> dict:
    return malha.malha_municipios()


@st.cache_data(show_spinner=False)
def limites_por_id() -> pd.DataFrame:
    """Bounding box de cada feição, para enquadrar o mapa no recorte escolhido."""
    feicoes = geo_municipios()["features"]
    return pd.DataFrame(
        [shapely.geometry.shape(f["geometry"]).bounds for f in feicoes],
        columns=["xmin", "ymin", "xmax", "ymax"],
        index=[f["id"] for f in feicoes],
    )
