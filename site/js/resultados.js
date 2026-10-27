// Vista "Resultados": um cargo, um ano, um turno — mapa + totais, candidatos, partidos e unidades do recorte.

import {
  U, agregar, candidatosUF, corrida, indicesDoRecorte, linha, nomeCargo, nomeVencedor, saldoPTPL, siglaVencedora, votosEm,
} from "./dados.js";
import { coresPartidos, cssVar, esc, fmtInt, fmtMargem, fmtPP, fmtPct, normalizar, ok, pct, rampaDoPartido, ROXO, AZUL, VERMELHO, classeSinal } from "./formato.js";
import { escalaDivergente, escalaSequencial, legendaCategorias, legendaRampa } from "./mapa.js";
import { barras, kpi, nomeUF, tabela } from "./painel.js";

const PARTICIPACAO = {
  abstencao: { rotulo: "Abstenção", titulo: "Abstenção (% dos aptos)", campo: "pAbst" },
  brancos: { rotulo: "Brancos", titulo: "Brancos (% do comparecimento)", campo: "pBr" },
  nulos: { rotulo: "Nulos", titulo: "Nulos (% do comparecimento)", campo: "pNu" },
};
const linhaDica = (a, b) => `<div class="linha"><span>${esc(a)}</span><span>${b}</span></div>`;
const rotuloCand = (x) => `${x.nome} (${x.partido})`;
const tagSituacao = (s) => (/eleito|2º turno/i.test(s) && !/não eleito/i.test(s) ? s : "");

export function metricas(e, { c }) {
  const semUF = e.uf === "BR" || e.uf === "ZZ";
  const part = Object.entries(PARTICIPACAO).map(([id, m]) => ({ id, rotulo: m.rotulo }));
  if (e.cargo === 1)
    return [
      { id: "saldo", rotulo: "Saldo PT − PL" },
      { id: "vencedor", rotulo: "Mais votado" },
      { id: "delta", rotulo: "Variação desde 2022", desabilitado: e.ano === 2022, dica: "Só para 2026" },
      { id: "candidato", rotulo: "% do candidato" },
      ...part,
    ];
  const candidato = { id: "candidato", rotulo: "% do candidato", desabilitado: semUF, dica: "Escolha uma UF" };
  if (!c.prop) return [{ id: "vencedor", rotulo: "Mais votado" }, candidato, ...part];
  return [{ id: "vencedor", rotulo: "Partido mais votado" }, { id: "partido", rotulo: "% do partido" }, candidato, ...part];
}

export async function preparar(e) {
  const [c, ant] = await Promise.all([corrida(e.cargo, e.ano, e.turno), e.cargo === 1 && e.ano === 2026 ? corrida(1, 2022, e.turno) : null]);
  const cu = c.prop && e.uf !== "BR" ? await candidatosUF(e.cargo, e.ano, e.turno, e.uf) : null;
  const ks = indicesDoRecorte(c, e.uf);
  const tot = agregar(c, ks);

  // candidatos com voto no recorte, mais votado primeiro (nos proporcionais, só com a UF escolhida)
  let cands = null;
  if (!c.prop && (e.cargo === 1 || e.uf !== "BR"))
    cands = c.candidatos.map((x, j) => ({ ...x, rec: tot.comp[j] })).filter((x) => x.rec > 0).sort((a, b) => b.rec - a.rec);
  if (cu) cands = cu.candidatos.map((x) => ({ ...x, rec: x.total }));
  const partidos = c.partidos
    .map((p, j) => ({ ...p, rec: c.prop ? tot.comp[j] : tot.partidos[j] }))
    .filter((p) => p.rec > 0)
    .sort((a, b) => b.rec - a.rec);

  const ms = metricas(e, { c });
  const m = (ms.find((x) => x.id === e.m && !x.desabilitado) ?? ms[0]).id;
  let cand = cands?.find((x) => x.nr === e.c) ?? null;
  if (m === "candidato" && !cand) cand = cands?.[0] ?? null;
  let partido = partidos.find((p) => p.sigla === e.p) ?? null;
  if (m === "partido" && !partido) partido = partidos[0] ?? null;

  const vitorias = new Map();
  for (const k of ks) {
    const s = siglaVencedora(c, k);
    if (s && s !== "empate") vitorias.set(s, (vitorias.get(s) ?? 0) + 1);
  }
  return { c, ant, cu, ks, tot, cands, partidos, m, cand, partido, cores: coresPartidos(vitorias) };
}

function valor(ctx, e, k) {
  const { c, ant, cand, partido, cores } = ctx;
  const cd = c.cd[k];
  switch (ctx.m) {
    case "saldo":
      return saldoPTPL(c, k);
    case "delta": {
      const s = saldoPTPL(c, k), sa = saldoPTPL(ant, ant.idx.get(cd));
      return ok(s) && ok(sa) ? s - sa : null;
    }
    case "vencedor": {
      const s = siglaVencedora(c, k);
      return s == null || s === "empate" ? s : cores[s] ? s : "outros";
    }
    case "candidato": {
      const uf = cand?.uf && cand.uf !== "BR" ? cand.uf : c.prop ? e.uf : null;
      if (!cand || (uf && U.porCd.get(cd)?.uf !== uf)) return null;
      return pct(votosEm(cand, cd), c.validos[k]);
    }
    case "partido":
      return partido ? pct(partido.v[k], c.validos[k]) : null;
    default:
      return linha(c, k)[PARTICIPACAO[ctx.m].campo];
  }
}

export function mapa(e, ctx) {
  const { c, m, cand, partido, cores } = ctx;
  const dentro = (u) => e.uf === "BR" || u.uf === e.uf;
  const valores = new Map(), noRecorte = [];
  for (let k = 0; k < c.n; k++) {
    const u = U.porCd.get(c.cd[k]);
    if (!u?.g) continue;
    const v = valor(ctx, e, k);
    valores.set(u.g, v);
    if (dentro(u)) noRecorte.push(v);
  }
  const spec = { valores, dentro, sel: e.u ? U.porCd.get(e.u)?.g : null, uf: e.uf };

  if (m === "vencedor") {
    const n = (cat) => noRecorte.filter((v) => v === cat).length;
    spec.categorias = { ...cores, outros: cssVar("--neutro"), empate: cssVar("--meio") };
    legendaCategorias(c.prop ? "Partido mais votado" : "Partido do mais votado", [
      ...Object.entries(cores).map(([s, cor]) => [s, cor, n(s)]),
      ["Outros partidos", spec.categorias.outros, n("outros")],
      ["Empate", spec.categorias.empate, n("empate")],
    ]);
  } else if (m === "saldo" || m === "delta") {
    spec.escala = escalaDivergente(noRecorte, AZUL, VERMELHO);
    const extremos = m === "saldo" ? ["PL à frente", "PT à frente"] : ["PL ganhou terreno", "PT ganhou terreno"];
    const titulo = m === "saldo" ? "Saldo PT − PL (pp dos válidos)" : "Variação do saldo PT − PL desde 2022";
    legendaRampa(titulo, spec.escala, [fmtPP(spec.escala.min, 0).slice(1), "0", fmtPP(spec.escala.max, 0).slice(1)], extremos);
  } else {
    const rampa = m === "candidato" ? rampaDoPartido(cand?.partido) : m === "partido" ? rampaDoPartido(partido?.sigla) : ROXO;
    spec.escala = escalaSequencial(noRecorte, rampa);
    const titulo =
      m === "candidato" ? `% ${cand ? rotuloCand(cand) : "—"} (válidos)` : m === "partido" ? `% ${partido?.sigla ?? "—"} (válidos, nominal + legenda)` : PARTICIPACAO[m].titulo;
    const { min, max } = spec.escala;
    legendaRampa(titulo, spec.escala, [fmtPct(min, 0), fmtPct((min + max) / 2, 0), fmtPct(max, 0)]);
  }
  return spec;
}

export function dica(e, ctx, u) {
  const { c, m, cand, partido } = ctx;
  const k = c.idx.get(u.cd);
  if (k == null) return linhaDica(nomeCargo(e.cargo), "sem dado");
  let html = linhaDica(c.prop ? "Partido mais votado" : "Mais votado", esc(nomeVencedor(c, k))) + linhaDica("Margem", fmtMargem(c.margem[k]));
  if (e.cargo === 1) {
    const pt = c.porSigla.get("PT"), pl = c.porSigla.get("PL");
    html += linhaDica("PT", fmtPct(pt && pct(pt.v[k], c.validos[k]))) + linhaDica("PL", fmtPct(pl && pct(pl.v[k], c.validos[k])));
    if (m === "delta") html += linhaDica("Saldo desde 2022", fmtPP(valor(ctx, e, k)));
  }
  if (m === "candidato" && cand) html += linhaDica(rotuloCand(cand), fmtPct(valor(ctx, e, k)));
  if (m === "partido" && partido) html += linhaDica(partido.sigla, fmtPct(valor(ctx, e, k)));
  if (PARTICIPACAO[m]) html += linhaDica(PARTICIPACAO[m].rotulo, fmtPct(valor(ctx, e, k)));
  return html;
}

// --- painel ---------------------------------------------------------------------
const corDe = (cores, sigla) => cores[sigla] ?? null;

function porUF(c, ks) {
  const grupos = Map.groupBy(ks, (k) => U.porCd.get(c.cd[k])?.uf ?? "?");
  return [...grupos].map(([uf, kk]) => ({ uf, a: agregar(c, kk) }));
}

function vencedorDe(c, a) {
  let j = -1;
  a.comp.forEach((v, i) => {
    if (v > 0 && (j < 0 || v > a.comp[j])) j = i;
  });
  if (j < 0) return { nome: "—", pct: null };
  const x = c.comp[j];
  return { nome: c.prop ? x.sigla : rotuloCand(x), pct: pct(a.comp[j], a.validos) };
}

function colunasPresidente(c) {
  const iPT = c.partidos.findIndex((p) => p.sigla === "PT"), iPL = c.partidos.findIndex((p) => p.sigla === "PL");
  return {
    calc: (a) => ({ pt: pct(a.partidos[iPT] ?? 0, a.validos), pl: pct(a.partidos[iPL] ?? 0, a.validos) }),
    colunas: [
      { id: "pt", rotulo: "% PT", fmt: fmtPct },
      { id: "pl", rotulo: "% PL", fmt: fmtPct },
      { id: "saldo", rotulo: "PT − PL", fmt: fmtPP, classe: classeSinal },
    ],
  };
}

function tabelaUnidades(e, ctx) {
  const { c, ks } = ctx;
  const pres = e.cargo === 1 ? colunasPresidente(c) : null;
  const extra = [];
  if (ctx.m === "candidato" && ctx.cand) extra.push({ id: "mcand", rotulo: `% ${ctx.cand.nome}`, fmt: fmtPct });
  if (ctx.m === "partido" && ctx.partido) extra.push({ id: "mpart", rotulo: `% ${ctx.partido.sigla}`, fmt: fmtPct });
  const base = [{ id: "validos", rotulo: "Válidos", fmt: fmtInt }];
  const fim = [{ id: "abst", rotulo: "Abst.", fmt: fmtPct }];

  if (e.uf === "BR") {
    const itens = porUF(c, ks).map(({ uf, a }) => {
      const venc = vencedorDe(c, a);
      const item = { nome: nomeUF(uf), validos: a.validos, abst: a.pAbst, venc: venc.nome, pvenc: venc.pct, ir: { uf, u: null } };
      if (pres) Object.assign(item, pres.calc(a), { saldo: pres.calc(a).pt - pres.calc(a).pl });
      // "% do partido" só existe nos proporcionais, onde os competidores são os próprios partidos
      if (ctx.m === "partido" && ctx.partido) item.mpart = pct(a.comp[c.partidos.findIndex((p) => p.sigla === ctx.partido.sigla)], a.validos);
      return item;
    });
    const meio = pres ? pres.colunas : [{ id: "venc", rotulo: c.prop ? "Partido mais votado" : "Mais votado" }, { id: "pvenc", rotulo: "%", fmt: fmtPct }];
    return `<h3>Por UF</h3>` + tabela("uf", [{ id: "nome", rotulo: "UF" }, ...base, ...meio, ...extra.filter((x) => x.id === "mpart"), ...fim], itens);
  }

  const itens = ks.map((k) => {
    const u = U.porCd.get(c.cd[k]);
    const l = linha(c, k);
    const item = { nome: u?.nome ?? c.cd[k], validos: l.validos, abst: l.pAbst, venc: nomeVencedor(c, k), margem: c.margem[k], ir: { u: c.cd[k] } };
    if (pres) {
      const pt = c.porSigla.get("PT"), pl = c.porSigla.get("PL");
      Object.assign(item, { pt: pct(pt?.v[k] ?? 0, l.validos), pl: pct(pl?.v[k] ?? 0, l.validos), saldo: saldoPTPL(c, k) });
    }
    if (extra.length) item[extra[0].id] = valor(ctx, e, k);
    return item;
  });
  const meio = pres ? pres.colunas : [{ id: "venc", rotulo: c.prop ? "Partido mais votado" : "Mais votado" }, { id: "margem", rotulo: "Margem", fmt: fmtMargem }];
  const titulo = { ZZ: "Por cidade", DF: "Por Região Administrativa" }[e.uf] ?? "Por município";
  return `<h3>${titulo} (${fmtInt(itens.length)})</h3>` + tabela("unidades", [{ id: "nome", rotulo: "Nome" }, ...base, ...meio, ...extra, ...fim], itens);
}

export function painel(e, ctx) {
  const { c, tot, cands, partidos, cores, m } = ctx;
  const api = c.fonte.filter((f) => !f.startsWith("csv"));
  let html = `<h2>${nomeUF(e.uf)}</h2><p class="sub">${nomeCargo(e.cargo)} · ${e.ano} · ${e.turno}º turno${
    api.length ? ` · <span title="Fonte: ${esc(api.join(", "))}">dados da API/boletins do TSE até o CSV oficial</span>` : ""
  }</p>`;
  if (!tot.aptos) return html + `<p class="sub">Não houve ${e.turno}º turno para ${nomeCargo(e.cargo)} em ${nomeUF(e.uf)} em ${e.ano}.</p>`;

  // indicadores: os dois primeiros (candidatos ou partidos) + participação
  const topo = cands ?? (c.prop ? partidos.map((p) => ({ nome: p.sigla, partido: p.sigla, rec: p.rec, sigla: true })) : []);
  const kpis = topo
    .slice(0, 2)
    .map((x) => kpi(x.sigla ? x.nome : rotuloCand(x), fmtPct(pct(x.rec, tot.validos), 2), `${fmtInt(x.rec)} votos`, corDe(cores, x.partido)));
  kpis.push(kpi("Comparecimento", fmtPct(tot.pComp), `${fmtInt(tot.comparecimento)} de ${fmtInt(tot.aptos)} aptos`));
  kpis.push(kpi("Abstenção", fmtPct(tot.pAbst), `${fmtInt(tot.abstencoes)} eleitores`));
  if (kpis.length < 4) kpis.push(kpi("Brancos", fmtPct(tot.pBr), "do comparecimento"), kpi("Nulos", fmtPct(tot.pNu), "do comparecimento"));
  html += `<div class="kpis">${kpis.slice(0, 4).join("")}</div>`;
  html += `<p class="sub nota-kpi">Válidos ${fmtInt(tot.validos)} · Brancos ${fmtPct(tot.pBr)} · Nulos ${fmtPct(tot.pNu)} do comparecimento</p>`;

  if (!c.prop && cands) {
    html += `<h3>Votos válidos por candidato</h3><p class="sub">Clique num candidato para ver o mapa dos seus votos.</p>`;
    html += barras(
      cands.map((x) => ({
        rotulo: rotuloCand(x),
        pct: pct(x.rec, tot.validos),
        detalhe: `${fmtPct(pct(x.rec, tot.validos), 2)} · ${fmtInt(x.rec)}`,
        cor: corDe(cores, x.partido),
        tag: tagSituacao(x.situacao),
        ir: { c: x.nr, m: "candidato" },
        ativo: m === "candidato" && ctx.cand?.nr === x.nr,
      })),
    );
  }

  if (c.prop) {
    const eleitos = (p) => (e.uf === "BR" ? Object.values(p.eleitos).reduce((a, b) => a + b, 0) : p.eleitos[e.uf] ?? 0);
    html += `<h3>Partidos</h3><p class="sub">Votos nominais + legenda. Clique para ver o mapa do partido.</p>`;
    html += tabela(
      "partidos",
      [
        { id: "nome", rotulo: "Partido", fmt: (s) => `<span class="ponto" style="--c:${corDe(cores, s) ?? cssVar("--neutro")}"></span>${esc(s)}` },
        { id: "rec", rotulo: "Votos", fmt: fmtInt },
        { id: "p", rotulo: "%", fmt: fmtPct },
        { id: "eleitos", rotulo: "Eleitos", fmt: fmtInt },
      ],
      partidos.map((p) => ({ nome: p.sigla, rec: p.rec, p: pct(p.rec, tot.validos), eleitos: eleitos(p), ir: { p: p.sigla, m: "partido" } })),
    );
    if (cands) {
      html += `<h3>Candidatos (${fmtInt(cands.length)})</h3>
        <input type="search" class="filtro" data-filtro="t-candidatos" placeholder="Filtrar por nome, número ou partido…" aria-label="Filtrar candidatos">`;
      html += tabela(
        "candidatos",
        [
          { id: "nome", rotulo: "Candidato" },
          { id: "partido", rotulo: "Partido" },
          { id: "rec", rotulo: "Votos", fmt: fmtInt },
          { id: "p", rotulo: "%", fmt: (x) => fmtPct(x, 2) },
          { id: "situacao", rotulo: "Situação", fmt: (s) => (tagSituacao(s) ? `<span class="tag">${esc(s)}</span>` : esc(s)) },
        ],
        cands.map((x) => ({
          nome: `${x.nome} · ${x.nr}`,
          partido: x.partido,
          rec: x.rec,
          p: pct(x.rec, tot.validos),
          situacao: x.situacao,
          busca: normalizar(`${x.nome} ${x.nr} ${x.partido}`),
          ir: { c: x.nr, m: "candidato" },
        })),
      );
    } else {
      html += `<p class="sub">Escolha uma UF para ver os candidatos.</p>`;
    }
  }
  return html + tabelaUnidades(e, ctx);
}
