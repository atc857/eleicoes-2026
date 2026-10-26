"""Carga de dados do painel, com cache do Streamlit."""

import json

import pandas as pd
import shapely
import streamlit as st

from .. import comparacao, fontes, unidades as _unidades

PROC = fontes.PROCESSADOS


@st.cache_data(show_spinner=False)
def unidades() -> pd.DataFrame:
    return pd.read_parquet(PROC / "unidades.parquet")


@st.cache_data(show_spinner=False)
def comparacao_presidente() -> pd.DataFrame:
    return pd.read_parquet(PROC / "comparacao_presidente.parquet")


@st.cache_data(show_spinner=False)
def votos_presidente() -> pd.DataFrame:
    """Votos de Presidente por unidade, com o DF por RA onde houver dado por seção."""
    return _unidades.sem_duplicar_df(pd.read_parquet(PROC / "votos_unidade.parquet", filters=[("cd_cargo", "==", 1)]))


@st.cache_data(show_spinner=False)
def indicadores_presidente() -> pd.DataFrame:
    """Formato longo (uma linha por ano/turno/unidade) — base da visão nacional."""
    participacao = _unidades.sem_duplicar_df(
        pd.read_parquet(PROC / "participacao_unidade.parquet", filters=[("cd_cargo", "==", 1)])
    )
    df = comparacao.indicadores_por_ano(votos_presidente(), participacao)
    return df.merge(unidades()[["cd_unidade", "nm_unidade", "id_geo", "tipo"]], on="cd_unidade", how="left")


@st.cache_data(show_spinner=False)
def votos_unidade(cd_unidade: str) -> pd.DataFrame:
    return pd.read_parquet(PROC / "votos_unidade.parquet", filters=[("cd_unidade", "==", cd_unidade)])


@st.cache_data(show_spinner=False)
def participacao_unidade(cd_unidade: str) -> pd.DataFrame:
    return pd.read_parquet(PROC / "participacao_unidade.parquet", filters=[("cd_unidade", "==", cd_unidade)])


@st.cache_data(show_spinner=False)
def geo_unidades() -> dict:
    return json.loads((PROC / "malha_unidades.geojson").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def limites_por_id() -> pd.DataFrame:
    """Bounding box de cada feição, para enquadrar o mapa no recorte escolhido."""
    feicoes = geo_unidades()["features"]
    return pd.DataFrame(
        [shapely.geometry.shape(f["geometry"]).bounds for f in feicoes],
        columns=["xmin", "ymin", "xmax", "ymax"],
        index=[f["id"] for f in feicoes],
    )
