# Boletim Urna 2022 × 2026

Resultados eleitorais por município (DF por Região Administrativa) a partir de fontes oficiais do TSE,
com comparação 2022 × 2026 para Presidente. Decisões de projeto em [docs/decisoes.md](docs/decisoes.md).

```sh
uv run boletim-urna baixar      # TSE Dados Abertos → data/raw/
uv run boletim-urna processar   # → data/processed/*.parquet
uv run boletim-urna atualizar   # troca API por CSV oficial quando o 2º turno de 2026 sair
uv run boletim-urna painel      # abre o painel Streamlit
uv run pytest                   # confere com a totalização oficial
```
