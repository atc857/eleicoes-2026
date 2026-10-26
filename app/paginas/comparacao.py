import plotly.graph_objects as go
import streamlit as st

from boletim_urna.painel import dados, visual as vz

st.title("Presidente — o que mudou de 2022 para 2026")

cmp = dados.comparacao_presidente()

c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
turno = c1.segmented_control("Turno", [1, 2], default=2, format_func=lambda t: f"{t}º turno", key="cp_turno") or 2
sel = cmp[cmp.nr_turno == turno]
disponiveis = [m for m in vz.METRICAS if f"d_{m}" in sel and sel[f"d_{m}"].notna().any()]
metrica = c2.selectbox("Métrica", disponiveis, format_func=lambda m: vz.METRICAS[m][0], key="cp_metrica")
ufs = ["Brasil"] + sorted(u for u in sel.sg_uf.unique() if u != "ZZ") + ["ZZ"]
uf = c3.selectbox("Recorte", ufs, format_func=lambda u: "Exterior" if u == "ZZ" else u, key="cp_uf")
modo = c4.segmented_control("Mapa", ["Diferença", "Viradas"], default="Diferença", key="cp_modo") or "Diferença"

if uf != "Brasil":
    sel = sel[sel.sg_uf == uf]
rotulo, lado, _ = vz.METRICAS[metrica]
d = f"d_{metrica}"

# --- resumo -------------------------------------------------------------------
comparaveis = sel[~sel.sem_comparacao]
pt_pl = (comparaveis.vencedor_partido_2022 == "PT") & (comparaveis.vencedor_partido_2026 == "PL")
pl_pt = (comparaveis.vencedor_partido_2022 == "PL") & (comparaveis.vencedor_partido_2026 == "PT")
k = st.columns(4)
k[0].metric("Unidades comparáveis", vz.fmt_int(len(comparaveis)))
k[1].metric("Viraram PT → PL", vz.fmt_int(pt_pl.sum()))
k[2].metric("Viraram PL → PT", vz.fmt_int(pl_pt.sum()))
k[3].metric(f"Mediana da variação — {rotulo}", vz.fmt_pp(comparaveis[d].median()))

# --- mapa ---------------------------------------------------------------------
hover = vz.hover_municipio(
    sel,
    {
        "2022": sel[f"{metrica}_2022"].map(vz.fmt_pct if metrica.startswith("pct") else vz.fmt_pp),
        "2026": sel[f"{metrica}_2026"].map(vz.fmt_pct if metrica.startswith("pct") else vz.fmt_pp),
        "Variação": sel[d].map(vz.fmt_pp),
        "Vencedor 2022 → 2026": sel.vencedor_partido_2022.fillna("—") + " → " + sel.vencedor_partido_2026.fillna("—"),
    },
)

if uf == "ZZ":
    st.info("O exterior não tem polígonos; veja as tabelas abaixo.")
elif modo == "Diferença":
    st.caption(
        f"Variação de **{rotulo}** em pontos percentuais. "
        + (
            "Vermelho = movimento a favor do lado PT, azul = a favor do lado PL"
            if lado
            else "Roxo = aumentou, verde = diminuiu"
        )
        + "; tons claros = variação pequena, escuros = grande. Cinza-escuro sem preenchimento = sem comparação."
    )
    lim = vz.limite_simetrico(comparaveis[d])
    fig = vz.mapa(sel, d, vz.escala_diferenca(lado), (-lim, lim), "Variação (pp)", hover)
    st.plotly_chart(fig, width="stretch")
else:
    st.caption("Partido do candidato mais votado em 2022 → 2026. **Apertada** = margem abaixo de 5 pp em algum dos anos.")
    cat = sel.copy()
    cat["categoria"] = "Manteve"
    cat.loc[cat.virou & ~cat.virada_apertada, "categoria"] = cat.vencedor_partido_2022 + " → " + cat.vencedor_partido_2026
    cat.loc[cat.virada_apertada, "categoria"] = cat.vencedor_partido_2022 + " → " + cat.vencedor_partido_2026 + " (apertada)"
    cat.loc[cat.sem_comparacao, "categoria"] = "Sem comparação"
    cores = {
        "PT → PL": vz.AZUL[4],
        "PT → PL (apertada)": vz.AZUL[1],
        "PL → PT": vz.VERMELHO[4],
        "PL → PT (apertada)": vz.VERMELHO[1],
        "Manteve": "#d6d5ce" if not vz.tema_escuro() else "#4a4a46",
        "Sem comparação": vz.COR_SEM_DADO,
    }
    outros = sorted(set(cat.categoria) - set(cores))
    cores |= {c: vz.COR_OUTROS for c in outros}
    st.plotly_chart(vz.mapa_categorico(cat, "categoria", cores, hover), width="stretch")

# --- dispersão 2022 × 2026 ----------------------------------------------------
esq, dir_ = st.columns(2)
with esq:
    st.subheader("2022 × 2026, unidade a unidade")
    st.caption("Acima da diagonal, a métrica cresceu. Tamanho do ponto ∝ eleitorado apto em 2026.")
    pts = comparaveis[comparaveis.qt_aptos_2026 > 0]
    cor = vz.COR_PARTIDO["PT"] if lado == "pt" else vz.COR_PARTIDO["PL"] if lado == "pl" else vz.ROXO[2]
    fig = go.Figure(
        go.Scattergl(
            x=pts[f"{metrica}_2022"],
            y=pts[f"{metrica}_2026"],
            mode="markers",
            marker={
                "size": (pts.qt_aptos_2026**0.5 / 25).clip(3, 30),
                "color": cor,
                "opacity": 0.55,
                "line": {"width": 0.5, "color": "white"},
            },
            text=hover.reindex(pts.index),
            hovertemplate="%{text}<extra></extra>",
        )
    )
    lo = min(pts[f"{metrica}_2022"].min(), pts[f"{metrica}_2026"].min())
    hi = max(pts[f"{metrica}_2022"].max(), pts[f"{metrica}_2026"].max())
    fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi, line={"dash": "dot", "width": 1, "color": vz.COR_SEM_DADO})
    fig.update_layout(
        xaxis_title=f"{rotulo} — 2022",
        yaxis_title=f"{rotulo} — 2026",
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=480,
    )
    st.plotly_chart(fig, width="stretch")

# --- rankings -----------------------------------------------------------------
with dir_:
    st.subheader("Maiores variações")
    minimo = st.number_input("Eleitorado apto mínimo (2026)", 0, 1_000_000, 5_000, step=1_000, key="cp_min")
    base = comparaveis[comparaveis.qt_aptos_2026 >= minimo]
    colunas = {
        "nm_unidade": "Município / RA",
        "sg_uf": "UF",
        f"{metrica}_2022": "2022",
        f"{metrica}_2026": "2026",
        d: "Variação (pp)",
        "qt_aptos_2026": "Aptos 2026",
    }
    fmt = {c: st.column_config.NumberColumn(format="%.1f") for c in ("2022", "2026", "Variação (pp)")} | {
        "Aptos 2026": st.column_config.NumberColumn(format="localized")
    }
    a, b = st.tabs(["Maiores altas", "Maiores quedas"])
    a.dataframe(base.nlargest(20, d)[list(colunas)].rename(columns=colunas), hide_index=True, column_config=fmt)
    b.dataframe(base.nsmallest(20, d)[list(colunas)].rename(columns=colunas), hide_index=True, column_config=fmt)

# --- viradas ------------------------------------------------------------------
st.subheader("Municípios e RAs que mudaram de vencedor")
vir = sel[sel.virou].sort_values("qt_aptos_2026", ascending=False)
st.dataframe(
    vir[
        ["nm_unidade", "sg_uf", "vencedor_nome_2022", "margem_pp_2022", "vencedor_nome_2026", "margem_pp_2026", "virada_apertada", "qt_aptos_2026"]
    ].rename(
        columns={
            "nm_unidade": "Município / RA",
            "sg_uf": "UF",
            "vencedor_nome_2022": "Vencedor 2022",
            "margem_pp_2022": "Margem 2022 (pp)",
            "vencedor_nome_2026": "Vencedor 2026",
            "margem_pp_2026": "Margem 2026 (pp)",
            "virada_apertada": "Apertada",
            "qt_aptos_2026": "Aptos 2026",
        }
    ),
    hide_index=True,
    width="stretch",
    column_config={
        "Margem 2022 (pp)": st.column_config.NumberColumn(format="%.1f"),
        "Margem 2026 (pp)": st.column_config.NumberColumn(format="%.1f"),
        "Aptos 2026": st.column_config.NumberColumn(format="localized"),
    },
)

sem = sel[sel.sem_comparacao]
if len(sem):
    with st.expander(f"{len(sem)} localidade(s) sem comparação"):
        st.write(", ".join((sem.nm_unidade.fillna(sem.cd_unidade).str.title() + "/" + sem.sg_uf).tolist()))
        st.caption("Boa Esperança do Norte (MT) foi criado após 2022 e ainda não está na malha do IBGE; no exterior, cidades que deixaram ou passaram a ter seção.")
