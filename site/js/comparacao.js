// Vista "Comparação 2022 × 2026" (Presidente): mapa de diferenças ou de viradas, dispersão, rankings e viradas.

import { INDICE, U, agregar, corrida, indicesDoRecorte, linha, nomeVencedor, saldoPTPL, siglaVencedora } from "./dados.js";
import { mudar } from "./estado.js";
import { AZUL, CATEGORICAS, COR, ROXO, VERDE, VERMELHO, classeSinal, cssVar, esc, fmtInt, fmtMargem, fmtPP, fmtPct, mediana, ok, pct } from "./formato.js";
import { escalaDivergente, legendaCategorias, legendaRampa } from "./mapa.js";
import { kpi, nomeUF, tabela } from "./painel.js";

const porPartido = (sigla) => (c, k) => {
  const p = c.porSigla.get(sigla);
  return k == null || !c.validos[k] ? null : pct(p ? p.v[k] : 0, c.validos[k]);
};
const participacao = (campo) => (c, k) => (k == null ? null : linha(c, k)[campo]);

// nivel: valor de um ano numa unidade; agregado: o mesmo para a soma do recorte
const METRICAS = {
  saldo: { rotulo: "Saldo PT − PL", lado: "pt", nivel: saldoPTPL, fmt: fmtPP, extremos: ["PL ganhou terreno", "PT ganhou terreno"] },
  pt: { rotulo: "% PT", lado: "pt", nivel: porPartido("PT"), fmt: fmtPct, extremos: ["caiu", "subiu"] },
  pl: { rotulo: "% PL", lado: "pl", nivel: porPartido("PL"), fmt: fmtPct, extremos: ["caiu", "subiu"] },
  abstencao: { rotulo: "Abstenção", lado: null, nivel: participacao("pAbst"), campo: "pAbst", fmt: fmtPct, extremos: ["caiu", "subiu"] },
  brancos: { rotulo: "Brancos", lado: null, nivel: participacao("pBr"), campo: "pBr", fmt: fmtPct, extremos: ["caiu", "subiu"] },
  nulos: { rotulo: "Nulos", lado: null, nivel: participacao("pNu"), campo: "pNu", fmt: fmtPct, extremos: ["caiu", "subiu"] },
};
const RAMPAS = { pt: [AZUL, VERMELHO], pl: [VERMELHO, AZUL], null: [VERDE, ROXO] };
const VIRADAS = {
  "PT→PL": ["PT → PL", AZUL[4]],
  "PT→PL*": ["PT → PL (apertada)", AZUL[1]],
  "PL→PT": ["PL → PT", VERMELHO[4]],
  "PL→PT*": ["PL → PT (apertada)", VERMELHO[1]],
  outra: ["Outra virada", CATEGORICAS[0]],
};
let aba = "altas";
const linhaDica = (a, b) => `<div class="linha"><span>${esc(a)}</span><span>${b}</span></div>`;

export const metricas = () => [...Object.entries(METRICAS).map(([id, m]) => ({ id, rotulo: m.rotulo })), { id: "viradas", rotulo: "Viradas" }];

export async function preparar(e) {
  const [a, b] = await Promise.all([corrida(1, 2022, e.turno), corrida(1, 2026, e.turno)]);
  const m = metricas().some((x) => x.id === e.m) ? e.m : "saldo";
  const met = METRICAS[m === "viradas" ? "saldo" : m];
  const limiar = INDICE.limiar_virada_apertada;
  const linhas = [];
  for (const cd of new Set([...a.cd, ...b.cd])) {
    const u = U.porCd.get(cd);
    if (!u) continue;
    const ka = a.idx.get(cd), kb = b.idx.get(cd);
    const comparavel = ka != null && kb != null && a.validos[ka] > 0 && b.validos[kb] > 0;
    const x = met.nivel(a, ka), y = met.nivel(b, kb);
    const va = ka == null ? null : siglaVencedora(a, ka), vb = kb == null ? null : siglaVencedora(b, kb);
    const virou = comparavel && va && vb && va !== vb;
    linhas.push({
      u, cd, comparavel, x, y, va, vb, virou,
      d: comparavel && ok(x) && ok(y) ? y - x : null,
      apertada: virou && (a.margem[ka] < limiar || b.margem[kb] < limiar),
      nomeA: nomeVencedor(a, ka), nomeB: nomeVencedor(b, kb),
      margemA: ka == null ? null : a.margem[ka], margemB: kb == null ? null : b.margem[kb],
      aptos: kb == null ? null : b.aptos[kb],
      dentro: e.uf === "BR" || u.uf === e.uf,
    });
  }
  return { a, b, m, met, linhas, porCd: new Map(linhas.map((l) => [l.cd, l])), rec: linhas.filter((l) => l.dentro) };
}

function categoria(l) {
  if (!l.comparavel) return null;
  if (!l.virou) return "manteve";
  const t = `${l.va}→${l.vb}`;
  return VIRADAS[t] ? t + (l.apertada ? "*" : "") : "outra";
}

export function mapa(e, ctx) {
  const { m, met, linhas, rec } = ctx;
  const valores = new Map(linhas.filter((l) => l.u.g).map((l) => [l.u.g, m === "viradas" ? categoria(l) : l.d]));
  const spec = { valores, dentro: (u) => e.uf === "BR" || u.uf === e.uf, sel: e.u ? U.porCd.get(e.u)?.g : null, uf: e.uf };
  if (m === "viradas") {
    spec.categorias = { ...Object.fromEntries(Object.entries(VIRADAS).map(([k, [, cor]]) => [k, cor])), manteve: cssVar("--neutro") };
    const n = (cat) => rec.filter((l) => l.u.g && categoria(l) === cat).length;
    legendaCategorias(`Mais votado 2022 → 2026 (apertada: margem < ${INDICE.limiar_virada_apertada} pp num dos anos)`, [
      ...Object.entries(VIRADAS).map(([k, [rotulo, cor]]) => [rotulo, cor, n(k)]),
      ["Manteve", spec.categorias.manteve, n("manteve")],
    ]);
  } else {
    const [neg, pos] = RAMPAS[met.lado];
    spec.escala = escalaDivergente(rec.filter((l) => l.u.g).map((l) => l.d), neg, pos);
    legendaRampa(`Variação de ${met.rotulo} (pp)`, spec.escala, [fmtPP(spec.escala.min, 0), "0", fmtPP(spec.escala.max, 0)], met.extremos);
  }
  return spec;
}

export function dica(e, ctx, u) {
  const l = ctx.porCd.get(u.cd);
  if (!l) return linhaDica("Presidente", "sem dado");
  const { met } = ctx;
  return (
    linhaDica(`${met.rotulo} 2022`, met.fmt(l.x)) +
    linhaDica(`${met.rotulo} 2026`, met.fmt(l.y)) +
    linhaDica("Variação", l.comparavel ? fmtPP(l.d) : "sem comparação") +
    linhaDica("Mais votado", `${l.va ?? "—"} → ${l.vb ?? "—"}`)
  );
}

// valor da métrica na soma do recorte
function agregado(c, uf, met) {
  const a = agregar(c, indicesDoRecorte(c, uf));
  if (met.campo) return a[met.campo];
  const v = (s) => a.partidos[c.partidos.findIndex((p) => p.sigla === s)] ?? 0;
  if (met === METRICAS.saldo) return pct(v("PT") - v("PL"), a.validos);
  return pct(v(met === METRICAS.pt ? "PT" : "PL"), a.validos);
}

export function painel(e, ctx) {
  const { a, b, met, rec } = ctx;
  const comp = rec.filter((l) => l.comparavel);
  const n = (va, vb) => comp.filter((l) => l.va === va && l.vb === vb).length;
  const [x, y] = [agregado(a, e.uf, met), agregado(b, e.uf, met)];
  let html = `<h2>${nomeUF(e.uf)}</h2><p class="sub">Presidente · ${e.turno}º turno · 2022 → 2026</p>`;
  html += `<div class="kpis">
    ${kpi(`${met.rotulo} no recorte`, met.fmt(y), `2022: ${met.fmt(x)} · <span class="${met.lado ? classeSinal(met.lado === "pl" ? x - y : y - x) : ""}">${fmtPP(y - x)}</span>`)}
    ${kpi("Mediana da variação", fmtPP(mediana(comp.map((l) => l.d))), `entre ${fmtInt(comp.length)} unidades comparáveis`)}
    ${kpi("Viraram PT → PL", fmtInt(n("PT", "PL")), "mais votado mudou", COR.PL)}
    ${kpi("Viraram PL → PT", fmtInt(n("PL", "PT")), "mais votado mudou", COR.PT)}
  </div>`;

  html += `<h3>2022 × 2026, unidade a unidade</h3>
    <p class="sub">${esc(met.rotulo)}. Acima da diagonal, cresceu. Tamanho ∝ eleitorado apto em 2026. Clique num ponto para abrir a ficha.</p>
    <div class="dispersao"><canvas id="dispersao" height="300"></canvas><div id="dica-disp" class="dica-flutuante" hidden></div></div>`;

  const base = comp.filter((l) => (l.aptos ?? 0) >= e.min && ok(l.d)).sort((p, q) => q.d - p.d);
  const top = aba === "altas" ? base.slice(0, 20) : base.slice(-20).reverse();
  const nomeUnid = (l) => `${l.u.nome} / ${l.u.uf === "ZZ" ? "Exterior" : l.u.uf}`;
  html += `<h3>Maiores variações</h3>
    <div class="linha-controles">
      <div class="grupo" role="group" aria-label="Ranking">
        <button data-aba="altas" aria-pressed="${aba === "altas"}">Maiores altas</button><button data-aba="quedas" aria-pressed="${aba === "quedas"}">Maiores quedas</button>
      </div>
      <label class="sub">Aptos ≥ <input type="number" class="minimo" data-min min="0" step="1000" value="${e.min}"></label>
    </div>`;
  html += tabela(
    `rank-${aba}`,
    [
      { id: "nome", rotulo: "Unidade" },
      { id: "x", rotulo: "2022", fmt: met.fmt },
      { id: "y", rotulo: "2026", fmt: met.fmt },
      { id: "d", rotulo: "Variação", fmt: fmtPP, classe: (v) => (met.lado ? classeSinal(met.lado === "pl" ? -v : v) : "") },
      { id: "aptos", rotulo: "Aptos 2026", fmt: fmtInt },
    ],
    top.map((l) => ({ nome: nomeUnid(l), x: l.x, y: l.y, d: l.d, aptos: l.aptos, ir: { u: l.cd } })),
    { ordem: { col: "d", desc: aba === "altas" } },
  );

  const vir = rec.filter((l) => l.virou);
  html += `<h3>Mudaram de mais votado (${fmtInt(vir.length)})</h3>`;
  html += vir.length
    ? tabela(
        "viradas",
        [
          { id: "nome", rotulo: "Unidade" },
          { id: "nomeA", rotulo: "2022" },
          { id: "margemA", rotulo: "Margem", fmt: fmtMargem },
          { id: "nomeB", rotulo: "2026" },
          { id: "margemB", rotulo: "Margem", fmt: fmtMargem },
          { id: "aptos", rotulo: "Aptos 2026", fmt: fmtInt },
        ],
        vir.map((l) => ({ nome: nomeUnid(l) + (l.apertada ? " *" : ""), nomeA: l.nomeA, margemA: l.margemA, nomeB: l.nomeB, margemB: l.margemB, aptos: l.aptos, ir: { u: l.cd } })),
        { ordem: { col: "aptos", desc: true }, limite: 300 },
      ) + `<p class="sub">* apertada: margem abaixo de ${INDICE.limiar_virada_apertada} pp em algum dos anos.</p>`
    : `<p class="sub">Nenhuma.</p>`;

  const sem = rec.filter((l) => !l.comparavel);
  if (sem.length)
    html += `<details class="sub"><summary>${fmtInt(sem.length)} localidade(s) sem comparação</summary>${sem.map((l) => esc(nomeUnid(l))).join(", ")}.
      Boa Esperança do Norte (MT) foi criado depois de 2022; no exterior, cidades que deixaram ou passaram a ter seção.</details>`;
  return html;
}

// --- dispersão (canvas: milhares de pontos sem pesar o DOM) -------------------
export function depois(e, ctx) {
  const canvas = document.getElementById("dispersao");
  for (const b of document.querySelectorAll("[data-aba]"))
    b.addEventListener("click", () => {
      aba = b.dataset.aba;
      mudar({});
    });
  document.querySelector("[data-min]")?.addEventListener("change", (ev) => mudar({ min: Math.max(0, Number(ev.target.value) || 0) }));
  if (!canvas) return;

  const { met } = ctx;
  const pts = ctx.rec.filter((l) => l.comparavel && ok(l.x) && ok(l.y) && l.aptos > 0).sort((p, q) => q.aptos - p.aptos);
  const W = canvas.clientWidth, H = 300, dpr = devicePixelRatio || 1;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const g = canvas.getContext("2d");
  g.scale(dpr, dpr);
  const m = { l: 44, r: 8, t: 8, b: 30 };
  const vals = pts.flatMap((l) => [l.x, l.y]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (!pts.length) [lo, hi] = [0, 1];
  const pad = (hi - lo) * 0.03 || 1;
  [lo, hi] = [lo - pad, hi + pad];
  const sx = (v) => m.l + ((v - lo) / (hi - lo)) * (W - m.l - m.r);
  const sy = (v) => H - m.b - ((v - lo) / (hi - lo)) * (H - m.t - m.b);
  const passo = [1, 2, 5, 10, 20, 25, 50, 100].find((s) => (hi - lo) / s <= 6) ?? 100;

  g.font = "11px system-ui, sans-serif";
  g.fillStyle = cssVar("--suave");
  g.strokeStyle = cssVar("--borda");
  g.lineWidth = 1;
  for (let t = Math.ceil(lo / passo) * passo; t <= hi; t += passo) {
    g.beginPath();
    g.moveTo(sx(t), m.t);
    g.lineTo(sx(t), H - m.b);
    g.moveTo(m.l, sy(t));
    g.lineTo(W - m.r, sy(t));
    g.stroke();
    g.textAlign = "center";
    g.fillText(String(t), sx(t), H - m.b + 14);
    g.textAlign = "right";
    g.fillText(String(t), m.l - 6, sy(t) + 4);
  }
  g.textAlign = "center";
  g.fillText("2022", (m.l + W - m.r) / 2, H - 2);
  g.save();
  g.translate(10, (m.t + H - m.b) / 2);
  g.rotate(-Math.PI / 2);
  g.fillText("2026", 0, 0);
  g.restore();
  g.setLineDash([4, 4]);
  g.strokeStyle = cssVar("--sem-dado");
  g.beginPath();
  g.moveTo(sx(lo), sy(lo));
  g.lineTo(sx(hi), sy(hi));
  g.stroke();
  g.setLineDash([]);

  const cor = met.lado === "pt" ? COR.PT : met.lado === "pl" ? COR.PL : ROXO[2];
  const raio = (l) => Math.min(14, Math.max(1.5, Math.sqrt(l.aptos) / 40));
  g.globalAlpha = 0.5;
  g.fillStyle = cor;
  for (const l of pts) {
    g.beginPath();
    g.arc(sx(l.x), sy(l.y), raio(l), 0, 2 * Math.PI);
    g.fill();
  }
  g.globalAlpha = 1;
  const sel = e.u && ctx.porCd.get(e.u);
  if (sel && pts.includes(sel)) {
    g.strokeStyle = cssVar("--selecao");
    g.lineWidth = 2;
    g.beginPath();
    g.arc(sx(sel.x), sy(sel.y), raio(sel) + 3, 0, 2 * Math.PI);
    g.stroke();
  }

  const dica = document.getElementById("dica-disp");
  const perto = (ev) => {
    const r = canvas.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top;
    let melhor = null, dist = Infinity;
    for (const l of pts) {
      const d = Math.hypot(sx(l.x) - px, sy(l.y) - py) - raio(l);
      if (d < dist) [melhor, dist] = [l, d];
    }
    return dist <= 4 ? { l: melhor, px, py } : null;
  };
  canvas.addEventListener("mousemove", (ev) => {
    const p = perto(ev);
    canvas.style.cursor = p ? "pointer" : "";
    dica.hidden = !p;
    if (!p) return;
    const { l } = p;
    dica.innerHTML = `<b>${esc(l.u.nome)} / ${l.u.uf}</b>` + dicaLinhas(met, l);
    dica.style.left = `${Math.min(p.px + 12, W - dica.offsetWidth - 4)}px`;
    dica.style.top = `${Math.max(0, p.py - dica.offsetHeight - 8)}px`;
  });
  canvas.addEventListener("mouseleave", () => (dica.hidden = true));
  canvas.addEventListener("click", (ev) => {
    const p = perto(ev);
    if (p) mudar({ u: p.l.cd });
  });
}

const dicaLinhas = (met, l) =>
  linhaDica("2022", met.fmt(l.x)) + linhaDica("2026", met.fmt(l.y)) + linhaDica("Variação", fmtPP(l.d)) + linhaDica("Aptos 2026", fmtInt(l.aptos));
