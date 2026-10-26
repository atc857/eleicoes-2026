"""Cliente da API de divulgação de resultados (resultados.tse.jus.br) — 2026.

Usada só onde o CSV oficial ainda não existe (2º turno de 2026). As respostas
brutas ficam em cache em data/raw/api/, então cada URL é buscada uma vez.
"""

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pandas as pd

from . import fontes

log = logging.getLogger(__name__)

CONCORRENCIA = 8
CACHE = fontes.BRUTOS / "api" / "2026"


def _int(valor) -> int:
    return int(valor) if valor not in (None, "") else 0


def url_municipios(ele: int) -> str:
    return f"{fontes.API_RESULTADOS}/ele2026/{ele}/config/mun-e{ele:06d}-cm.json"


def url_resultado(ele: int, uf: str, cd_municipio: str, cd_cargo: int) -> str:
    return (
        f"{fontes.API_RESULTADOS}/ele2026/{ele}/dados/{uf}/"
        f"{uf}{cd_municipio}-c{cd_cargo:04d}-e{ele:06d}-u.json"
    )


async def _buscar(cliente: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, destino: Path) -> dict:
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    async with sem:
        for tentativa in range(4):
            try:
                resp = await cliente.get(url)
                resp.raise_for_status()
                break
            except (httpx.HTTPError, httpx.TimeoutException):
                if tentativa == 3:
                    raise
                await asyncio.sleep(2**tentativa)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(resp.text, encoding="utf-8")
    return resp.json()


def municipios(ele: int) -> pd.DataFrame:
    """Municípios da eleição com códigos TSE e IBGE (`cdi`). Exterior (ZZ) vem sem código IBGE."""
    destino = CACHE / str(ele) / "config.json"
    dados = asyncio.run(_buscar_um(url_municipios(ele), destino))
    linhas = [
        {
            "sg_uf": abr["cd"].upper(),
            "cd_municipio": mu["cd"],
            "cd_municipio_ibge": mu.get("cdi") or None,
            "nm_municipio": mu["nm"],
        }
        for abr in dados["abr"]
        for mu in abr["mu"]
    ]
    return pd.DataFrame(linhas)


async def _buscar_um(url: str, destino: Path) -> dict:
    async with httpx.AsyncClient(timeout=60) as cliente:
        return await _buscar(cliente, asyncio.Semaphore(1), url, destino)


def _linhas_resultado(dados: dict, ele: int, sg_uf: str, cd_municipio: str):
    turno = int(dados["t"])
    votos, participacao = [], []
    for cargo in dados["carg"]:
        cd_cargo = int(cargo["cd"])
        for agr in cargo["agr"]:
            for par in agr["par"]:
                for cand in par["cand"]:
                    votos.append(
                        {
                            "sq_candidato": cand["sqcand"],
                            "nr_votavel": int(cand["n"]),
                            "nm_votavel": cand["nmu"],
                            "sg_partido": par["sg"],
                            "ds_coligacao": agr["com"],
                            "ds_situacao": cand["st"].upper(),
                            "qt_votos": _int(cand.get("vap")),
                            "qt_votos_nominais": _int(cand.get("vap")),
                            "ds_destinacao": cand.get("dvt"),
                            "cd_cargo": cd_cargo,
                        }
                    )
    e, v = dados["e"], dados["v"]
    participacao.append(
        {
            "qt_aptos": _int(e["te"]),
            "qt_comparecimento": _int(e["c"]),
            "qt_abstencoes": _int(e["a"]),
            "qt_eleitores_secoes_nao_instaladas": _int(e["te"]) - _int(e["c"]) - _int(e["a"]),
            "qt_votos_validos": _int(v["vv"]),
            "qt_votos_brancos": _int(v["vb"]),
            "qt_votos_nulos": _int(v["tvn"]),
            "qt_votos_anulados": _int(v.get("van")) + _int(v.get("vansj")),
            "cd_cargo": int(dados["carg"][0]["cd"]),
        }
    )
    comum = {"ano": 2026, "nr_turno": turno, "sg_uf": sg_uf, "cd_municipio": cd_municipio, "fonte": f"api:{ele}"}
    return [comum | l for l in votos], [comum | l for l in participacao]


async def _coletar(ele: int, cd_cargo: int, muns: pd.DataFrame):
    sem = asyncio.Semaphore(CONCORRENCIA)
    async with httpx.AsyncClient(timeout=60) as cliente:
        tarefas = [
            _buscar(
                cliente,
                sem,
                url_resultado(ele, r.sg_uf.lower(), r.cd_municipio, cd_cargo),
                CACHE / str(ele) / r.sg_uf.lower() / f"{r.cd_municipio}-c{cd_cargo:04d}.json",
            )
            for r in muns.itertuples()
        ]
        return await asyncio.gather(*tarefas)


def resultados_municipais(ele: int, cd_cargo: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Votos por candidato e participação de todos os municípios de uma eleição/cargo."""
    muns = municipios(ele)
    respostas = asyncio.run(_coletar(ele, cd_cargo, muns))
    votos, participacao = [], []
    for r, dados in zip(muns.itertuples(), respostas):
        v, p = _linhas_resultado(dados, ele, r.sg_uf, r.cd_municipio)
        votos += v
        participacao += p
    return pd.DataFrame(votos), pd.DataFrame(participacao)
