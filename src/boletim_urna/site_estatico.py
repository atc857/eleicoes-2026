"""Exporta os dados do site estático (site/dados/).

O navegador só filtra e pinta; o que dá para calcular antes é calculado aqui. JSON colunar: as listas
de participação são alinhadas a `cd`; votos são esparsos, `[[índices em cd], [votos]]`, só onde houve voto.

- unidades.json, malha.json, ufs.json — unidades, polígonos (id = id_geo) e contornos das UFs
- indice.json — corridas disponíveis (cargo/ano/turno) e UFs com arquivo de candidatos
- c{cargo}_{ano}_{turno}.json — participação por unidade + candidatos (majoritários) ou partidos (proporcionais)
- c{cargo}_{ano}_{turno}_{UF}.json — candidatos a deputado da UF (carregado ao escolher a UF)
- ficha_{UF}.json — participação de todos os cargos e os mais votados de cada cargo, por unidade

Deputado Distrital (8) entra como cargo 7, "Deputado Estadual/Distrital". Votos anulados ficam de fora:
os percentuais são sobre válidos, e candidatos + legenda conferem com qt_votos_validos (teste).
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

import pandas as pd
import shapely

from . import comparacao, fontes
from . import unidades as _unidades

PROC = fontes.PROCESSADOS
SITE = fontes.RAIZ / "site"
DADOS = SITE / "dados"
CARGOS = {1: "Presidente", 3: "Governador", 5: "Senador", 6: "Deputado Federal", 7: "Deputado Estadual/Distrital"}
PROPORCIONAIS = {6, 7}
TOP_FICHA = 10
PARTICIPACAO = {
    "aptos": "qt_aptos",
    "comparecimento": "qt_comparecimento",
    "abstencoes": "qt_abstencoes",
    "brancos": "qt_votos_brancos",
    "nulos": "qt_votos_nulos",
    "validos": "qt_votos_validos",
}
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "d"}


def _gravar(nome: str, obj) -> None:
    (DADOS / nome).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def nome_proprio(texto: str) -> str:
    """'SÃO JOÃO DEL-REI' → 'São João Del-Rei'; preposições em minúscula ('Lula da Silva')."""
    palavras = re.split(r"(\s+|-)", str(texto).strip().lower())
    return "".join(p if p in _MINUSCULAS and i else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def situacao(texto) -> str:
    """'ELEITO POR QP' → 'Eleito por QP'; vazio (API, antes do CSV) → ''."""
    if not isinstance(texto, str) or texto.startswith("#"):
        return ""
    return texto.capitalize().replace(" qp", " QP")


# --- malha -------------------------------------------------------------------


def _aneis(geometria: dict):
    poligonos = [geometria["coordinates"]] if geometria["type"] == "Polygon" else geometria["coordinates"]
    for poligono in poligonos:
        yield from poligono


def _contornos_uf(feicoes: list[dict], uf_por_geo: dict) -> tuple[list[dict], dict]:
    """Contorno de cada UF (linha grossa no mapa) e seu enquadramento.

    União de polígonos falha nesta malha (arredondada, com polígonos inválidos), então o contorno sai
    da topologia: segmento usado por uma só unidade da UF é borda da UF. A simplificação por cobertura
    mantém as bordas compartilhadas idênticas, o que faz a contagem funcionar.
    """
    segmentos: dict[str, Counter] = defaultdict(Counter)
    for f in feicoes:
        uf = uf_por_geo[f["id"]]
        for anel in _aneis(f["geometry"]):
            for a, b in zip(anel, anel[1:]):
                segmentos[uf][tuple(sorted((tuple(a), tuple(b))))] += 1
    contornos, limites = [], {}
    for uf, contagem in sorted(segmentos.items()):
        borda = shapely.line_merge(shapely.MultiLineString([s for s, n in contagem.items() if n == 1]))
        contornos.append({"type": "Feature", "properties": {"uf": uf}, "geometry": json.loads(shapely.to_geojson(borda))})
        limites[uf] = [round(x, 3) for x in borda.bounds]
    return contornos, limites


def _unidades_e_malha() -> None:
    """Grava unidades.json, malha.json e ufs.json; o DF entra só pelas RAs (todas as corridas têm dado por seção)."""
    u = pd.read_parquet(PROC / "unidades.parquet")
    u = u[u.tipo != "df"].reset_index(drop=True)

    malha = json.loads((PROC / "malha_unidades.geojson").read_text(encoding="utf-8"))
    uf_por_geo = dict(zip(u.id_geo.dropna(), u.sg_uf[u.id_geo.notna()]))
    feicoes = [f for f in malha["features"] if f["id"] in uf_por_geo]
    _gravar(
        "malha.json",
        {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"g": f["id"]}, "geometry": f["geometry"]} for f in feicoes]},
    )
    contornos, limites = _contornos_uf(feicoes, uf_por_geo)
    _gravar("ufs.json", {"type": "FeatureCollection", "features": contornos})
    _gravar(
        "unidades.json",
        {
            "cd": u.cd_unidade.tolist(),
            "g": [g if isinstance(g, str) else None for g in u.id_geo],  # exterior não tem polígono
            "nome": u.nm_unidade.map(nome_proprio).tolist(),
            "uf": u.sg_uf.tolist(),
            "tipo": u.tipo.tolist(),
            "limites_uf": limites,
        },
    )


# --- resultados ----------------------------------------------------------------


def _ler(tabela: str, cargos: list[int], colunas: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(PROC / f"{tabela}.parquet", filters=[("cd_cargo", "in", cargos)], columns=colunas)
    df = _unidades.sem_duplicar_df(df)
    return df.assign(cd_cargo=df.cd_cargo.replace({8: 7}))


def _esparso(df: pd.DataFrame, chave: str, ordem: list) -> list[list[list[int]]]:
    """Uma entrada por item de `ordem`: [[índices], [votos]] das unidades com voto (`df` tem `k` e `qt`)."""
    grupos = {c: g for c, g in df[df.qt > 0].sort_values("k").groupby(chave, sort=False)}
    vazio = pd.DataFrame({"k": [], "qt": []})
    return [[grupos.get(c, vazio).k.astype(int).tolist(), grupos.get(c, vazio).qt.astype(int).tolist()] for c in ordem]


def _candidatos(v: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por candidato da corrida (chave: UF da disputa + número), mais votado primeiro."""
    return (
        v.groupby(["uf_disputa", "nr_votavel"])
        .agg(nome=("nm_votavel", "first"), partido=("sg_partido", "first"), situacao=("ds_situacao", "first"), total=("qt_votos", "sum"))
        .sort_values("total", ascending=False)
        .reset_index()
    )


def _lista_candidatos(cand: pd.DataFrame, com_uf: bool) -> list[dict]:
    return [
        {"nr": int(c.nr_votavel), "nome": nome_proprio(c.nome), "partido": c.partido, "situacao": situacao(c.situacao), "total": int(c.total)}
        | ({"uf": c.uf_disputa} if com_uf else {})
        for c in cand.itertuples()
    ]


def _corrida(cargo: int, ano: int, turno: int, v: pd.DataFrame, p: pd.DataFrame, leg: pd.DataFrame | None) -> dict:
    """Grava c{cargo}_{ano}_{turno}.json (e, nos proporcionais, um arquivo de candidatos por UF)."""
    p = p.groupby("cd_unidade")[list(PARTICIPACAO.values())].sum()
    cds = p.index.union(v.cd_unidade.unique())
    p = p.reindex(cds).fillna(0)
    k = pd.Series(range(len(cds)), index=cds)
    v = v.assign(k=v.cd_unidade.map(k).to_numpy(), qt=v.qt_votos)
    base = {"cargo": cargo, "ano": ano, "turno": turno, "fonte": sorted(v.fonte.dropna().unique().tolist()), "cd": cds.tolist()}
    base |= {campo: p[coluna].astype(int).tolist() for campo, coluna in PARTICIPACAO.items()}
    nome = f"c{cargo}_{ano}_{turno}"
    ufs_com_arquivo = []

    if cargo not in PROPORCIONAIS:
        cand = _candidatos(v)
        chaves = list(zip(cand.uf_disputa, cand.nr_votavel))
        v = v.assign(chave=list(zip(v.uf_disputa, v.nr_votavel)))
        _gravar(f"{nome}.json", base | {"candidatos": _lista_candidatos(cand, cargo != 1), "votos": _esparso(v, "chave", chaves)})
    else:
        # total do partido = nominais válidos dos candidatos + legenda (a tabela de partidos das RAs não traz nominais)
        nominais = v.groupby(["cd_unidade", "sg_partido"]).qt_votos.sum()
        legenda = leg.groupby(["cd_unidade", "sg_partido"]).qt_votos_legenda.sum()
        por_partido = nominais.add(legenda, fill_value=0).rename("qt").reset_index()
        por_partido["k"] = por_partido.cd_unidade.map(k)
        totais = por_partido.groupby("sg_partido").qt.sum().sort_values(ascending=False)
        totais = totais[totais > 0]
        eleitos = v[v.ds_situacao.fillna("").str.startswith("ELEITO")].drop_duplicates(["uf_disputa", "nr_votavel"])
        eleitos = eleitos.groupby(["sg_partido", "uf_disputa"]).size()
        federacao = leg.drop_duplicates("sg_partido").set_index("sg_partido").sg_federacao
        partidos = [
            {
                "sigla": s,
                "federacao": f if isinstance(f := federacao.get(s), str) and not f.startswith("#") else "",
                "total": int(t),
                "legenda": int(legenda.xs(s, level="sg_partido").sum()) if s in legenda.index.get_level_values(1) else 0,
                "eleitos": {uf: int(n) for uf, n in eleitos.get(s, pd.Series(dtype=int)).items()},
            }
            for s, t in totais.items()
        ]
        _gravar(f"{nome}.json", base | {"partidos": partidos, "votos": _esparso(por_partido, "sg_partido", list(totais.index))})
        for uf, vu in v.groupby("uf_disputa"):
            cds_uf = sorted(vu.cd_unidade.unique())
            ku = pd.Series(range(len(cds_uf)), index=cds_uf)
            vu = vu.assign(k=vu.cd_unidade.map(ku).to_numpy())
            cand = _candidatos(vu)
            _gravar(
                f"{nome}_{uf}.json",
                {"cd": cds_uf, "candidatos": _lista_candidatos(cand, False), "votos": _esparso(vu, "nr_votavel", cand.nr_votavel.tolist())},
            )
            ufs_com_arquivo.append(uf)

    resumo = {"cargo": cargo, "ano": ano, "turno": turno, "unidades": len(cds), "validos": int(p.qt_votos_validos.sum())}
    if ufs_com_arquivo:
        resumo["ufs"] = ufs_com_arquivo
    return resumo


def _ficha(votos: pd.DataFrame, participacao: pd.DataFrame) -> None:
    """ficha_{UF}.json: participação de cada corrida e os mais votados de cada cargo (exceto Presidente,
    que a página já tem inteiro), por unidade. Candidatos numa tabela por UF, referenciados por índice."""
    v = votos[votos.cd_cargo != 1]
    top = v[v.qt_votos > 0].sort_values("qt_votos", ascending=False).groupby(["cd_cargo", "ano", "nr_turno", "cd_unidade"]).head(TOP_FICHA)
    part = participacao.groupby(["sg_uf", "cd_unidade", "cd_cargo", "ano", "nr_turno"])[list(PARTICIPACAO.values())].sum().reset_index()
    for uf in sorted(set(part.sg_uf) - {"ZZ"}):
        tu = top[top.sg_uf == uf]
        cand = tu.drop_duplicates(["cd_cargo", "ano", "uf_disputa", "nr_votavel"])
        indice = {(r.cd_cargo, r.ano, r.nr_votavel): i for i, r in enumerate(cand.itertuples())}
        unidades: dict[str, dict] = defaultdict(lambda: {"part": [], "top": defaultdict(list)})
        for r in part[part.sg_uf == uf].itertuples(index=False):
            unidades[r.cd_unidade]["part"].append([int(r.cd_cargo), int(r.ano), int(r.nr_turno), *(int(getattr(r, c)) for c in PARTICIPACAO.values())])
        for r in tu.itertuples():
            unidades[r.cd_unidade]["top"][f"{r.cd_cargo}-{r.ano}-{r.nr_turno}"].append([indice[(r.cd_cargo, r.ano, r.nr_votavel)], int(r.qt_votos)])
        _gravar(
            f"ficha_{uf}.json",
            {
                "campos": ["cargo", "ano", "turno", *PARTICIPACAO],
                "candidatos": [[nome_proprio(c.nm_votavel), c.sg_partido, int(c.nr_votavel), situacao(c.ds_situacao)] for c in cand.itertuples()],
                "unidades": unidades,
            },
        )


def _resultados() -> list[dict]:
    colunas_votos = ["ano", "nr_turno", "cd_cargo", "sg_uf", "cd_unidade", "nr_votavel", "nm_votavel", "sg_partido",
                     "ds_situacao", "qt_votos", "ds_destinacao", "fonte", "tipo"]  # fmt: skip
    colunas_part = ["ano", "nr_turno", "cd_cargo", "sg_uf", "cd_unidade", "tipo", *PARTICIPACAO.values()]
    resumo, votos_ficha, part_ficha = [], [], []
    for cargos in ([1], [3], [5], [6], [7, 8]):
        votos = _ler("votos_unidade", cargos, colunas_votos)
        # anulados não são válidos; "Válido (legenda)" já está na legenda do partido
        destino = votos.ds_destinacao.fillna("")
        votos = votos[~destino.str.startswith("Anulado") & (destino != "Válido (legenda)")]
        votos = votos.assign(uf_disputa="BR" if cargos == [1] else votos.sg_uf)
        participacao = _ler("participacao_unidade", cargos, colunas_part)
        legenda = None
        if cargos[0] in PROPORCIONAIS:
            legenda = _ler("votos_partido_unidade", cargos, ["ano", "nr_turno", "cd_cargo", "cd_unidade", "sg_partido", "sg_federacao",
                                                              "qt_votos_legenda", "tipo"])  # fmt: skip
        for (cargo, ano, turno), p in participacao.groupby(["cd_cargo", "ano", "nr_turno"]):
            assert not (p.tipo == "df").any(), f"{cargo}/{ano}/{turno}: DF sem dado por RA; o site só tem a malha das RAs"
            filtro = lambda df: df[(df.cd_cargo == cargo) & (df.ano == ano) & (df.nr_turno == turno)]  # noqa: E731
            resumo.append(_corrida(int(cargo), int(ano), int(turno), filtro(votos), p, None if legenda is None else filtro(legenda)))
        votos_ficha.append(votos)
        part_ficha.append(participacao)
    _ficha(pd.concat(votos_ficha), pd.concat(part_ficha))
    return resumo


def exportar() -> list[dict]:
    DADOS.mkdir(parents=True, exist_ok=True)
    for antigo in DADOS.glob("*.json"):
        antigo.unlink()
    _unidades_e_malha()
    resumo = _resultados()
    _, rotulos = comparacao.carregar_blocos()
    _gravar(
        "indice.json",
        {
            "gerado_em": datetime.now().isoformat(timespec="minutes"),
            "cargos": {str(c): n for c, n in CARGOS.items()},
            "proporcionais": sorted(PROPORCIONAIS),
            "corridas": resumo,
            "limiar_virada_apertada": comparacao.LIMIAR_VIRADA_APERTADA,
            "rotulos_bloco": rotulos,
        },
    )
    return resumo
