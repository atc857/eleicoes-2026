"""Confere os JSON do site estático contra a totalização oficial e contra os válidos de cada corrida."""

import json

import pytest

from boletim_urna import site_estatico


@pytest.fixture(scope="module")
def dados():
    site_estatico.exportar()
    return site_estatico.DADOS


def _ler(dados, nome):
    return json.loads((dados / f"{nome}.json").read_text(encoding="utf-8"))


def _soma(votos):
    return sum(sum(v) for _, v in votos)


@pytest.mark.parametrize(
    "ano, turno, partido, esperado",
    [
        (2022, 2, "PT", 60_345_999),
        (2022, 2, "PL", 58_206_354),
        (2026, 2, "PT", 64_256_232),
        (2026, 2, "PL", 59_826_041),
    ],
)
def test_totais_presidente(dados, ano, turno, partido, esperado):
    d = _ler(dados, f"c1_{ano}_{turno}")
    j = next(i for i, c in enumerate(d["candidatos"]) if c["partido"] == partido)
    assert _soma([d["votos"][j]]) == esperado


def test_cada_corrida_fecha_com_os_validos(dados):
    """Majoritários: soma dos candidatos = válidos. Proporcionais: partidos (nominal + legenda) = válidos,
    e os candidatos de cada UF somam no máximo isso (o resto é legenda)."""
    indice = _ler(dados, "indice")
    assert len(indice["corridas"]) == 14
    for r in indice["corridas"]:
        d = _ler(dados, f"c{r['cargo']}_{r['ano']}_{r['turno']}")
        validos = sum(d["validos"])
        assert _soma(d["votos"]) == validos, r
        if r["cargo"] in indice["proporcionais"]:
            nominais = sum(_soma(_ler(dados, f"c{r['cargo']}_{r['ano']}_{r['turno']}_{uf}")["votos"]) for uf in r["ufs"])
            legenda = sum(p["legenda"] for p in d["partidos"])
            assert nominais + legenda == validos, r


def test_ficha_tem_todas_as_unidades_da_uf(dados):
    u = _ler(dados, "unidades")
    ficha = _ler(dados, "ficha_DF")
    ras = {cd for cd, uf in zip(u["cd"], u["uf"]) if uf == "DF"}
    assert ras - set(ficha["unidades"]) <= {"DF-RA36"}  # 26 de Setembro não tem local de votação
    plano = ficha["unidades"]["DF-RA01"]
    assert {"3-2022-1", "5-2026-1", "6-2026-1", "7-2026-1"} <= set(plano["top"])


def test_toda_unidade_com_poligono_esta_na_malha(dados):
    u = _ler(dados, "unidades")
    malha = _ler(dados, "malha")
    ids = {f["properties"]["g"] for f in malha["features"]}
    # Boa Esperança do Norte (MT) ainda não está na malha IBGE v3 (ver docs/decisoes.md)
    assert {g for g in u["g"] if g} - ids == {"5101837"}
    assert "DF" in u["limites_uf"] and len(u["limites_uf"]) == 27


def test_nome_proprio_e_situacao():
    assert site_estatico.nome_proprio("SÃO JOÃO DEL-REI") == "São João Del-Rei"
    assert site_estatico.nome_proprio("LUIZ INÁCIO LULA DA SILVA") == "Luiz Inácio Lula da Silva"
    assert site_estatico.situacao("ELEITO POR QP") == "Eleito por QP"
    assert site_estatico.situacao("#NULO#") == ""
