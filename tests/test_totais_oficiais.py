"""Confere os Parquets processados contra a totalização oficial do TSE."""

import httpx
import pandas as pd
import pytest

from boletim_urna import fontes

PROC = fontes.PROCESSADOS


@pytest.fixture(scope="module")
def votos():
    return pd.read_parquet(PROC / "votos_municipio.parquet", filters=[("cd_cargo", "==", 1)])


@pytest.fixture(scope="module")
def participacao():
    return pd.read_parquet(PROC / "participacao_municipio.parquet")


def _total(votos, ano, turno, nr):
    return votos.query("ano == @ano and nr_turno == @turno and nr_votavel == @nr").qt_votos.sum()


# Totalização oficial de Presidente (Brasil + exterior).
@pytest.mark.parametrize(
    "ano, turno, nr, esperado",
    [
        (2022, 1, 13, 57_259_504),
        (2022, 1, 22, 51_072_345),
        (2022, 2, 13, 60_345_999),
        (2022, 2, 22, 58_206_354),
        (2026, 2, 13, 64_256_232),
        (2026, 2, 22, 59_826_041),
    ],
)
def test_presidente_bate_com_totalizacao(votos, ano, turno, nr, esperado):
    assert _total(votos, ano, turno, nr) == esperado


def _nacional_api(ele: int) -> dict:
    url = f"{fontes.API_RESULTADOS}/ele2026/{ele}/dados/br/br-c0001-e{ele:06d}-u.json"
    return httpx.get(url, timeout=60).json()


@pytest.mark.parametrize("turno, ele", [(1, 6257), (2, 6258)])
def test_presidente_2026_csv_ou_api_bate_com_nacional_da_api(votos, participacao, turno, ele):
    """Onde CSV e API se sobrepõem (1º turno de 2026), os totais precisam coincidir."""
    nac = _nacional_api(ele)
    for agr in nac["carg"][0]["agr"]:
        for par in agr["par"]:
            for cand in par["cand"]:
                assert _total(votos, 2026, turno, int(cand["n"])) == int(cand["vap"]), cand["nmu"]
    p = participacao.query("ano == 2026 and nr_turno == @turno and cd_cargo == 1").sum(numeric_only=True)
    assert p.qt_aptos == int(nac["e"]["te"])
    assert p.qt_comparecimento == int(nac["e"]["c"])
    assert p.qt_votos_brancos == int(nac["v"]["vb"])
    assert p.qt_votos_nulos == int(nac["v"]["tvn"])


def test_municipios_tem_codigo_ibge_exceto_exterior():
    m = pd.read_parquet(PROC / "municipios.parquet")
    br = m[m.sg_uf != "ZZ"]
    assert len(br) == 5571  # 5.570 municípios + Boa Esperança do Norte (MT)
    assert br.cd_municipio_ibge.notna().all()


def test_participacao_fecha(participacao):
    p = participacao
    assert (p.qt_aptos == p.qt_comparecimento + p.qt_abstencoes + p.qt_eleitores_secoes_nao_instaladas).all()
    assert (p.qt_eleitores_secoes_nao_instaladas >= 0).all()
    # Em 2026 o Senado renovou 2/3: duas vagas, dois votos por eleitor.
    votos_por_eleitor = 1 + ((p.ano == 2026) & (p.cd_cargo == 5))
    total_votos = p.qt_votos_validos + p.qt_votos_brancos + p.qt_votos_nulos
    assert (p.qt_comparecimento * votos_por_eleitor >= total_votos).all()
