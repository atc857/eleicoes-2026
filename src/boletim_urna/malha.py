"""Malha municipal (API de malhas IBGE v3), simplificada e cacheada em GeoJSON leve."""

import json
import urllib.parse

import geopandas as gpd
import shapely

from . import baixar, fontes

URL_IBGE = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?intrarregiao=municipio&qualidade=intermediaria&formato="
    # o formato precisa ir URL-encodado: o '+' cru vira espaço
    + urllib.parse.quote("application/vnd.geo+json", safe="")
)
BRUTO = fontes.BRUTOS / "ibge" / "malha_municipios.geojson"
PROCESSADO = fontes.PROCESSADOS / "malha_municipios.geojson"

# coverage_simplify preserva as fronteiras compartilhadas; set_precision/make_valid a quebram.
TOLERANCIA = 0.012


def malha_municipios() -> dict:
    """GeoJSON (EPSG:4326) com `id` = código IBGE de 7 dígitos."""
    if not PROCESSADO.exists():
        baixar.baixar_arquivo(URL_IBGE, BRUTO)
        gdf = gpd.read_file(BRUTO)
        gdf["geometry"] = shapely.coverage_simplify(gdf.geometry.values, TOLERANCIA)
        feicoes = [
            {
                "type": "Feature",
                "id": str(cod),
                "properties": {},
                "geometry": json.loads(shapely.to_geojson(geom, indent=None)),
            }
            for cod, geom in zip(gdf["codarea"], gdf.geometry)
        ]
        texto = json.dumps({"type": "FeatureCollection", "features": feicoes}, separators=(",", ":"))
        # arredonda coordenadas a 3 casas (~100 m) para reduzir o arquivo
        geo = json.loads(texto, parse_float=lambda s: round(float(s), 3))
        PROCESSADO.parent.mkdir(parents=True, exist_ok=True)
        PROCESSADO.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    return json.loads(PROCESSADO.read_text(encoding="utf-8"))
