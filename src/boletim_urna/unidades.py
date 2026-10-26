"""Unidades geográficas do painel: municípios + (no DF) Regiões Administrativas.

As tabelas *_unidade.parquet trazem as linhas municipais de todo o país (inclusive o DF
inteiro, tipo "df") e as linhas por RA (tipo "ra") onde há dado por seção. Quem consome
escolhe a granularidade do DF com `sem_duplicar_df` (visão de um ano) ou
`df_comparavel` (comparação entre anos).
"""

import json

import pandas as pd

from . import fontes

PROC = fontes.PROCESSADOS
GRUPO = ["ano", "nr_turno", "cd_cargo"]
NOME_DF = "DISTRITO FEDERAL (TODO)"


def _municipais(tabela: str, municipios: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_parquet(PROC / f"{tabela}_municipio.parquet")
    df = df.merge(municipios[["cd_municipio", "cd_municipio_ibge", "nm_municipio"]], on="cd_municipio", how="left")
    eh_df = df.cd_municipio == fontes.CD_MUNICIPIO_DF
    df["tipo"] = eh_df.map({True: "df", False: "municipio"})
    df["nm_unidade"] = df.nm_municipio.where(~eh_df, NOME_DF)
    return df.rename(columns={"cd_municipio": "cd_unidade", "cd_municipio_ibge": "id_geo"}).drop(columns="nm_municipio")


def _ras(tabela: str, ras: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_parquet(PROC / f"{tabela}_ra.parquet").merge(ras[["cd_ra", "nm_ra", "id_geo"]], on="cd_ra", how="left")
    df["cd_unidade"] = df.id_geo.fillna("DF-RA00")
    df["nm_unidade"] = df.nm_ra.fillna("RA NÃO IDENTIFICADA")
    df["tipo"] = "ra"
    return df.drop(columns=["cd_ra", "nm_ra"])


def processar() -> None:
    municipios = pd.read_parquet(PROC / "municipios.parquet")
    ras = pd.read_parquet(PROC / "ras_df.parquet")
    for tabela in ("votos", "votos_partido", "participacao"):
        pd.concat([_municipais(tabela, municipios), _ras(tabela, ras)], ignore_index=True).to_parquet(
            PROC / f"{tabela}_unidade.parquet", index=False
        )

    lista = pd.concat(
        [
            municipios.assign(
                tipo=(municipios.cd_municipio == fontes.CD_MUNICIPIO_DF).map({True: "df", False: "municipio"}),
                nm_municipio=municipios.nm_municipio.where(municipios.cd_municipio != fontes.CD_MUNICIPIO_DF, NOME_DF),
            ).rename(columns={"cd_municipio": "cd_unidade", "cd_municipio_ibge": "id_geo", "nm_municipio": "nm_unidade"}),
            ras.assign(sg_uf="DF", tipo="ra", cd_unidade=ras.id_geo).rename(columns={"nm_ra": "nm_unidade"}).drop(columns="cd_ra"),
        ],
        ignore_index=True,
    )
    lista.to_parquet(PROC / "unidades.parquet", index=False)

    # malha única: municípios (id = código IBGE) + RAs (id = DF-RAnn)
    geo = json.loads((PROC / "malha_municipios.geojson").read_text(encoding="utf-8"))
    geo["features"] += json.loads((PROC / "malha_ras_df.geojson").read_text(encoding="utf-8"))["features"]
    (PROC / "malha_unidades.geojson").write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")


def _grupos_com_ra(df: pd.DataFrame, chaves: list[str]) -> pd.Index:
    return pd.MultiIndex.from_frame(df.loc[df.tipo == "ra", chaves].drop_duplicates())


def sem_duplicar_df(df: pd.DataFrame, chaves: list[str] = GRUPO) -> pd.DataFrame:
    """Para cada grupo (ano/turno/cargo): RAs se houver, senão o DF inteiro — nunca os dois."""
    com_ra = _grupos_com_ra(df, chaves)
    no_grupo = pd.MultiIndex.from_frame(df[chaves]).isin(com_ra)
    return df[~((df.tipo == "df") & no_grupo) & ~((df.tipo == "ra") & ~no_grupo)]


def df_comparavel(df: pd.DataFrame, chaves: list[str] = ("nr_turno", "cd_cargo")) -> pd.DataFrame:
    """Para comparar anos: RAs só nos turnos/cargos em que os dois anos têm RA; senão o DF inteiro."""
    chaves = list(chaves)
    anos_com_ra = df[df.tipo == "ra"].groupby(chaves).ano.nunique()
    completos = anos_com_ra[anos_com_ra == len(fontes.ANOS)].index
    no_grupo = pd.MultiIndex.from_frame(df[chaves]).isin(completos) if len(completos) else pd.Series(False, index=df.index).to_numpy()
    return df[~((df.tipo == "df") & no_grupo) & ~((df.tipo == "ra") & ~no_grupo)]
