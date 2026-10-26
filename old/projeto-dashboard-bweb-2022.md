---
name: projeto-dashboard-bweb-2022
description: "Dashboard HTML autocontido das eleições 2022 — onde está, como regenerar, e armadilhas (coverage_simplify, ZZ, voto de legenda tipo 4)"
metadata: 
  node_type: memory
  type: project
  originSessionId: e0308feb-25e8-4a73-b28e-25e4885a2760
---

Dashboard de 3 páginas (Presidente / Governador+Senador / Deputados) criado em 2026-07-03:
`output/dashboard_eleicoes_2022.html` (~34 MB, zero dependências externas, tema claro/escuro,
deep-link `#pres|#maj|#dep`, `?theme=dark|light` e `?uf=XX`). Fontes de regeneração em
`output/dashboard_src/`. **Build em dois passos**: `prep_dashboard.py` gera data.json+geo.json;
`build_dashboard.py` injeta esses JSONs nos placeholders `/*__DATA__*/null` e `/*__GEO__*/null`
de `dashboard_template.html` e grava o HTML final (esse 2º script foi criado 2026-07-04; antes
a montagem era manual).

Fatos não óbvios:
- **Detalhe do candidato por local de votação (2026-07-04)**: nas páginas 2 e 3, um seletor de
  candidato (`P2.cand`/`P3.mapCand`) dirige o mapa "% de um candidato" **e** duas tabelas de
  consulta — por município/RA e por **local de votação** (Município·Local·Endereço·Bairro·Zona·
  Válidos·Votos·%·%cand), via helper JS `localDetailTable`. `makeTable` ganhou `initialSort`.
  - **Unidade fina = local de votação, NÃO zona nem seção**: seção não acrescenta geografia
    (todas as seções de um local têm o mesmo endereço/bairro; ~5,4 seções/local); zona é
    grosseira (~8 bairros/zona). Chegamos a implementar detalhe por zona e por bairro e
    descartamos — o local é o átomo geográfico certo. Ver MEMORIES.md 2026-07-04 (2ª entrada).
  - Dados: `data.locais[uf]=[[mun_idx, zona, bairro_id, nome, endereço],…]` + `data.bairros[uf]`
    (interno). `boletins.geo.locais_metadata(ano)` traz nome/endereço/bairro (dataset eleitorado,
    1 linha/local). No prep, `agrega_cargo_local` faz merge de `local_id` (por município+zona+
    local) e reusa `agrega_cargo(keycol="local_id")`+`matriz_municipal`. Majoritárias guardam
    matriz por local de todos os candidatos; deputados `localt`/`localv` só dos **top-20**
    (local é ~8x mais linhas que zona → seletor/cobertura de deputado = 20). HTML ~34 MB.
  - **Mapa de pontos por local foi cogitado e descartado** pelo usuário; mapas seguem coropléticos
    município/RA (que já usam geografia do ponto/local, não zona).
- **DF nas páginas 2 e 3 é subdividido pelas 33 Regiões Administrativas** (o TSE/IBGE tratam
  o DF como 1 município). `prep_dashboard.py` usa `geo.regioes_administrativas_df()` +
  `geo.locais_por_ra_df(2022)` (de-para local→RA por ponto-em-polígono) para gerar matrizes
  `ra`/`rat`/`rav` só do DF; `data.ras_df` traz as poligonais (simplify 0.0006, EPSG:4326).
  No template, `MuniMap.setView(features, key)` é genérico (feições `{id,coords}`), e
  `usaRA(uf)` decide RA×município. Soma por RA < total do DF (só locais georreferenciados, ~99,9%).
- **Páginas de uso**:
  - **Página 1 (Presidente)**: sempre municipal (foco nacional). Mapas por município em todos os UFs incluindo DF.
  - **Página 2 (Governador/Senador)**: municipal para UFs normais; **por RA para o DF**. Tabela muda o nome "Municípios" → "Regiões Administrativas".
  - **Página 3 (Deputados)**: municipal para UFs normais; **por RA para o DF** (tabela continua "Candidatos", mas mapa é por RA). DF tem toggle "Dep. Federal / Dep. Distrital" (não "Estadual").
- **Deep-links**: `?uf=SP#maj` seleciona UF+aba; `?theme=dark` força modo escuro; `#dep` seleciona aba deputados.
- **Válidos em proporcionais**: nominais + legenda (tipos 1 e 4). Dashboard mostra "Votos por partido" empilhando nominais (azul) + legenda (verde), e tabela "Votos nominais / Votos de legenda" na legenda.
- **Voto de legenda é `CD_TIPO_VOTAVEL=4`** (não está em `constants.py`); válidos de
  proporcionais = nominais + legenda. NR_VOTAVEL do voto de legenda é o nº do partido.
- **ZZ (exterior) agora está baixado** em data/raw/bweb/2022 (1t e 2t) — só tem Presidente;
  entra nos totais nacionais/por UF, fora dos mapas.
- **`shapely.coverage_simplify`** (shapely 2.1) preserva fronteiras compartilhadas da malha
  municipal BR inteira; MAS `set_precision` depois dela lança TopologyException, e
  `make_valid` antes dela cria GeometryCollection que ela rejeita — usar coverage_simplify
  pura (tolerance 0.012) + arredondar coords a 3 casas na serialização (~3,8 MB p/ 5.570 munis).
- Totais conferidos com a totalização oficial (Lula 60.345.999 × Bolsonaro 58.206.354;
  12 UFs com 2ºt de governador: AL AM BA ES MS PB PE RO RS SC SE SP).
- Paleta validada com dataviz/validate_palette.js; mapas categóricos usam 5 slots
  [azul, amarelo, vermelho, água, laranja] (all-pairs CVD ok nos 2 modos; 6º+ vira "Outros"
  cinza); overrides de leitura: PT→vermelho, PL→azul.
