// Peças de HTML do painel lateral: indicadores, barras e tabelas ordenáveis.
// Linhas e barras clicáveis levam `data-ir` (o que muda no estado) e um link real (abre em nova aba).

import { hashDe } from "./estado.js";
import { cssVar, esc, ok } from "./formato.js";

export const ir = (parcial) => `data-ir="${esc(JSON.stringify(parcial))}"`;
export const link = (parcial, texto) => `<a href="${hashDe(parcial)}" ${ir(parcial)}>${texto}</a>`;

export const kpi = (rotulo, valor, detalhe = "", cor = null) =>
  `<div class="kpi" ${cor ? `style="--c:${cor}"` : ""}><div class="rotulo" title="${esc(rotulo)}">${esc(rotulo)}</div>
   <div class="valor">${valor}</div><div class="detalhe">${detalhe}</div></div>`;

// itens: { rotulo, pct, detalhe, cor, ir?, tag?, ativo? } — a largura é relativa ao maior
export function barras(itens) {
  const max = Math.max(...itens.map((x) => x.pct ?? 0), 0);
  return `<div class="barras">${itens
    .map(
      (x) => `<div class="barra-cand${x.ir ? " clicavel" : ""}${x.ativo ? " ativo" : ""}" ${x.ir ? ir(x.ir) : ""}>
        <span>${esc(x.rotulo)}${x.tag ? ` <span class="tag">${esc(x.tag)}</span>` : ""}</span>
        <span class="num">${x.detalhe}</span>
        <div class="pista"><div style="width:${max ? (100 * (x.pct ?? 0)) / max : 0}%;background:${x.cor ?? cssVar("--neutro")}"></div></div></div>`,
    )
    .join("")}</div>`;
}

// colunas: { id, rotulo, fmt?, classe? }; itens: objetos com os ids + `ir` (opcional) + `busca` (opcional)
const ordens = {};
export function definirOrdem(id, col) {
  const atual = ordens[id];
  ordens[id] = { col, desc: atual?.col === col ? !atual.desc : col !== "nome" };
}

export function tabela(id, colunas, itens, { ordem = null, limite = Infinity } = {}) {
  const { col, desc } = ordens[id] ?? ordem ?? { col: colunas[1].id, desc: true };
  const ordenados = [...itens].sort((a, b) => {
    const x = a[col], y = b[col];
    const r = typeof x === "string" || typeof y === "string" ? String(x ?? "").localeCompare(String(y ?? ""), "pt-BR") : (ok(x) ? x : -Infinity) - (ok(y) ? y : -Infinity);
    return desc ? -r : r;
  });
  const mostrados = ordenados.slice(0, limite);
  const cab = colunas
    .map((c) => `<th data-ordem="${id}:${c.id}" ${c.id === col ? `aria-sort="${desc ? "descending" : "ascending"}"` : ""}>${c.rotulo}</th>`)
    .join("");
  const corpo = mostrados
    .map(
      (l) => `<tr ${l.ir ? ir(l.ir) : ""} ${l.busca ? `data-busca="${esc(l.busca)}"` : ""}>${colunas
        .map((c, i) => {
          const texto = (c.fmt ?? esc)(l[c.id]);
          return `<td class="${c.classe?.(l[c.id]) ?? ""}">${i === 0 && l.ir ? link(l.ir, texto) : texto}</td>`;
        })
        .join("")}</tr>`,
    )
    .join("");
  const resto = ordenados.length - mostrados.length;
  return `<div class="tabela"><table id="t-${id}"><thead><tr>${cab}</tr></thead><tbody>${corpo}</tbody></table></div>${
    resto > 0 ? `<p class="sub">+ ${resto} linhas (ordene ou filtre para ver outras)</p>` : ""
  }`;
}

export const nomeUF = (uf) => ({ BR: "Brasil", ZZ: "Exterior", DF: "Distrito Federal" })[uf] ?? uf;
