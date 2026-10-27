// Estado da página inteiro na URL: #v=c&turno=1&uf=DF&m=pt&u=DF-RA28 (padrões omitidos).
// Qualquer tela vira um link; voltar/avançar do navegador funcionam.

import { INDICE, U, corridaExiste } from "./dados.js";

export const PADRAO = { v: "r", cargo: 1, ano: 2026, turno: 2, uf: "BR", m: null, c: null, p: null, u: null, min: 5000 };
const NUMERICOS = ["cargo", "ano", "turno", "c", "min"];
// Presidente abre no 2º turno; os demais cargos, no 1º (2º turno de governador só em algumas UFs)
const turnoPadrao = (e) => (e.v === "c" || e.cargo === 1 ? 2 : 1);
const padraoDe = (e, k) => (k === "turno" ? turnoPadrao(e) : PADRAO[k]);

export function lerEstado(hash = location.hash) {
  const q = new URLSearchParams(hash.replace(/^#/, ""));
  const e = { ...PADRAO };
  for (const k of Object.keys(PADRAO)) {
    const x = q.get(k);
    if (x != null && x !== "") e[k] = NUMERICOS.includes(k) ? Number(x) : x;
  }
  if (!["r", "c"].includes(e.v)) e.v = "r";
  if (e.v === "c" || !INDICE.cargos[e.cargo]) e.cargo = 1; // a comparação é só de Presidente
  if (!q.get("turno")) e.turno = turnoPadrao(e);
  if (![2022, 2026].includes(e.ano)) e.ano = PADRAO.ano;
  if (![1, 2].includes(e.turno)) e.turno = PADRAO.turno;
  if (!corridaExiste(e.cargo, e.ano, e.turno) || (e.v === "c" && !corridaExiste(1, 2022, e.turno))) e.turno = 1;
  const ufs = e.cargo === 1 ? [...U.ufs, "ZZ"] : U.ufs;
  if (e.uf !== "BR" && !ufs.includes(e.uf)) e.uf = "BR";
  if (!Number.isInteger(e.c)) e.c = null;
  if (!U.porCd.has(e.u)) e.u = null;
  if (!Number.isFinite(e.min) || e.min < 0) e.min = PADRAO.min;
  return e;
}

// Mudanças que tornam outras escolhas sem sentido: trocar o cargo zera candidato, partido e métrica etc.
function coerente(antes, parcial) {
  const e = { ...antes, ...parcial };
  if ("cargo" in parcial && parcial.cargo !== antes.cargo) Object.assign(e, { c: null, p: null, m: null, turno: turnoPadrao(e), ...parcial });
  if ("v" in parcial && parcial.v !== antes.v && !("turno" in parcial)) e.turno = turnoPadrao(e);
  if ("ano" in parcial && parcial.ano !== antes.ano && !("c" in parcial)) e.c = null;
  if ("v" in parcial && parcial.v !== antes.v && !("m" in parcial)) e.m = null;
  return e;
}

export function hashDe(parcial, base = lerEstado()) {
  const e = coerente(base, parcial);
  const q = new URLSearchParams();
  for (const k of Object.keys(PADRAO)) if (e[k] != null && e[k] !== padraoDe(e, k)) q.set(k, e[k]);
  return "#" + q.toString();
}

let aoMudar = () => {};
export const definirRender = (f) => (aoMudar = f);

export function mudar(parcial) {
  const h = hashDe(parcial);
  history.pushState(null, "", h === "#" ? location.pathname + location.search : h);
  aoMudar();
}
