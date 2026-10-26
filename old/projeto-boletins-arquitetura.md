---
name: projeto-boletins-arquitetura
description: "Decisões da refatoração do projeto Boletins de Urna (pacote boletins/, venv, fontes de dados)"
metadata: 
  node_type: memory
  type: project
  originSessionId: dd7f609a-3d70-4d86-ae4a-da6534c33643
---

Refatoração concluída em 2026-07-03: notebook Colab único virou pacote `boletins/` local com venv `.venv` (Python 3.14, pandas 3.0.3, geopandas 1.1.4).

Decisões não óbvias:
- **geobr NÃO instala** no Python 3.14/Windows (pina shapely/lxml antigos sem wheels, exige MSVC). A malha municipal vem da **API de malhas do IBGE v3** (`servicodados.ibge.gov.br/api/v3/malhas`), cacheada em geoparquet. Cuidado: o parâmetro `formato=application/vnd.geo+json` precisa ser URL-encodado (o `+` vira espaço se passado cru ao GDAL).
- De-para município TSE→IBGE: CSV de `betafcc/Municipios-Brasileiros-TSE` (GitHub raw), vendorizado em `data/raw/reference/`.
- Zonas eleitorais não têm polígono oficial; detalhe intra-municipal = pontos dos locais de votação (dataset CKAN `eleitorado-{ano}`, lat/long com vírgula decimal e `-1`/`#NULO#` como ausente).
- Nos BWEB de 2º turno só aparecem os cargos que tiveram 2º turno naquela UF (AC e DF 2022 só têm Presidente — não teve 2º turno de governador; testes não podem assumir Governador no 2t).
- Candidato identificado sempre por NR_VOTAVEL (95=Branco, 96=Nulo); cargo por CD_CARGO numérico.
- Usuário decidiu: rodar local (não Colab), mapas estáticos E interativos, pipeline genérico por URL/slug CKAN.
