// Carga e preparo dos JSON de dados/ (gerados por `boletim-urna site`). Cada arquivo é buscado uma vez;
// votos esparsos viram vetores densos (Int32Array por candidato/partido, alinhados a `cd`).

import { normalizar, pct } from "./formato.js";

export const U = { lista: [], porCd: new Map(), porGeo: new Map(), limites: {}, ufs: [] };
export const INDICE = {};
export const CAMPOS = ["aptos", "comparecimento", "abstencoes", "brancos", "nulos", "validos"];

export async function iniciarDados() {
  const [u, indice] = await Promise.all([buscarJson("unidades"), buscarJson("indice")]);
  u.cd.forEach((cd, i) => {
    const x = { cd, g: u.g[i], nome: u.nome[i], uf: u.uf[i], tipo: u.tipo[i], chave: normalizar(u.nome[i]) };
    U.lista.push(x);
    U.porCd.set(cd, x);
    if (x.g) U.porGeo.set(x.g, x);
  });
  U.limites = u.limites_uf;
  U.ufs = Object.keys(u.limites_uf).sort();
  Object.assign(INDICE, indice);
}

export const nomeCargo = (cargo) => INDICE.cargos[cargo];
export const proporcional = (cargo) => INDICE.proporcionais.includes(+cargo);
export const corridaExiste = (cargo, ano, turno) => INDICE.corridas.some((c) => c.cargo === +cargo && c.ano === +ano && c.turno === +turno);

// --- busca com cache e contagem de pendentes (para o aviso "Carregando…") -------
const cache = new Map();
let pendentes = 0;
export let aoMudarPendentes = () => {};
export const definirAvisoCarga = (f) => (aoMudarPendentes = f);

function buscarJson(nome) {
  pendentes++;
  aoMudarPendentes(pendentes);
  return fetch(`dados/${nome}.json`)
    .then((r) => {
      if (!r.ok) throw new Error(`dados/${nome}.json: HTTP ${r.status}`);
      return r.json();
    })
    .finally(() => aoMudarPendentes(--pendentes));
}

function buscar(nome, preparar) {
  if (!cache.has(nome)) {
    const p = buscarJson(nome).then(preparar);
    p.catch(() => cache.delete(nome)); // nova tentativa no próximo clique
    cache.set(nome, p);
  }
  return cache.get(nome);
}

export const corrida = (cargo, ano, turno) => buscar(`c${cargo}_${ano}_${turno}`, prepararCorrida);
export const candidatosUF = (cargo, ano, turno, uf) => buscar(`c${cargo}_${ano}_${turno}_${uf}`, prepararUF);
export const ficha = (uf) => buscar(`ficha_${uf}`, (d) => d);

// --- preparo ---------------------------------------------------------------------
function denso(n, [indices, votos]) {
  const v = new Int32Array(n);
  for (let t = 0; t < indices.length; t++) v[indices[t]] = votos[t];
  return v;
}

const indexar = (cds) => new Map(cds.map((cd, k) => [cd, k]));

// Corrida (cargo/ano/turno) no Brasil todo. `comp` = quem disputa o "mais votado" de cada unidade:
// candidatos nos majoritários, partidos (nominal + legenda) nos proporcionais.
function prepararCorrida(d) {
  const n = d.cd.length;
  const c = { cargo: d.cargo, ano: d.ano, turno: d.turno, fonte: d.fonte, n, cd: d.cd, idx: indexar(d.cd), prop: proporcional(d.cargo) };
  for (const campo of CAMPOS) c[campo] = Int32Array.from(d[campo]);
  if (c.prop) {
    c.partidos = d.partidos.map((p, j) => ({ ...p, v: denso(n, d.votos[j]), idx: c.idx }));
  } else {
    c.candidatos = d.candidatos.map((x, j) => ({ ...x, uf: x.uf ?? "BR", v: denso(n, d.votos[j]), idx: c.idx }));
    const porSigla = new Map();
    for (const x of c.candidatos) {
      if (!porSigla.has(x.partido)) porSigla.set(x.partido, { sigla: x.partido, total: 0, v: new Int32Array(n), idx: c.idx });
      const p = porSigla.get(x.partido);
      p.total += x.total;
      for (let k = 0; k < n; k++) p.v[k] += x.v[k];
    }
    c.partidos = [...porSigla.values()].sort((a, b) => b.total - a.total);
  }
  c.porSigla = new Map(c.partidos.map((p) => [p.sigla, p]));
  c.comp = c.prop ? c.partidos : c.candidatos;

  // mais votado e margem sobre o 2º em cada unidade; -1 = sem voto válido, -2 = empate no topo
  c.venc = new Int32Array(n).fill(-1);
  c.margem = new Float64Array(n).fill(NaN);
  const v1 = new Int32Array(n), v2 = new Int32Array(n);
  c.comp.forEach((x, j) => {
    for (let k = 0; k < n; k++) {
      const q = x.v[k];
      if (q > v1[k]) [v2[k], v1[k], c.venc[k]] = [v1[k], q, j];
      else if (q > v2[k]) v2[k] = q;
    }
  });
  for (let k = 0; k < n; k++) {
    if (v1[k] > 0 && v1[k] === v2[k]) c.venc[k] = -2;
    if (c.validos[k]) c.margem[k] = pct(v1[k] - v2[k], c.validos[k]);
  }
  return c;
}

function prepararUF(d) {
  const n = d.cd.length, idx = indexar(d.cd);
  return { cd: d.cd, idx, candidatos: d.candidatos.map((x, j) => ({ ...x, v: denso(n, d.votos[j]), idx })) };
}

// --- consultas -------------------------------------------------------------------
export const votosEm = (item, cd) => {
  const k = item.idx.get(cd);
  return k == null ? 0 : item.v[k];
};

export const siglaVencedora = (c, k) =>
  c.venc[k] === -1 ? null : c.venc[k] === -2 ? "empate" : c.prop ? c.partidos[c.venc[k]].sigla : c.candidatos[c.venc[k]].partido;

export const nomeVencedor = (c, k) => {
  if (k == null || c.venc[k] === -1) return "—";
  if (c.venc[k] === -2) return "Empate";
  const x = c.comp[c.venc[k]];
  return c.prop ? x.sigla : `${x.nome} (${x.partido})`;
};

export function taxas(p) {
  return {
    ...p,
    pComp: pct(p.comparecimento, p.aptos),
    pAbst: pct(p.abstencoes, p.aptos),
    pBr: pct(p.brancos, p.comparecimento),
    pNu: pct(p.nulos, p.comparecimento),
  };
}

export const linha = (c, k) => (k == null ? null : taxas(Object.fromEntries(CAMPOS.map((f) => [f, c[f][k]]))));

// Soma de um conjunto de unidades (índices `ks`): participação e votos de cada competidor e partido.
export function agregar(c, ks) {
  const p = Object.fromEntries(CAMPOS.map((f) => [f, 0]));
  for (const k of ks) for (const f of CAMPOS) p[f] += c[f][k];
  const soma = (x) => {
    let s = 0;
    for (const k of ks) s += x.v[k];
    return s;
  };
  const todas = ks.length === c.n;
  return {
    ...taxas(p),
    comp: c.comp.map((x) => (todas ? x.total : soma(x))),
    partidos: c.prop ? null : c.partidos.map((x) => (todas ? x.total : soma(x))),
  };
}

export const saldoPTPL = (c, k) => {
  if (k == null || !c.validos[k]) return null;
  const pt = c.porSigla.get("PT"), pl = c.porSigla.get("PL");
  return pct((pt ? pt.v[k] : 0) - (pl ? pl.v[k] : 0), c.validos[k]);
};

export const indicesDoRecorte = (c, uf) => {
  const ks = [];
  for (let k = 0; k < c.n; k++) if (uf === "BR" || U.porCd.get(c.cd[k])?.uf === uf) ks.push(k);
  return ks;
};
