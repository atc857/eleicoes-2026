"""Coerência da comparação 2022 × 2026 de Presidente."""

import pandas as pd
import pytest

from boletim_urna import fontes


@pytest.fixture(scope="module")
def cmp():
    return pd.read_parquet(fontes.PROCESSADOS / "comparacao_presidente.parquet")


def test_segundo_turno_so_tem_pt_e_pl(cmp):
    t2 = cmp[(cmp.nr_turno == 2) & ~cmp.sem_comparacao & (cmp.qt_validos_2022 > 0) & (cmp.qt_validos_2026 > 0)]
    for ano in fontes.ANOS:
        assert (t2[f"pct_pt_{ano}"] + t2[f"pct_pl_{ano}"]).round(9).eq(100).all()


def test_blocos_somam_100(cmp):
    for ano in fontes.ANOS:
        cols = [c for c in cmp.columns if c.startswith("pct_bloco_") and c.endswith(f"_{ano}")]
        ok = cmp[cmp[f"qt_validos_{ano}"] > 0]
        assert ok[cols].fillna(0).sum(axis=1).round(9).eq(100).all()


def test_virada_coerente(cmp):
    v = cmp[cmp.virou]
    assert (v.vencedor_partido_2022 != v.vencedor_partido_2026).all()
    assert not cmp[cmp.virada_apertada & ~cmp.virou].size


def test_todo_municipio_brasileiro_tem_par_exceto_os_novos(cmp):
    sem = cmp[cmp.sem_comparacao & (cmp.sg_uf != "ZZ")]
    assert set(sem.cd_unidade) == {"73709"}  # Boa Esperança do Norte (MT), criado após 2022
