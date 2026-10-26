import plotly.graph_objects as go
import streamlit as st

from boletim_urna import fontes
from boletim_urna.painel import dados, visual as vz

st.title("Ficha do município")

mun = dados.municipios().copy()
mun["rotulo"] = mun.nm_municipio.str.title() + " / " + mun.sg_uf.replace({"ZZ": "Exterior"})
mun = mun.sort_values("rotulo")
opcoes = dict(zip(mun.rotulo, mun.cd_municipio))
padrao = list(opcoes).index("Brasília / DF") if "Brasília / DF" in opcoes else 0
escolha = st.selectbox("Município", list(opcoes), index=padrao, key="fi_mun")
cd = opcoes[escolha]

votos = dados.votos_municipio(cd)
part = dados.participacao_municipio(cd)
cmp = dados.comparacao_presidente()
cmp = cmp[cmp.cd_municipio == cd]

# --- Presidente: 2022 × 2026 --------------------------------------------------
st.header("Presidente")
for turno in (1, 2):
    linha = cmp[cmp.nr_turno == turno]
    if linha.empty:
        continue
    r = linha.iloc[0]
    st.subheader(f"{turno}º turno")
    k = st.columns(4)
    k[0].metric("% PT 2026", vz.fmt_pct(r.pct_pt_2026), vz.fmt_pp(r.d_pct_pt) + " vs 2022", delta_color="off")
    k[1].metric("% PL 2026", vz.fmt_pct(r.pct_pl_2026), vz.fmt_pp(r.d_pct_pl) + " vs 2022", delta_color="off")
    k[2].metric("Abstenção 2026", vz.fmt_pct(r.pct_abstencao_2026), vz.fmt_pp(r.d_pct_abstencao) + " vs 2022", delta_color="off")
    k[3].metric("Eleitorado apto 2026", vz.fmt_int(r.qt_aptos_2026), vz.fmt_pct(r.d_pct_aptos) + " vs 2022", delta_color="off")

    colunas = st.columns(2)
    for col, ano in zip(colunas, fontes.ANOS):
        v = votos[(votos.cd_cargo == 1) & (votos.ano == ano) & (votos.nr_turno == turno)].sort_values("qt_votos", ascending=False)
        if v.empty:
            col.caption(f"{ano}: sem dados")
            continue
        pct = 100 * v.qt_votos / v.qt_votos.sum()
        fig = go.Figure(
            go.Bar(
                x=pct,
                y=v.nm_votavel.str.title() + " (" + v.sg_partido + ")",
                orientation="h",
                marker={"color": [vz.COR_PARTIDO.get(p, vz.COR_OUTROS) for p in v.sg_partido], "cornerradius": 4},
                text=[f"{vz.fmt_pct(p)} · {vz.fmt_int(q)}" for p, q in zip(pct, v.qt_votos)],
                textposition="outside",
                hoverinfo="skip",
            )
        )
        fig.update_layout(
            title={"text": str(ano), "x": 0},
            yaxis={"autorange": "reversed"},
            xaxis={"visible": False, "range": [0, 130]},
            margin={"l": 0, "r": 0, "t": 30, "b": 0},
            height=60 + 30 * len(v),
            bargap=0.35,
        )
        col.plotly_chart(fig, width="stretch", key=f"fi_{turno}_{ano}")
        fonte = v.fonte.iloc[0]
        if fonte != "csv":
            col.caption(f"Fonte: API de resultados do TSE ({fonte}) — será trocada pelo CSV oficial quando publicado.")

# --- Participação -------------------------------------------------------------
st.header("Participação por cargo")
p = part.copy()
p["Cargo"] = p.cd_cargo.map(fontes.CARGOS)
p["% abstenção"] = 100 * p.qt_abstencoes / p.qt_aptos
p["% brancos"] = 100 * p.qt_votos_brancos / p.qt_comparecimento
p["% nulos"] = 100 * p.qt_votos_nulos / p.qt_comparecimento
st.dataframe(
    p.sort_values(["cd_cargo", "nr_turno", "ano"])[
        ["Cargo", "nr_turno", "ano", "qt_aptos", "qt_comparecimento", "% abstenção", "% brancos", "% nulos"]
    ].rename(columns={"nr_turno": "Turno", "ano": "Ano", "qt_aptos": "Aptos", "qt_comparecimento": "Comparecimento"}),
    hide_index=True,
    width="stretch",
    column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ("% abstenção", "% brancos", "% nulos")}
    | {c: st.column_config.NumberColumn(format="localized") for c in ("Aptos", "Comparecimento")}
    | {"Ano": st.column_config.NumberColumn(format="%d")},
)

# --- Outros cargos ------------------------------------------------------------
st.header("Outros cargos")
outros = sorted(c for c in votos.cd_cargo.unique() if c != 1)
if not outros:
    st.caption("No exterior só se vota para Presidente.")
else:
    ano = st.segmented_control("Ano", list(fontes.ANOS), default=2026, key="fi_ano_outros") or 2026
    abas = st.tabs([fontes.CARGOS[c] for c in outros])
    for aba, cargo in zip(abas, outros):
        v = votos[(votos.cd_cargo == cargo) & (votos.ano == ano)]
        if v.empty:
            aba.caption("Sem dados para este ano.")
            continue
        for turno in sorted(v.nr_turno.unique()):
            t = v[v.nr_turno == turno].sort_values("qt_votos", ascending=False).copy()
            t["%"] = 100 * t.qt_votos / t.qt_votos.sum()
            aba.markdown(f"**{turno}º turno**" + (" — 20 mais votados" if len(t) > 20 else ""))
            aba.dataframe(
                t.head(20)[["nm_votavel", "nr_votavel", "sg_partido", "qt_votos", "%", "ds_situacao"]].rename(
                    columns={"nm_votavel": "Candidato", "nr_votavel": "Número", "sg_partido": "Partido", "qt_votos": "Votos", "ds_situacao": "Situação"}
                ),
                hide_index=True,
                width="stretch",
                column_config={"%": st.column_config.NumberColumn(format="%.1f"), "Votos": st.column_config.NumberColumn(format="localized")},
            )
