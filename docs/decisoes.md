# Decisões do projeto — Boletim Urna 2022 × 2026

Registro das decisões tomadas na sessão de planejamento de 26/10/2026. Inspiração: urnaaberta.com.br.

## Produto

- Pipeline de dados reprodutível (Parquet + DuckDB) + site estático de uso local (o painel Streamlit inicial foi substituído em 27/10/2026, ver "Site estático").
- Uso pessoal e local. (A exportação de CSV/PNG do painel Streamlit não foi levada ao site.)
- Código, colunas e documentação em português, seguindo a nomenclatura do TSE (`cd_municipio`, `qt_votos`…).
- Stack: `uv`, Python 3.13 (o 3.14 teve problemas de wheels no projeto anterior), Parquet + DuckDB, CLI com `baixar`, `processar`, `atualizar`. Repositório git nesta pasta.

## Escopo

- **Cargos**: todos (Presidente, Governador, Senador, Dep. Federal, Dep. Estadual/Distrital), consultáveis por ano. **Comparação 2022 × 2026 só para Presidente.**
- **Geografia**: Brasil inteiro + exterior. Unidade = **município**; o **DF é dividido nas 37 Regiões Administrativas** atuais (malha IDE-DF), em todos os cargos, nos dois anos, inclusive no mapa nacional.
- **Exterior**: tabelas por país/cidade com comparação; entra nos totais nacionais; fora dos mapas.

## Fontes

| Dado | Fonte |
|---|---|
| 2022 (tudo) | TSE Dados Abertos (CDN `cdn.tse.jus.br/estatistica/sead/odsele/…`) |
| 2026 1º turno | TSE Dados Abertos |
| 2026 2º turno (municípios) | API de resultados `resultados.tse.jus.br/oficial/ele2026/{6258,6260}` até o CSV oficial sair |
| 2026 2º turno (DF por RA) | Boletins de urna decodificados da API (`arquivo-urna/3221`) até o CSV oficial sair |
| De-para TSE → IBGE | campo `cdi` de `mun-e00{ele}-cm.json` |
| Malha municipal | API de malhas IBGE v3 (geobr não instala no Windows/3.14) |
| Malha das RAs do DF | IDE-DF ArcGIS `Publico/LIMITES/MapServer/1` (37 RAs) |
| Locais de votação (DF) | `eleitorado_locais_votacao/eleitorado_local_votacao_{ano}.zip` |

- Municípios: arquivos `votacao_candidato_munzona`, `votacao_partido_munzona`, `detalhe_votacao_munzona` (não BWEB).
- DF: `votacao_secao_{ano}_DF` (Gov/Sen/Deputados) + `votacao_secao_{ano}_BR` filtrado (Presidente), seção → local (chave `NR_ZONA`+`NR_LOCAL_VOTACAO`) → RA por ponto-em-polígono.
- Proveniência registrada por linha; onde CSV e API se sobrepõem (2026 1º turno) os totais são conferidos.
- `atualizar` (execução manual) consulta o CKAN, baixa o CSV oficial do 2º turno de 2026 quando publicado, substitui API/BU e confere.

## Comparação (Presidente)

- Pares: 1ºt 2022 × 1ºt 2026 e 2ºt 2022 × 2ºt 2026.
- Por **partido**, por **bloco** (YAML configurável: campo Lula/PT, campo bolsonarista/PL, demais — montado a partir das coligações oficiais e revisável), **participação** e **swing** do 2º turno.
- Indicador principal: **pontos percentuais dos votos válidos**; votos absolutos e variação do eleitorado como complemento.
- Abstenção/comparecimento sobre aptos; brancos/nulos sobre comparecimento.
- **Virada**: partido do mais votado mudou entre os anos no mesmo turno; destaque para viradas com margem < 5 pp em algum dos anos.
- Municípios sem par (ex.: Boa Esperança do Norte/MT) = "sem comparação", cinza no mapa, listados em relatório.

## Mapas e visual

- Coropléticos (MapLibre no site), malha simplificada com `shapely.coverage_simplify` (sem `set_precision`/`make_valid`).
- Diferença PT × PL: escala divergente vermelho (PT) ↔ azul (PL), claro = pequena, escuro = grande, cinza perto de zero. Métricas não partidárias: outro par divergente (roxo ↔ verde).
- Paleta do projeto anterior (PT vermelho, PL azul, 5 categóricas validadas para daltonismo), temas claro/escuro.

## Painel

1. Visão nacional
2. Comparação 2022 × 2026 (Presidente): mapas de diferença, viradas, rankings
3. Ficha do município/RA
4. Outros cargos (um ano por vez; deputados: ranking + votos por partido, nominal + legenda)
5. Exterior

## DF por RA — detalhes

- Malha atual de 37 RAs aplicada aos dois anos.
- Seções sem coordenada: herdam coordenada do mesmo local (outra seção / outro ano); o resto vai para "RA não identificada" (soma nos totais, fora do mapa, reportado).
- Seções agregadas contam pela seção principal.

## Decodificador de boletins (BU) — DF 2º turno 2026

- Especificação ASN.1 v2 em `vendor/tse/bu_v2.asn1`. O zip oficial não pôde ser obtido (site do TSE bloqueia download automatizado e o usuário não tinha cópia); veio de duas cópias públicas idênticas, ver `vendor/tse/PROVENIENCIA.md`. A v1 (2022) não decodifica os BUs de 2026.
- Download educado (concorrência baixa, cache em disco, nunca baixa duas vezes).
- Conferência: decodifica sem erro; seção/zona do BU = URL; **soma dos BUs = total DF da API, voto a voto** (Presidente e Governador). Assinatura digital fora do escopo.
- Permanece como verificação seção a seção contra o CSV oficial quando este sair.

## Testes

- Conferência obrigatória dos totais com a totalização oficial (ex.: 2022 2ºt Lula 60.345.999 × Bolsonaro 58.206.354; 2026 2ºt Lula 64.256.232 × Flávio Bolsonaro 59.826.041).

## Etapas

1. Pipeline municipal 2022 + 2026 (CSV + API) com testes de totais — **feito**
2. Comparação Presidente + painel (páginas 1–3) — **feito**
3. DF por RA — **feito**
4. Decodificador de BU (DF 2ºt 2026) — **feito**
5. Outros cargos e exterior (páginas 4–5) — **feito** (no site estático)
6. Site estático substitui o Streamlit — **feito** (uso local)

## Notas de implementação

- Mapas sem mapa de fundo (só a superfície do tema): com tiles, países vizinhos claros pareciam "sem dado".
- A malha IBGE v3 ainda não tem Boa Esperança do Norte (MT, 5101837): aparece nas tabelas, não no mapa.
- Localidades sem votos válidos (exterior) ficam sem vencedor; topo empatado = "EMPATE".
- Senador 2026: duas vagas, dois votos por eleitor (votos > comparecimento é esperado).
- DF por RA: soma das RAs confere voto a voto com o total do DF (candidatos, legenda, participação).
  Votos do arquivo de seção são classificados pelo destino do TSE: "Válido" (nominal), "Válido (legenda)"
  (soma na legenda), "Anulado"/"Anulado sub judice" (coluna qt_votos_anulados, fora de nulos e válidos);
  número ausente da lista de candidatos = nulo técnico (soma aos nulos).
- RA 36 (26 de Setembro) não tem local de votação: aparece em cinza ("sem dado").
- Unidades: `*_unidade.parquet` têm o DF inteiro (tipo "df") e as RAs (tipo "ra"); `sem_duplicar_df`
  escolhe RA quando há dado por seção; a comparação usa RA só nos turnos em que os dois anos têm RA
  (até a etapa 4, o 2º turno do DF é comparado com o DF inteiro).
- BUs do DF (2º turno 2026): 6.969 seções principais baixadas e decodificadas; a soma confere voto a voto
  com a totalização oficial (Presidente e Governador). Linhas com `fonte = bu:3221`.
- `atualizar`, quando o CSV oficial do 2º turno sair: troca API/BU pelo CSV e grava
  `conferencia_bu_csv_df_2t_2026.csv` com as divergências seção a seção (vazio = tudo confere).

## Site estático (27/10/2026)

- O Streamlit ficou lento: cada clique roda a página inteira no Python e o Plotly redesenha a malha toda.
  Trocado por um **site estático**: `uv run boletim-urna site --servir` (exporta e abre em http://localhost:8000).
- `site_estatico.py` exporta `site/dados/` (gitignorado, ~49 MB em 153 arquivos):
  - `unidades`, `malha` (GeoJSON, `promoteId` = id_geo), `ufs` (contornos: segmentos não compartilhados;
    união de polígonos falha nesta malha), `indice` (corridas disponíveis);
  - `c{cargo}_{ano}_{turno}`: participação por unidade + candidatos (majoritários) ou partidos (proporcionais), votos esparsos;
  - `c{cargo}_{ano}_{turno}_{UF}`: candidatos a deputado da UF, só carregado ao escolher a UF (SP: 370 KB gzip);
  - `ficha_{UF}`: participação de todas as corridas e os 10 mais votados de cada cargo por unidade.
- Deputado Distrital (8) entra como cargo 7, "Deputado Estadual/Distrital". Votos anulados ficam fora dos candidatos.
  Total do partido = nominais válidos dos candidatos + legenda (a tabela de partidos das RAs não traz nominais);
  confere com `qt_votos_validos` em todas as corridas (teste).
- Página em HTML + módulos JS sem build (`site/js/`), MapLibre GL 4.7.1 via CDN. Trocar ano/turno/métrica só muda
  `feature-state` (cor), sem redesenhar a malha. Estado inteiro na URL (`#v=c&turno=1&uf=DF&m=viradas&u=DF-RA28`).
- Vistas: **Resultados** (qualquer cargo/ano/turno; mapa de mais votado, % do candidato, % do partido, saldo PT − PL,
  variação desde 2022, participação) e **Comparação 2022 × 2026** (Presidente: diferenças, viradas, dispersão,
  rankings). A **ficha** abre no painel lateral nas duas vistas.
- Cores categóricas: PT e PL fixos; os três partidos que mais vencem no recorte ganham amarelo/verde/roxo; o resto, cinza neutro.
- Turno padrão: 2º para Presidente, 1º para os demais cargos (2º turno de governador só em algumas UFs).
- Medido localmente: trocas de botão 5–210 ms (o pior: deputados de SP, 1.650 linhas na tabela).
- Uso só local (decisão do usuário, 27/10/2026): sem hospedagem pública. O painel Streamlit (`app/`) foi removido.
