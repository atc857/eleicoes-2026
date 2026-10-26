"""Comparação 2022 × 2026 de Presidente por município (e, depois, por RA no DF).

Gera data/processed/comparacao_presidente.parquet: uma linha por (unidade, turno),
com indicadores de cada ano (sufixos _2022/_2026) e as diferenças (prefixo d_).
Percentuais de candidatos/blocos sobre votos válidos; abstenção sobre aptos;
brancos e nulos sobre comparecimento. Diferenças em pontos percentuais.
"""

import pandas as pd
import yaml

from . import fontes

CONFIG_BLOCOS = fontes.RAIZ / "config" / "blocos.yaml"
PARTIDOS_PRINCIPAIS = ("PT", "PL")
LIMIAR_VIRADA_APERTADA = 5.0  # pp


def carregar_blocos() -> tuple[dict[int, dict[int, str]], dict[str, str]]:
    """{ano: {nr_votavel: bloco}} e os rótulos de exibição."""
    cfg = yaml.safe_load(CONFIG_BLOCOS.read_text(encoding="utf-8"))
    rotulos = cfg.pop("rotulos")
    por_ano = {int(ano): {nr: bloco for bloco, nrs in blocos.items() for nr in nrs} for ano, blocos in cfg.items()}
    return por_ano, rotulos


def indicadores_por_ano(votos: pd.DataFrame, participacao: pd.DataFrame, chave: str = "cd_municipio") -> pd.DataFrame:
    """Indicadores de Presidente por (ano, turno, unidade). `votos`/`participacao` já filtrados em cd_cargo == 1."""
    blocos, _ = carregar_blocos()
    v = votos.copy()
    v["bloco"] = [blocos.get(a, {}).get(n, "demais") for a, n in zip(v.ano, v.nr_votavel)]
    ids = ["ano", "nr_turno", "sg_uf", chave]

    validos = v.groupby(ids).qt_votos.sum().rename("qt_validos")
    por_partido = (
        v[v.sg_partido.isin(PARTIDOS_PRINCIPAIS)].pivot_table(index=ids, columns="sg_partido", values="qt_votos", aggfunc="sum")
    )
    por_bloco = v.pivot_table(index=ids, columns="bloco", values="qt_votos", aggfunc="sum")

    # vencedor e margem sobre o 2º colocado
    ordenado = v.sort_values("qt_votos", ascending=False)
    top = ordenado.groupby(ids).head(2).copy()
    top["pos"] = top.groupby(ids).cumcount()
    primeiro = top[top.pos == 0].set_index(ids)
    segundo = top[top.pos == 1].set_index(ids).qt_votos

    df = pd.DataFrame(validos)
    for p in PARTIDOS_PRINCIPAIS:
        df[f"pct_{p.lower()}"] = 100 * por_partido.get(p, 0).reindex(df.index).fillna(0) / df.qt_validos
    for b in por_bloco.columns:
        df[f"pct_bloco_{b}"] = 100 * por_bloco[b].reindex(df.index).fillna(0) / df.qt_validos
    df["vencedor_partido"] = primeiro.sg_partido
    df["vencedor_nome"] = primeiro.nm_votavel
    df["margem_pp"] = 100 * (primeiro.qt_votos - segundo.reindex(primeiro.index).fillna(0)) / df.qt_validos
    # seções do exterior com poucos eleitores: sem votos válidos não há vencedor; topo igualado é empate
    df.loc[df.margem_pp == 0, ["vencedor_partido", "vencedor_nome"]] = "EMPATE"
    df.loc[df.qt_validos == 0, ["vencedor_partido", "vencedor_nome", "margem_pp"]] = None
    # saldo PT − PL: positivo = PT à frente. É o que o mapa de "vencedor" pinta.
    df["saldo_pt_pl"] = df.pct_pt - df.pct_pl

    p = participacao.groupby(ids)[
        ["qt_aptos", "qt_comparecimento", "qt_abstencoes", "qt_votos_brancos", "qt_votos_nulos"]
    ].sum()
    df = df.join(p)
    df["pct_abstencao"] = 100 * df.qt_abstencoes / df.qt_aptos
    df["pct_brancos"] = 100 * df.qt_votos_brancos / df.qt_comparecimento
    df["pct_nulos"] = 100 * df.qt_votos_nulos / df.qt_comparecimento
    df["fonte"] = votos.groupby(ids).fonte.first()
    return df.reset_index()


def comparar(ind: pd.DataFrame, chave: str = "cd_municipio") -> pd.DataFrame:
    """Une 2022 e 2026 por (unidade, turno) e calcula as diferenças."""
    a, b = (ind[ind.ano == ano].drop(columns="ano") for ano in fontes.ANOS)
    df = a.merge(b, on=["nr_turno", "sg_uf", chave], how="outer", suffixes=("_2022", "_2026"))
    df["sem_comparacao"] = df.qt_validos_2022.isna() | df.qt_validos_2026.isna()

    metricas = ["pct_pt", "pct_pl", "saldo_pt_pl", "pct_abstencao", "pct_brancos", "pct_nulos"]
    metricas += sorted({c for c in ind.columns if c.startswith("pct_bloco_")})
    for m in metricas:
        df[f"d_{m}"] = df[f"{m}_2026"] - df[f"{m}_2022"]
    df["d_qt_aptos"] = df.qt_aptos_2026 - df.qt_aptos_2022
    df["d_pct_aptos"] = 100 * df.d_qt_aptos / df.qt_aptos_2022

    tem_vencedor = df.vencedor_partido_2022.notna() & df.vencedor_partido_2026.notna()
    df["virou"] = ~df.sem_comparacao & tem_vencedor & (df.vencedor_partido_2022 != df.vencedor_partido_2026)
    df["virada_apertada"] = df.virou & (
        (df.margem_pp_2022 < LIMIAR_VIRADA_APERTADA) | (df.margem_pp_2026 < LIMIAR_VIRADA_APERTADA)
    )
    return df


def processar() -> pd.DataFrame:
    filtro = [("cd_cargo", "==", 1)]
    votos = pd.read_parquet(fontes.PROCESSADOS / "votos_municipio.parquet", filters=filtro)
    participacao = pd.read_parquet(fontes.PROCESSADOS / "participacao_municipio.parquet", filters=filtro)
    municipios = pd.read_parquet(fontes.PROCESSADOS / "municipios.parquet")

    df = comparar(indicadores_por_ano(votos, participacao))
    df = df.merge(municipios[["cd_municipio", "cd_municipio_ibge", "nm_municipio"]], on="cd_municipio", how="left")
    df.to_parquet(fontes.PROCESSADOS / "comparacao_presidente.parquet", index=False)
    return df
