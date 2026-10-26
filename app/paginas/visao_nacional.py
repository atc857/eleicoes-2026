import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from boletim_urna.painel import dados, visual as vz

st.title("Presidente — visão nacional")

ind = dados.indicadores_presidente()
votos = dados.votos_presidente()

c1, c2, c3 = st.columns([1, 1, 2])
ano = c1.segmented_control("Ano", [2022, 2026], default=2026, key="vn_ano") or 2026
turno = c2.segmented_control("Turno", [1, 2], default=2, format_func=lambda t: f"{t}º turno", key="vn_turno") or 2
ufs = ["Brasil"] + sorted(u for u in ind.sg_uf.unique() if u != "ZZ") + ["ZZ"]
uf = c3.selectbox("Recorte", ufs, format_func=lambda u: "Exterior" if u == "ZZ" else u, key="vn_uf")

sel = ind[(ind.ano == ano) & (ind.nr_turno == turno)]
v = votos[(votos.ano == ano) & (votos.nr_turno == turno)]
if uf != "Brasil":
    sel = sel[sel.sg_uf == uf]
    v = v[v.sg_uf == uf]

# --- números principais -------------------------------------------------------
cand = v.groupby(["nr_votavel", "nm_votavel", "sg_partido"]).qt_votos.sum().sort_values(ascending=False).reset_index()
cand["pct"] = 100 * cand.qt_votos / cand.qt_votos.sum()
tot = sel[["qt_aptos", "qt_comparecimento", "qt_abstencoes", "qt_votos_brancos", "qt_votos_nulos"]].sum()

k = st.columns(4)
for col, (_, r) in zip(k[:2], cand.head(2).iterrows()):
    col.metric(f"{r.nm_votavel.title()} ({r.sg_partido})", vz.fmt_pct(r.pct, 2), vz.fmt_int(r.qt_votos) + " votos", delta_color="off")
k[2].metric("Comparecimento", vz.fmt_pct(100 * tot.qt_comparecimento / tot.qt_aptos), vz.fmt_int(tot.qt_comparecimento), delta_color="off")
k[3].metric("Abstenção", vz.fmt_pct(100 * tot.qt_abstencoes / tot.qt_aptos), vz.fmt_int(tot.qt_abstencoes), delta_color="off")

esq, dir_ = st.columns([3, 2])

# --- mapa: saldo PT − PL ------------------------------------------------------
with esq:
    st.subheader("Quem venceu e por quanto")
    st.caption("Saldo PT − PL em pontos percentuais dos válidos: vermelho = PT à frente, azul = PL à frente; quanto mais escuro, maior a vantagem.")
    lim = vz.limite_simetrico(sel.saldo_pt_pl)
    hover = vz.hover_municipio(
        sel,
        {
            "PT": sel.pct_pt.map(vz.fmt_pct),
            "PL": sel.pct_pl.map(vz.fmt_pct),
            "Vencedor": sel.vencedor_nome.fillna("—").str.title(),
            "Margem": sel.margem_pp.map(lambda x: vz.fmt_pp(x).lstrip("+")),
        },
    )
    if uf == "ZZ":
        st.info("O exterior não tem polígonos; veja a tabela ao lado.")
    else:
        fig = vz.mapa(sel, "saldo_pt_pl", vz.escala_diferenca("pt"), (-lim, lim), "PT − PL (pp)", hover)
        st.plotly_chart(fig, width="stretch", config={"locale": "pt-BR"})

# --- barras por candidato -----------------------------------------------------
with dir_:
    st.subheader("Votos válidos por candidato")
    cores = [vz.COR_PARTIDO.get(p, vz.COR_OUTROS) for p in cand.sg_partido]
    fig = go.Figure(
        go.Bar(
            x=cand.pct,
            y=cand.nm_votavel.str.title() + " (" + cand.sg_partido + ")",
            orientation="h",
            marker={"color": cores, "cornerradius": 4},
            text=cand.pct.map(lambda x: vz.fmt_pct(x, 2)),
            textposition="outside",
            customdata=cand.qt_votos.map(vz.fmt_int),
            hovertemplate="%{y}<br>%{text} · %{customdata} votos<extra></extra>",
        )
    )
    fig.update_layout(
        yaxis={"autorange": "reversed"},
        xaxis={"visible": False, "range": [0, cand.pct.max() * 1.25]},
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=max(160, 34 * len(cand)),
        bargap=0.35,
    )
    st.plotly_chart(fig, width="stretch")

    brancos_nulos = pd.DataFrame(
        {
            "Indicador": ["Aptos", "Brancos", "Nulos"],
            "Votos": [vz.fmt_int(tot.qt_aptos), vz.fmt_int(tot.qt_votos_brancos), vz.fmt_int(tot.qt_votos_nulos)],
            "%": ["", vz.fmt_pct(100 * tot.qt_votos_brancos / tot.qt_comparecimento), vz.fmt_pct(100 * tot.qt_votos_nulos / tot.qt_comparecimento)],
        }
    )
    st.dataframe(brancos_nulos, hide_index=True, width="stretch")

# --- tabela -------------------------------------------------------------------
if uf == "Brasil":
    st.subheader("Por UF")
    t = sel.groupby("sg_uf")[["qt_validos", "qt_aptos", "qt_abstencoes"]].sum()
    pv = v[v.sg_partido.isin(["PT", "PL"])].pivot_table(index="sg_uf", columns="sg_partido", values="qt_votos", aggfunc="sum")
    t["% PT"] = 100 * pv.PT / t.qt_validos
    t["% PL"] = 100 * pv.PL / t.qt_validos
    t["% abstenção"] = 100 * t.qt_abstencoes / t.qt_aptos
    t = t.rename(columns={"qt_validos": "Válidos", "qt_aptos": "Aptos"}).drop(columns="qt_abstencoes").reset_index()
    t["sg_uf"] = t.sg_uf.replace({"ZZ": "Exterior"})
    tabela = t.rename(columns={"sg_uf": "UF"})
else:
    st.subheader({"ZZ": "Por cidade", "DF": "Por Região Administrativa"}.get(uf, "Por município"))
    tabela = sel[["nm_unidade", "qt_validos", "pct_pt", "pct_pl", "vencedor_nome", "margem_pp", "pct_abstencao"]].rename(
        columns={
            "nm_unidade": "Município / RA",
            "qt_validos": "Válidos",
            "pct_pt": "% PT",
            "pct_pl": "% PL",
            "vencedor_nome": "Vencedor",
            "margem_pp": "Margem (pp)",
            "pct_abstencao": "% abstenção",
        }
    )

st.dataframe(
    tabela,
    hide_index=True,
    width="stretch",
    column_config={c: st.column_config.NumberColumn(format="%.1f") for c in tabela.columns if c.startswith(("%", "Margem"))}
    | {c: st.column_config.NumberColumn(format="localized") for c in ("Válidos", "Aptos")},
)
