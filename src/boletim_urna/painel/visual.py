"""Cores, escalas, formatação pt-BR e o mapa coroplético comum às páginas.

Paleta (validada com o validador da skill dataviz): PT vermelho, PL azul; demais
candidatos em amarelo (passa CVD all-pairs com os dois no tema claro).
Escalas divergentes: vermelho (lado PT) ↔ azul (lado PL) e roxo ↔ verde para
métricas sem lado político; claro = diferença pequena, escuro = grande, cinza no zero.
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import dados

COR_PARTIDO = {"PT": "#e34948", "PL": "#2a78d6"}
COR_OUTROS = "#eda100"
COR_SEM_DADO = "#898781"

AZUL = ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281"]
VERMELHO = ["#fbd5d4", "#f29493", "#e34948", "#b8302f", "#7f1a19"]
ROXO = ["#e3defa", "#ab9ff0", "#6250d6", "#4a3aa7", "#2e2373"]
VERDE = ["#d3f0d3", "#86cf86", "#2f9e2f", "#008300", "#004d00"]
AMARELO = ["#fdeec7", "#f8d27a", "#eda100", "#b87d00", "#7a5300"]


def tema_escuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except AttributeError:
        return False


def _meio() -> str:
    return "#383835" if tema_escuro() else "#f0efec"


def escala_divergente(negativo: list[str], positivo: list[str]) -> list:
    """Do escuro do lado negativo, passando pelo cinza neutro, ao escuro do lado positivo."""
    cores = list(reversed(negativo)) + [_meio()] + positivo
    return [[i / (len(cores) - 1), c] for i, c in enumerate(cores)]


def escala_sequencial(rampa: list[str]) -> list:
    return [[i / (len(rampa) - 1), c] for i, c in enumerate(rampa)]


# Métricas: rótulo, de que lado fica o positivo ("pt", "pl" ou None = sem lado), rampa sequencial.
METRICAS = {
    "saldo_pt_pl": ("Saldo PT − PL (pp)", "pt", None),
    "pct_pt": ("% PT (válidos)", "pt", VERMELHO),
    "pct_pl": ("% PL (válidos)", "pl", AZUL),
    "pct_bloco_campo_lula": ("% Campo Lula/PT", "pt", VERMELHO),
    "pct_bloco_campo_bolsonarista": ("% Campo bolsonarista/PL", "pl", AZUL),
    "pct_bloco_demais": ("% Demais candidatos", None, AMARELO),
    "pct_abstencao": ("% Abstenção (aptos)", None, ROXO),
    "pct_brancos": ("% Brancos (comparecimento)", None, ROXO),
    "pct_nulos": ("% Nulos (comparecimento)", None, ROXO),
}


def escala_diferenca(lado: str | None) -> list:
    if lado == "pt":
        return escala_divergente(AZUL, VERMELHO)
    if lado == "pl":
        return escala_divergente(VERMELHO, AZUL)
    return escala_divergente(VERDE, ROXO)


def fmt_int(x) -> str:
    return "—" if pd.isna(x) else f"{int(x):,}".replace(",", ".")


def fmt_pct(x, casas: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",") + "%"


def fmt_pp(x, casas: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x:+.{casas}f}".replace(".", ",") + " pp"


def limite_simetrico(valores: pd.Series, quantil: float = 0.98) -> float:
    """Faixa simétrica da escala divergente; corta extremos para não lavar o mapa."""
    v = valores.abs().dropna()
    return float(np.ceil(v.quantile(quantil))) if len(v) else 1.0


def _mercator_y(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _enquadrar(ids: pd.Series, altura: int, largura: int = 760) -> dict:
    """Centro e zoom (MapLibre, tiles de 512 px) que fazem o recorte caber no quadro."""
    b = dados.limites_por_id().reindex(ids.dropna().unique()).dropna()
    if b.empty:
        return {"center": {"lat": -14.5, "lon": -52.0}, "zoom": 3.0}
    xmin, ymin, xmax, ymax = b.xmin.min(), b.ymin.min(), b.xmax.max(), b.ymax.max()
    px_por_grau = 512 / 360
    zoom_x = math.log2(largura / (max(xmax - xmin, 0.01) * px_por_grau))
    zoom_y = math.log2(altura / (max(_mercator_y(ymax) - _mercator_y(ymin), 0.0002) * 512 / (2 * math.pi)))
    centro_lat = math.degrees(2 * math.atan(math.exp((_mercator_y(ymin) + _mercator_y(ymax)) / 2)) - math.pi / 2)
    return {"center": {"lat": centro_lat, "lon": (xmin + xmax) / 2}, "zoom": min(zoom_x, zoom_y) - 0.15}


def _estilo_mapa() -> dict:
    """Sem mapa de fundo: só a superfície do tema (países vizinhos não parecem "sem dado")."""
    fundo = "#1a1a19" if tema_escuro() else "#fcfcfb"
    return {"version": 8, "sources": {}, "layers": [{"id": "fundo", "type": "background", "paint": {"background-color": fundo}}]}


def _camada_sem_dado(df: pd.DataFrame) -> go.Choroplethmap | None:
    """Unidades do recorte sem linha em `df` (ex.: RA sem local de votação) em cinza, para não virar buraco."""
    u = dados.unidades()
    u = u[u.sg_uf.isin(df.sg_uf.unique()) & u.id_geo.notna()]
    tipos = set(df.tipo) if "tipo" in df else {"municipio"}
    u = u[u.tipo != ("df" if "ra" in tipos else "ra")]  # nunca DF inteiro sob as RAs (ou vice-versa)
    faltam = u[~u.id_geo.isin(df.id_geo)]
    if faltam.empty:
        return None
    return go.Choroplethmap(
        geojson=dados.geo_unidades(),
        locations=faltam.id_geo,
        z=np.zeros(len(faltam)),
        colorscale=[[0, COR_SEM_DADO], [1, COR_SEM_DADO]],
        showscale=False,
        marker_line_width=0.2,
        marker_line_color="rgba(128,128,128,0.35)",
        text="<b>" + faltam.nm_unidade.str.title() + " / " + faltam.sg_uf + "</b><br>sem dado (sem local de votação ou sem par)",
        hovertemplate="%{text}<extra></extra>",
        name="Sem dado",
    )


def mapa(
    df: pd.DataFrame,
    valor: str,
    escala: list,
    faixa: tuple[float, float],
    titulo_cor: str,
    hover: pd.Series,
    altura: int = 620,
) -> go.Figure:
    """Coroplético por unidade (WebGL). `df` precisa de `id_geo`; exterior fica de fora."""
    df = df[df.id_geo.notna()]
    fig = go.Figure()
    if (sem_dado := _camada_sem_dado(df)) is not None:
        fig.add_trace(sem_dado)
    fig.add_trace(
        go.Choroplethmap(
            geojson=dados.geo_unidades(),
            locations=df.id_geo,
            z=df[valor],
            zmin=faixa[0],
            zmax=faixa[1],
            colorscale=escala,
            marker_line_width=0.2,
            marker_line_color="rgba(128,128,128,0.35)",
            colorbar={"title": {"text": titulo_cor, "side": "right"}, "thickness": 12},
            text=hover.reindex(df.index),
            hovertemplate="%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        map={"style": _estilo_mapa(), **_enquadrar(df.id_geo, altura)},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=altura,
    )
    return fig


def mapa_categorico(df: pd.DataFrame, coluna: str, cores: dict[str, str], hover: pd.Series, altura: int = 620) -> go.Figure:
    """Um traço por categoria, para que a legenda mostre cada uma (identidade não só pela cor)."""
    df = df[df.id_geo.notna()]
    fig = go.Figure()
    if (sem_dado := _camada_sem_dado(df)) is not None:
        fig.add_trace(sem_dado)
    for categoria, cor in cores.items():
        parte = df[df[coluna] == categoria]
        if parte.empty:
            continue
        fig.add_trace(
            go.Choroplethmap(
                geojson=dados.geo_unidades(),
                locations=parte.id_geo,
                z=np.ones(len(parte)),
                colorscale=[[0, cor], [1, cor]],
                showscale=False,
                showlegend=True,
                name=f"{categoria} ({len(parte)})",
                marker_line_width=0.2,
                marker_line_color="rgba(128,128,128,0.35)",
                text=hover.reindex(parte.index),
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.update_layout(
        map={"style": _estilo_mapa(), **_enquadrar(df.id_geo, altura)},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=altura,
        legend={"orientation": "h", "y": 1.02, "x": 0},
    )
    return fig


def hover_municipio(df: pd.DataFrame, linhas: dict[str, pd.Series]) -> pd.Series:
    """Texto do tooltip: nome/UF em negrito + linhas `rótulo: valor` já formatadas."""
    texto = "<b>" + df.nm_unidade.fillna("?").str.title() + " / " + df.sg_uf + "</b>"
    for rotulo, serie in linhas.items():
        texto = texto + f"<br>{rotulo}: " + serie.astype(str)
    return texto
