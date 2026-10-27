# Boletim Urna 2022 × 2026

Resultados eleitorais por município (DF por Região Administrativa) a partir de fontes oficiais do TSE,
com comparação 2022 × 2026 para Presidente. Decisões de projeto em [docs/decisoes.md](docs/decisoes.md).

```sh
uv run boletim-urna baixar      # TSE Dados Abertos → data/raw/
uv run boletim-urna processar   # → data/processed/*.parquet
uv run boletim-urna comparar     # regera só a comparação 2022 × 2026 de Presidente
uv run boletim-urna atualizar   # troca API por CSV oficial quando o 2º turno de 2026 sair
uv run boletim-urna site --servir  # exporta site/dados/ e abre o site em http://localhost:8000
uv run pytest                   # confere com a totalização oficial
```

## Estado

Site estático em [site/](site/) (HTML + JS, sem build): resultados de todos os cargos por município/RA e exterior,
comparação 2022 × 2026 de Presidente e ficha de cada unidade; o estado da tela fica na URL. Uso local: `boletim-urna site --servir`.
`data/` (bruto, temporário e processado) não é versionado; `data/tmp/` guarda CSVs extraídos e pode ser regenerado.
