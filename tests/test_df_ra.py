"""A soma das RAs tem de reproduzir exatamente o total municipal do DF."""

import json

import pandas as pd
import pytest

from boletim_urna import fontes

PROC = fontes.PROCESSADOS
DF = [("cd_municipio", "==", fontes.CD_MUNICIPIO_DF)]
IDS = ["ano", "nr_turno", "cd_cargo"]


def test_votos_por_candidato_batem_com_municipal():
    ra = pd.read_parquet(PROC / "votos_ra.parquet")
    mun = pd.read_parquet(PROC / "votos_municipio.parquet", filters=DF)
    chaves = ra[IDS].drop_duplicates()
    mun = mun.merge(chaves, on=IDS)  # só ano/turno/cargo que já têm dados por seção
    a = ra.groupby([*IDS, "nr_votavel"]).qt_votos.sum()
    b = mun.groupby([*IDS, "nr_votavel"]).qt_votos.sum()
    diff = a.sub(b, fill_value=0)
    assert (diff == 0).all(), diff[diff != 0]


def test_votos_de_legenda_batem_com_municipal():
    ra = pd.read_parquet(PROC / "votos_partido_ra.parquet")
    mun = pd.read_parquet(PROC / "votos_partido_municipio.parquet", filters=DF)
    mun = mun[mun.cd_cargo.isin([6, 8]) & (mun.qt_votos_legenda > 0)]
    a = ra.groupby([*IDS, "nr_partido"]).qt_votos_legenda.sum()
    b = mun.groupby([*IDS, "nr_partido"]).qt_votos_legenda.sum()
    diff = a.sub(b, fill_value=0)
    assert (diff == 0).all(), diff[diff != 0]


@pytest.mark.parametrize(
    "coluna",
    [
        "qt_aptos",
        "qt_comparecimento",
        "qt_abstencoes",
        "qt_votos_brancos",
        "qt_votos_nulos",
        "qt_votos_anulados",
        "qt_votos_validos",
    ],
)
def test_participacao_bate_com_municipal(coluna):
    ra = pd.read_parquet(PROC / "participacao_ra.parquet")
    mun = pd.read_parquet(PROC / "participacao_municipio.parquet", filters=DF).merge(ra[IDS].drop_duplicates(), on=IDS)
    a = ra.groupby(IDS)[coluna].sum()
    b = mun.groupby(IDS)[coluna].sum()
    assert a.equals(b.reindex(a.index)), pd.concat([a, b], axis=1, keys=["ra", "mun"])[a != b.reindex(a.index)]


def test_todos_os_locais_tem_ra():
    locais = pd.read_parquet(PROC / "locais_df.parquet")
    assert (locais.cd_ra != 0).all()


def test_malha_tem_37_ras():
    geo = json.loads((PROC / "malha_ras_df.geojson").read_text(encoding="utf-8"))
    assert len(geo["features"]) == 37


def test_unidades_sem_duplicar_preserva_totais_nacionais():
    from boletim_urna import unidades

    uni = unidades.sem_duplicar_df(pd.read_parquet(PROC / "votos_unidade.parquet", filters=[("cd_cargo", "==", 1)]))
    mun = pd.read_parquet(PROC / "votos_municipio.parquet", filters=[("cd_cargo", "==", 1)])
    a = uni.groupby(["ano", "nr_turno", "nr_votavel"]).qt_votos.sum()
    b = mun.groupby(["ano", "nr_turno", "nr_votavel"]).qt_votos.sum()
    assert a.equals(b)


def test_comparacao_df_nao_mistura_ra_e_df_inteiro():
    cmp = pd.read_parquet(PROC / "comparacao_presidente.parquet")
    df = cmp[cmp.sg_uf == "DF"]
    assert (df.groupby("nr_turno").tipo.nunique() == 1).all()
