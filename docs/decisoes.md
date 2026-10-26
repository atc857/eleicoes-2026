# Decisões do projeto — Boletim Urna 2022 × 2026

Registro das decisões tomadas na sessão de planejamento de 26/10/2026. Inspiração: urnaaberta.com.br.

## Produto

- Pipeline de dados reprodutível (Parquet + DuckDB) + painel interativo local em **Streamlit**. Site público estático fica para evolução futura.
- Uso pessoal, com saídas compartilháveis: toda tabela exporta CSV, todo gráfico/mapa exporta PNG (Plotly). Relatório estático fica para depois.
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

- Coropléticos Plotly, malha simplificada com `shapely.coverage_simplify` (sem `set_precision`/`make_valid`).
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

- Especificação ASN.1 oficial (pacote "Formato dos arquivos de BU, RDV e assinatura digital", v2) **baixada manualmente pelo usuário** em `vendor/tse/` (o site do TSE bloqueia download automatizado); hash registrado.
- Download educado (concorrência baixa, cache em disco, nunca baixa duas vezes).
- Conferência: decodifica sem erro; seção/zona do BU = URL; **soma dos BUs = total DF da API, voto a voto** (Presidente e Governador). Assinatura digital fora do escopo.
- Permanece como verificação seção a seção contra o CSV oficial quando este sair.

## Testes

- Conferência obrigatória dos totais com a totalização oficial (ex.: 2022 2ºt Lula 60.345.999 × Bolsonaro 58.206.354; 2026 2ºt Lula 64.256.232 × Flávio Bolsonaro 59.826.041).

## Etapas

1. Pipeline municipal 2022 + 2026 (CSV + API) com testes de totais
2. Comparação Presidente + painel (páginas 1–3)
3. DF por RA
4. Decodificador de BU (DF 2ºt 2026)
5. Outros cargos e exterior (páginas 4–5)
