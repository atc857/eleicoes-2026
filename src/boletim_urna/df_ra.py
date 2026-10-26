"""Divisão do DF nas 37 Regiões Administrativas (malha atual da IDE-DF, aplicada aos dois anos).

Seção → local de votação (NR_ZONA + NR_LOCAL_VOTACAO, que vem no próprio arquivo de seção)
→ coordenada (cadastro de locais do TSE) → RA por ponto-em-polígono.
Locais sem coordenada herdam a do mesmo local (pelo nome) no outro ano; o que sobra vai
para "RA não identificada" (cd_ra = 0), que soma nos totais e fica fora do mapa.

Gera em data/processed/:
- ras_df.parquet (cd_ra, nm_ra, id_geo) e malha_ras_df.geojson
- locais_df.parquet (ano, nr_zona, nr_local, nm_local, lat, lon, cd_ra, origem_coord)
- votos_ra.parquet, votos_partido_ra.parquet, participacao_ra.parquet (mesmo formato das
  tabelas municipais, com cd_ra no lugar de cd_municipio)
"""

import json
import logging
import zipfile

import duckdb
import geopandas as gpd
import pandas as pd
import shapely

from . import bu, fontes
from .processar import TEMP

log = logging.getLogger(__name__)

RA_NAO_IDENTIFICADA = 0
TOLERANCIA = 0.0006  # graus, ~60 m: suficiente para a escala do DF
VOTAVEIS_ESPECIAIS = {95: "Branco", 96: "Nulo", 97: "Anulado"}


def _extrair(chave: str, ano: int, nome: str):
    destino = TEMP / nome
    if not destino.exists():
        TEMP.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(fontes.caminho_secao(chave, ano)) as z:
            z.extract(nome, TEMP)
    return destino


def _csv(caminho) -> str:
    return f"read_csv('{caminho.as_posix()}', delim=';', header=true, encoding='latin-1', all_varchar=true)"


def id_geo(cd_ra: int) -> str:
    return f"DF-RA{cd_ra:02d}"


# --- malha -------------------------------------------------------------------------------


def ras() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(fontes.BRUTOS / "df" / "regioes_administrativas.geojson")
    gdf = gdf.rename(columns={"ra_cira": "cd_ra", "ra_nome": "nm_ra"})[["cd_ra", "nm_ra", "geometry"]]
    gdf["cd_ra"] = gdf.cd_ra.astype(int)
    gdf["nm_ra"] = gdf.nm_ra.str.replace("AGUA QUENTE", "ÁGUA QUENTE")
    gdf["id_geo"] = gdf.cd_ra.map(id_geo)
    return gdf.sort_values("cd_ra").reset_index(drop=True)


def gravar_malha(gdf: gpd.GeoDataFrame) -> None:
    simplificada = shapely.coverage_simplify(gdf.geometry.values, TOLERANCIA)
    feicoes = [
        {"type": "Feature", "id": i, "properties": {}, "geometry": json.loads(shapely.to_geojson(g))}
        for i, g in zip(gdf.id_geo, simplificada)
    ]
    texto = json.dumps({"type": "FeatureCollection", "features": feicoes}, separators=(",", ":"))
    geo = json.loads(texto, parse_float=lambda s: round(float(s), 4))
    (fontes.PROCESSADOS / "malha_ras_df.geojson").write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")


# --- locais de votação --------------------------------------------------------------------


def _locais_tse(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    nome = f"eleitorado_local_votacao_{ano}_DF.csv" if ano >= 2026 else f"eleitorado_local_votacao_{ano}.csv"
    fonte = _csv(_extrair("eleitorado_local_votacao", ano, nome))
    return con.sql(f"""
        SELECT NR_ZONA::INT AS nr_zona, NR_LOCAL_VOTACAO::INT AS nr_local,
               any_value(NM_LOCAL_VOTACAO) AS nm_local,
               -- coordenada com vírgula decimal; -1 e #NULO# = ausente
               max(TRY_CAST(nullif(replace(NR_LATITUDE, ',', '.'), '-1') AS DOUBLE)) AS lat,
               max(TRY_CAST(nullif(replace(NR_LONGITUDE, ',', '.'), '-1') AS DOUBLE)) AS lon
        FROM {fonte}
        WHERE SG_UF = 'DF'
        GROUP BY ALL
    """).df()


def locais(con: duckdb.DuckDBPyConnection, malha: gpd.GeoDataFrame, anos=fontes.ANOS) -> pd.DataFrame:
    df = pd.concat([_locais_tse(con, a).assign(ano=a) for a in anos], ignore_index=True)
    df["origem_coord"] = df.lat.notna().map({True: "cadastro", False: None})

    # sem coordenada: herda do mesmo local (mesmo nome) em qualquer ano
    conhecidos = df.dropna(subset=["lat"]).groupby("nm_local")[["lat", "lon"]].first()
    faltam = df.lat.isna() & df.nm_local.isin(conhecidos.index)
    df.loc[faltam, ["lat", "lon"]] = conhecidos.loc[df.loc[faltam, "nm_local"]].to_numpy()
    df.loc[faltam, "origem_coord"] = "mesmo nome"

    pontos = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
    com_ponto = pontos[pontos.lat.notna()]
    dentro = gpd.sjoin(com_ponto, malha[["cd_ra", "geometry"]], how="left", predicate="within")
    df["cd_ra"] = dentro.cd_ra.reindex(df.index)
    # ponto na fronteira ou ligeiramente fora (erro de geocodificação): RA mais próxima até ~500 m
    fora = df.index[df.cd_ra.isna() & df.lat.notna()]
    if len(fora):
        proj = pontos.loc[fora].to_crs(31983)
        perto = gpd.sjoin_nearest(proj, malha[["cd_ra", "geometry"]].to_crs(31983), max_distance=500)
        perto = perto[~perto.index.duplicated()]
        df.loc[perto.index, "cd_ra"] = perto.cd_ra
    df["cd_ra"] = df.cd_ra.fillna(RA_NAO_IDENTIFICADA).astype(int)
    return df


# --- votos e participação ------------------------------------------------------------------


def _votos_secao(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    df_csv = _csv(_extrair("votacao_secao_df", ano, f"votacao_secao_{ano}_DF.csv"))
    br_csv = _csv(_extrair("votacao_secao_br", ano, f"votacao_secao_{ano}_BR.csv"))
    seletor = """
        SELECT NR_TURNO::INT AS nr_turno, CD_CARGO::INT AS cd_cargo, NR_ZONA::INT AS nr_zona,
               NR_LOCAL_VOTACAO::INT AS nr_local, NR_VOTAVEL::INT AS nr_votavel,
               sum(QT_VOTOS::BIGINT)::BIGINT AS qt_votos
        FROM {fonte} WHERE SG_UF = 'DF' GROUP BY ALL
    """
    return con.sql(f"{seletor.format(fonte=df_csv)} UNION ALL {seletor.format(fonte=br_csv)}").df().assign(ano=ano)


def _participacao_secao(con: duckdb.DuckDBPyConnection, ano: int) -> pd.DataFrame:
    # _DF traz os cargos estaduais; Presidente só está no _BR (todas as UFs)
    arquivos = [f"detalhe_votacao_secao_{ano}_DF.csv", f"detalhe_votacao_secao_{ano}_BR.csv"]
    fonte = "(" + " UNION ALL ".join(
        f"SELECT * FROM {_csv(_extrair('detalhe_votacao_secao', ano, a))} WHERE SG_UF = 'DF'" for a in arquivos
    ) + ")"
    return con.sql(f"""
        SELECT NR_TURNO::INT AS nr_turno, CD_CARGO::INT AS cd_cargo, NR_ZONA::INT AS nr_zona,
               NR_LOCAL_VOTACAO::INT AS nr_local,
               sum(QT_APTOS::BIGINT)::BIGINT AS qt_aptos,
               sum(QT_COMPARECIMENTO::BIGINT)::BIGINT AS qt_comparecimento,
               sum(QT_ABSTENCOES::BIGINT)::BIGINT AS qt_abstencoes,
               sum(QT_VOTOS_NOMINAIS::BIGINT + QT_VOTOS_LEGENDA::BIGINT)::BIGINT AS qt_votos_validos,
               sum(QT_VOTOS_BRANCOS::BIGINT)::BIGINT AS qt_votos_brancos,
               sum(QT_VOTOS_NULOS::BIGINT)::BIGINT AS qt_votos_nulos,
               -- seção não instalada: aptos sem comparecimento nem abstenção
               sum(CASE WHEN ST_SECAO_INSTALADA = 'Não' THEN QT_APTOS::BIGINT ELSE 0 END)::BIGINT
                   AS qt_eleitores_secoes_nao_instaladas
        FROM {fonte} GROUP BY ALL
    """).df().assign(ano=ano)


def _com_ra(df: pd.DataFrame, locais_df: pd.DataFrame) -> pd.DataFrame:
    mapa = locais_df[["ano", "nr_zona", "nr_local", "cd_ra"]]
    out = df.merge(mapa, on=["ano", "nr_zona", "nr_local"], how="left")
    out["cd_ra"] = out.cd_ra.fillna(RA_NAO_IDENTIFICADA).astype(int)
    return out


def _marcar_fonte_bu(df: pd.DataFrame, usa_bu: bool) -> pd.DataFrame:
    if usa_bu:
        df.loc[(df.ano == 2026) & (df.nr_turno == 2), "fonte"] = f"bu:{bu.PLEITO_2T_2026}"
    return df


def processar(anos=fontes.ANOS) -> None:
    con = duckdb.connect()
    malha = ras()
    gravar_malha(malha)
    malha.drop(columns="geometry").to_parquet(fontes.PROCESSADOS / "ras_df.parquet", index=False)

    locais_df = locais(con, malha, anos)
    locais_df.drop(columns="geometry", errors="ignore").to_parquet(fontes.PROCESSADOS / "locais_df.parquet", index=False)

    comum = {"sg_uf": "DF", "fonte": "csv:secao"}
    ids = ["ano", "nr_turno", "cd_cargo", "cd_ra"]

    votos_secao = pd.concat([_votos_secao(con, a) for a in anos], ignore_index=True)
    part_secao = pd.concat([_participacao_secao(con, a) for a in anos], ignore_index=True)
    # 2º turno de 2026 ainda sem CSV por seção: usa os Boletins de Urna decodificados
    usa_bu = 2026 in anos and votos_secao.query("ano == 2026 and nr_turno == 2").empty
    if usa_bu:
        log.info("2º turno de 2026 sem CSV por seção: decodificando os BUs do DF")
        v_bu, p_bu = bu.votos_e_participacao_por_secao()
        votos_secao = pd.concat([votos_secao, v_bu.drop(columns="nr_secao")], ignore_index=True)
        part_secao = pd.concat([part_secao, p_bu.drop(columns="nr_secao")], ignore_index=True)

    votos = _com_ra(votos_secao, locais_df)
    votos = votos.groupby([*ids, "nr_votavel"], as_index=False).qt_votos.sum()

    # Identidade e destino dos votos de cada candidato vêm da tabela municipal do DF:
    # - "Válido": voto nominal válido
    # - "Válido (legenda)": nominal que conta para a legenda do partido
    # - "Anulado" / "Anulado sub judice": categoria própria (não é nulo nem válido)
    # Número ausente da tabela municipal = candidatura com votos "nulos técnicos" (somam aos nulos),
    # exceto, nos proporcionais, número de 2 dígitos = voto de legenda.
    municipal = pd.read_parquet(
        fontes.PROCESSADOS / "votos_municipio.parquet", filters=[("cd_municipio", "==", fontes.CD_MUNICIPIO_DF)]
    )
    chave = ["ano", "nr_turno", "cd_cargo", "nr_votavel"]
    cand = municipal.drop_duplicates(chave)[
        [*chave, "sq_candidato", "nm_votavel", "sg_partido", "ds_coligacao", "ds_situacao", "ds_destinacao"]
    ]
    votos = votos[~votos.nr_votavel.isin(VOTAVEIS_ESPECIAIS)].merge(cand, on=chave, how="left")
    proporcional = votos.cd_cargo.isin([6, 7, 8])
    sem_cand = votos.ds_destinacao.isna()

    partidos = pd.read_parquet(
        fontes.PROCESSADOS / "votos_partido_municipio.parquet", filters=[("cd_municipio", "==", fontes.CD_MUNICIPIO_DF)]
    )
    legenda_valida = set(
        partidos[partidos.qt_votos_legenda > 0][["ano", "nr_turno", "cd_cargo", "nr_partido"]].itertuples(index=False, name=None)
    )
    numero_legenda = sem_cand & proporcional & (votos.nr_votavel < 100)
    chave_partido = list(zip(votos.ano, votos.nr_turno, votos.cd_cargo, votos.nr_votavel))
    eh_legenda_valida = numero_legenda & pd.Series([k in legenda_valida for k in chave_partido], index=votos.index)
    convertido = votos.ds_destinacao == "Válido (legenda)"

    destino = pd.Series("nulo_tecnico", index=votos.index)
    destino[numero_legenda] = "anulado"  # legenda de partido sem legenda válida
    destino[eh_legenda_valida | convertido] = "legenda"
    destino[votos.ds_destinacao == "Válido"] = "nominal"
    destino[votos.ds_destinacao.fillna("").str.startswith("Anulado")] = "anulado"

    nominais = votos[destino == "nominal"].drop(columns="ds_destinacao").assign(**comum)
    nominais = _marcar_fonte_bu(nominais, usa_bu)
    nominais.to_parquet(fontes.PROCESSADOS / "votos_ra.parquet", index=False)

    leg = votos[destino == "legenda"].copy()
    leg["nr_partido"] = leg.nr_votavel.where(leg.nr_votavel < 100, leg.nr_votavel.astype(str).str[:2].astype(int))
    nomes = partidos.drop_duplicates(["ano", "nr_partido"]).set_index(["ano", "nr_partido"]).sg_partido
    leg["sg_partido"] = [nomes.get(k) for k in zip(leg.ano, leg.nr_partido)]
    legenda = leg.groupby([*ids, "nr_partido", "sg_partido"], as_index=False, dropna=False).qt_votos.sum()
    legenda = legenda.rename(columns={"qt_votos": "qt_votos_legenda"})
    legenda.assign(**comum).to_parquet(fontes.PROCESSADOS / "votos_partido_ra.parquet", index=False)

    por_destino = votos.assign(destino=destino).pivot_table(index=ids, columns="destino", values="qt_votos", aggfunc="sum")

    part = _com_ra(part_secao, locais_df)
    part = part.groupby(ids)[
        ["qt_aptos", "qt_comparecimento", "qt_abstencoes", "qt_eleitores_secoes_nao_instaladas", "qt_votos_brancos", "qt_votos_nulos"]
    ].sum()
    extra = por_destino.reindex(part.index).fillna(0).astype("int64")
    zero = pd.Series(0, index=part.index)
    part["qt_votos_validos"] = extra.get("nominal", zero) + extra.get("legenda", zero)
    part["qt_votos_nulos"] += extra.get("nulo_tecnico", zero)
    part["qt_votos_anulados"] = extra.get("anulado", zero)
    part = _marcar_fonte_bu(part.reset_index().assign(**comum), usa_bu)
    part.to_parquet(fontes.PROCESSADOS / "participacao_ra.parquet", index=False)
