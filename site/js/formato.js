// Cores, formatação pt-BR e utilidades de HTML comuns a todas as vistas.

// Paleta do painel Streamlit (validada para daltonismo): PT vermelho, PL azul; demais partidos em
// amarelo, verde e roxo (os três que mais vencem no recorte), o resto em cinza claro neutro.
export const COR = { PT: "#e34948", PL: "#2a78d6" };
export const CATEGORICAS = ["#eda100", "#2f9e2f", "#6250d6"];
export const AZUL = ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281"];
export const VERMELHO = ["#fbd5d4", "#f29493", "#e34948", "#b8302f", "#7f1a19"];
export const ROXO = ["#e3defa", "#ab9ff0", "#6250d6", "#4a3aa7", "#2e2373"];
export const VERDE = ["#d3f0d3", "#86cf86", "#2f9e2f", "#008300", "#004d00"];

export const rampaDoPartido = (sigla) => (sigla === "PT" ? VERMELHO : sigla === "PL" ? AZUL : ROXO);

// PT e PL sempre com a sua cor; os três partidos que mais vencem (`vitorias`: Map sigla → unidades) ganham
// as categóricas; quem não está no mapa retornado é "outros" (cinza neutro).
export function coresPartidos(vitorias) {
  const cores = { ...COR };
  [...vitorias]
    .filter(([s]) => !cores[s])
    .sort((a, b) => b[1] - a[1])
    .slice(0, CATEGORICAS.length)
    .forEach(([s], i) => (cores[s] = CATEGORICAS[i]));
  return cores;
}

const nf = new Intl.NumberFormat("pt-BR");
const dec = (x, c) => x.toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
export const ok = (x) => typeof x === "number" && Number.isFinite(x);
export const fmtInt = (x) => (ok(x) ? nf.format(x) : "—");
export const fmtPct = (x, c = 1) => (ok(x) ? dec(x, c) + "%" : "—");
export const fmtPP = (x, c = 1) => (ok(x) ? (x > 0 ? "+" : x < 0 ? "−" : "") + dec(Math.abs(x), c) + " pp" : "—");
export const fmtMargem = (x) => (ok(x) ? dec(x, 1) + " pp" : "—");
export const pct = (a, b) => (b ? (100 * a) / b : null);
export const classeSinal = (x) => (ok(x) && x > 0 ? "positivo" : ok(x) && x < 0 ? "negativo" : "");

export const cssVar = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
export const normalizar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
export const $ = (s) => document.querySelector(s);
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function quantil(valores, q) {
  const s = valores.filter(ok).sort((a, b) => a - b);
  return s.length ? s[Math.min(s.length - 1, Math.floor(q * (s.length - 1)))] : null;
}

export function mediana(valores) {
  const s = valores.filter(ok).sort((a, b) => a - b);
  if (!s.length) return null;
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
