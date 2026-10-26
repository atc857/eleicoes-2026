"""Boletins de Urna (BU) do DF no 2º turno de 2026, decodificados da API de resultados.

Usado enquanto o TSE não publica o CSV por seção do 2º turno (decisão da etapa 4). Depois
disso, continua como conferência seção a seção contra o CSV oficial (`conferir_com_csv`).

Fluxo: lista de seções (config/df/df-p003221-cs.json) → índice de cada seção (aux.json,
que dá o hash e o nome do arquivo) → arquivo -bu.dat → envelope genérico → BU (ASN.1 BER,
especificação v2 em vendor/tse/bu_v2.asn1).
"""

import asyncio
import json
import logging
from functools import cache
from pathlib import Path

import asn1tools
import httpx
import pandas as pd

from . import fontes

log = logging.getLogger(__name__)

PLEITO_2T_2026 = 3221
BASE = f"{fontes.API_RESULTADOS}/ele2026/arquivo-urna/{PLEITO_2T_2026}"
CACHE = fontes.BRUTOS / "bu" / "2026" / str(PLEITO_2T_2026) / "df"
SPEC = fontes.RAIZ / "vendor" / "tse" / "bu_v2.asn1"
CONCORRENCIA = 6

CARGOS = {"presidente": 1, "governador": 3}
VOTAVEL_ESPECIAL = {"branco": 95, "nulo": 96}


@cache
def _asn1():
    return asn1tools.compile_files(str(SPEC), codec="ber")


def secoes() -> pd.DataFrame:
    """Seções do DF no pleito; as agregadas (sem arquivo próprio) apontam para a principal."""
    destino = CACHE / "cs.json"
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        resp = httpx.get(f"{BASE}/config/df/df-p{PLEITO_2T_2026:06d}-cs.json", timeout=60)
        resp.raise_for_status()
        destino.write_bytes(resp.content)
    dados = json.loads(destino.read_text(encoding="utf-8"))
    linhas = []
    for mu in dados["abr"][0]["mu"]:
        for zona in mu["zon"]:
            for s in zona["sec"]:
                linhas.append(
                    {"cd_municipio": mu["cd"], "nr_zona": int(zona["cd"]), "nr_secao": int(s["ns"]), "nr_secao_principal": int(s.get("nsp", s["ns"]))}
                )
    return pd.DataFrame(linhas)


def _pasta_secao(cd_municipio: str, zona: int, secao: int) -> str:
    return f"{BASE}/dados/df/{cd_municipio}/{zona:04d}/{secao:04d}"


async def _baixar_bu(cliente: httpx.AsyncClient, sem: asyncio.Semaphore, cd_municipio: str, zona: int, secao: int) -> Path:
    destino = CACHE / f"z{zona:04d}" / f"s{secao:04d}-bu.dat"
    if destino.exists():
        return destino
    pasta = _pasta_secao(cd_municipio, zona, secao)
    async with sem:
        for tentativa in range(4):
            try:
                aux = await cliente.get(
                    f"{pasta}/p{PLEITO_2T_2026:06d}-df-m{cd_municipio}-z{zona:04d}-s{secao:04d}-aux.json"
                )
                aux.raise_for_status()
                # o registro "Totalizado" é o que entrou na totalização (pode haver outro se a urna foi trocada)
                registros = aux.json()["hashes"]
                reg = next((h for h in registros if h["st"] == "Totalizado"), registros[-1])
                nome = next(a["nm"] for a in reg["arq"] if a["tp"] == "bu")
                resp = await cliente.get(f"{pasta}/{reg['hash']}/{nome}")
                resp.raise_for_status()
                break
            except (httpx.HTTPError, KeyError, StopIteration):
                if tentativa == 3:
                    raise
                await asyncio.sleep(2**tentativa)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(resp.content)
    return destino


async def _baixar_todos(principais: pd.DataFrame) -> list[Path]:
    sem = asyncio.Semaphore(CONCORRENCIA)
    async with httpx.AsyncClient(timeout=60) as cliente:
        return await asyncio.gather(
            *(_baixar_bu(cliente, sem, r.cd_municipio, r.nr_zona, r.nr_secao) for r in principais.itertuples())
        )


def decodificar(caminho: Path) -> dict:
    c = _asn1()
    envelope = c.decode("EntidadeEnvelopeGenerico", caminho.read_bytes())
    return c.decode("EntidadeBoletimUrna", envelope["conteudo"])


def _linhas(bu: dict, zona_esperada: int, secao_esperada: int):
    sec = bu["identificacaoSecao"]
    zona, secao, local = sec["municipioZona"]["zona"], sec["secao"], sec["local"]
    if (zona, secao) != (zona_esperada, secao_esperada):
        raise ValueError(f"BU da seção {zona}/{secao} veio na URL de {zona_esperada}/{secao_esperada}")
    votos, participacao = [], []
    for eleicao in bu["resultadosVotacaoPorEleicao"]:
        aptos = eleicao["qtdEleitoresAptos"]
        for resultado in eleicao["resultadosVotacao"]:
            comparecimento = resultado["qtdComparecimento"]
            for total in resultado["totaisVotosCargo"]:
                cd_cargo = CARGOS[total["codigoCargo"][1]]
                brancos = nulos = validos = 0
                for v in total["votosVotaveis"]:
                    qtd = v["quantidadeVotos"]
                    if v["tipoVoto"] == "nominal":
                        nr = v["identificacaoVotavel"]["codigo"]
                        validos += qtd
                    elif v["tipoVoto"] in VOTAVEL_ESPECIAL:
                        nr = VOTAVEL_ESPECIAL[v["tipoVoto"]]
                        brancos += qtd if v["tipoVoto"] == "branco" else 0
                        nulos += qtd if v["tipoVoto"] == "nulo" else 0
                    else:
                        raise ValueError(f"tipo de voto inesperado no 2º turno: {v['tipoVoto']}")
                    votos.append({"cd_cargo": cd_cargo, "nr_votavel": nr, "qt_votos": qtd})
                participacao.append(
                    {
                        "cd_cargo": cd_cargo,
                        "qt_aptos": aptos,
                        "qt_comparecimento": comparecimento,
                        "qt_abstencoes": aptos - comparecimento,
                        "qt_eleitores_secoes_nao_instaladas": 0,
                        "qt_votos_validos": validos,
                        "qt_votos_brancos": brancos,
                        "qt_votos_nulos": nulos,
                        "qt_votos_anulados": 0,
                    }
                )
    comum = {"nr_turno": 2, "nr_zona": zona, "nr_secao": secao, "nr_local": local}
    return [comum | l for l in votos], [comum | l for l in participacao]


def votos_e_participacao_por_secao() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Baixa (com cache) e decodifica todos os BUs do DF; uma linha por seção/cargo/votável."""
    secs = secoes()
    principais = secs[secs.nr_secao == secs.nr_secao_principal]
    caminhos = asyncio.run(_baixar_todos(principais))
    votos, participacao = [], []
    for r, caminho in zip(principais.itertuples(), caminhos):
        v, p = _linhas(decodificar(caminho), r.nr_zona, r.nr_secao)
        votos += v
        participacao += p
    return pd.DataFrame(votos).assign(ano=2026), pd.DataFrame(participacao).assign(ano=2026)


def conferir_com_csv(votos_csv: pd.DataFrame) -> pd.DataFrame:
    """Compara, seção a seção, os BUs decodificados com o CSV oficial do 2º turno (quando publicado).

    `votos_csv`: linhas do votacao_secao do DF no 2º turno de 2026 com nr_zona, nr_secao,
    cd_cargo, nr_votavel, qt_votos. Devolve só as divergências (vazio = tudo confere).
    """
    v_bu, _ = votos_e_participacao_por_secao()
    chave = ["nr_zona", "nr_secao", "cd_cargo", "nr_votavel"]
    a = v_bu.groupby(chave).qt_votos.sum().rename("qt_bu")
    b = votos_csv.groupby(chave).qt_votos.sum().rename("qt_csv")
    df = pd.concat([a, b], axis=1).fillna(0).astype("int64")
    return df[df.qt_bu != df.qt_csv].reset_index()
