"""Decodificador de Boletins de Urna (DF, 2º turno de 2026)."""

import pandas as pd
import pytest

from boletim_urna import bu, fontes


@pytest.fixture(scope="module")
def secoes():
    return bu.secoes()


def test_um_bu_por_secao_principal(secoes):
    principais = secoes[secoes.nr_secao == secoes.nr_secao_principal]
    arquivos = list(bu.CACHE.glob("z*/s*-bu.dat"))
    if not arquivos:
        pytest.skip("BUs ainda não baixados")
    assert len(arquivos) == len(principais)


def test_bu_decodificado_identifica_a_propria_secao():
    caminho = bu.CACHE / "z0001" / "s0001-bu.dat"
    if not caminho.exists():
        pytest.skip("BU de exemplo não baixado")
    votos, participacao = bu._linhas(bu.decodificar(caminho), 1, 1)
    assert {v["cd_cargo"] for v in votos} == {1, 3}
    with pytest.raises(ValueError):
        bu._linhas(bu.decodificar(caminho), 1, 2)


def test_soma_dos_bus_bate_com_totalizacao_do_df():
    """Prova completa: o DF é um município só, então a soma dos BUs = total oficial do DF."""
    ra = pd.read_parquet(fontes.PROCESSADOS / "participacao_ra.parquet").query("ano == 2026 and nr_turno == 2")
    if ra.empty or not ra.fonte.str.startswith("bu").all():
        pytest.skip("2º turno de 2026 do DF não vem dos BUs (CSV oficial já publicado)")
    mun = pd.read_parquet(
        fontes.PROCESSADOS / "participacao_municipio.parquet",
        filters=[("cd_municipio", "==", fontes.CD_MUNICIPIO_DF), ("ano", "==", 2026), ("nr_turno", "==", 2)],
    ).set_index("cd_cargo")
    soma = ra.groupby("cd_cargo")[mun.columns.intersection(ra.columns).drop(["ano", "nr_turno", "sg_uf", "fonte"], errors="ignore")].sum()
    for col in ["qt_aptos", "qt_comparecimento", "qt_abstencoes", "qt_votos_brancos", "qt_votos_nulos", "qt_votos_validos"]:
        assert soma[col].equals(mun.loc[soma.index, col]), col
