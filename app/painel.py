"""Ponto de entrada do painel: `uv run boletim-urna painel`."""

import streamlit as st

st.set_page_config(page_title="Boletim Urna 2022 × 2026", page_icon="🗳️", layout="wide")

paginas = st.navigation(
    [
        st.Page("paginas/visao_nacional.py", title="Visão nacional", icon="🇧🇷", default=True),
        st.Page("paginas/comparacao.py", title="Comparação 2022 × 2026", icon="↔️"),
        st.Page("paginas/ficha.py", title="Ficha do município", icon="📍"),
    ]
)
paginas.run()

st.caption(
    "Fontes: TSE Dados Abertos (CSV oficial) e API de resultados do TSE (2º turno de 2026, até a publicação do CSV); "
    "malha municipal IBGE. Válidos = votos nominais válidos; abstenção sobre aptos; brancos/nulos sobre comparecimento."
)
