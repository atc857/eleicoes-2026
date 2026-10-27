// Boletim Urna 2022 × 2026 — site estático. Liga controles, estado (URL), mapa e painel.
// Cada vista (resultados, comparação) expõe: preparar(e) → ctx, metricas, mapa, dica, painel e, opcionalmente, depois.

import { INDICE, U, corrida, corridaExiste, definirAvisoCarga, iniciarDados, nomeCargo } from "./js/dados.js";
import { definirRender, lerEstado, mudar } from "./js/estado.js";
import { fichaHtml } from "./js/ficha.js";
import { $, esc, normalizar } from "./js/formato.js";
import { coresDoTema, criarMapa, pintar } from "./js/mapa.js";
import { definirOrdem, nomeUF } from "./js/painel.js";
import * as comparacao from "./js/comparacao.js";
import * as resultados from "./js/resultados.js";

let geracao = 0; // renderizações mais novas descartam as antigas que ainda esperavam dados
let atual = null; // { e, vista, ctx } da última renderização, para a dica do mapa

async function render() {
  const minha = ++geracao;
  const t0 = performance.now();
  const e = lerEstado();
  const vista = e.v === "c" ? comparacao : resultados;
  controles(e);
  try {
    const ctx = await vista.preparar(e);
    if (minha !== geracao) return;
    atual = { e, vista, ctx };
    botoesMetricas(e, vista, ctx);
    pintar(vista.mapa(e, ctx));
    const html = e.u ? await fichaHtml(e) : vista.painel(e, ctx);
    if (minha !== geracao) return;
    const painel = $("#painel");
    const manterRolagem = painel.dataset.chave === `${e.v}|${e.u}`;
    const rolagem = painel.scrollTop;
    painel.innerHTML = html + rodape(Math.round(performance.now() - t0));
    painel.dataset.chave = `${e.v}|${e.u}`;
    painel.scrollTop = manterRolagem ? rolagem : 0;
    if (!e.u) vista.depois?.(e, ctx);
    document.title = `${e.u ? U.porCd.get(e.u).nome : nomeUF(e.uf)} · ${e.v === "c" ? "Comparação 2022 × 2026" : `${nomeCargo(e.cargo)} ${e.ano}`}`;
  } catch (erro) {
    console.error(erro);
    if (minha === geracao) $("#painel").innerHTML = `<p class="erro">Não foi possível carregar os dados (${esc(erro.message)}). Tente de novo.</p>`;
  }
}

const rodape = (ms) => `<p class="nota">Fontes: TSE (CSV oficial; 2º turno de 2026 pela API e pelos boletins de urna do DF até o CSV sair);
  malhas IBGE e IDE-DF. Percentuais de candidatos e partidos sobre votos válidos; abstenção sobre aptos; brancos e nulos sobre
  comparecimento. Dados gerados em ${esc(INDICE.gerado_em.replace("T", " "))}. Atualizado em ${ms} ms.</p>`;

function controles(e) {
  for (const g of document.querySelectorAll(".grupo[data-campo]:not(#metricas)"))
    for (const b of g.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.v === String(e[g.dataset.campo])));
  for (const el of document.querySelectorAll(".so-resultados")) el.hidden = e.v === "c";
  $("#cargo").value = e.cargo;
  $('[data-campo="turno"] [data-v="2"]').disabled = e.v === "c" ? false : !corridaExiste(e.cargo, e.ano, 2);
  const ufs = ["BR", ...U.ufs, ...(e.cargo === 1 ? ["ZZ"] : [])];
  const sel = $("#uf");
  if (sel.dataset.opcoes !== ufs.join()) {
    sel.innerHTML = ufs.map((u) => `<option value="${u}">${nomeUF(u)}</option>`).join("");
    sel.dataset.opcoes = ufs.join();
  }
  sel.value = e.uf;
}

function botoesMetricas(e, vista, ctx) {
  $("#metricas").innerHTML = vista
    .metricas(e, ctx)
    .map(
      (m) =>
        `<button data-v="${m.id}" aria-pressed="${m.id === ctx.m}" ${m.desabilitado ? `disabled title="${esc(m.dica ?? "")}"` : ""}>${esc(m.rotulo)}</button>`,
    )
    .join("");
}

function ligar() {
  $("#cargo").innerHTML = Object.entries(INDICE.cargos)
    .map(([c, nome]) => `<option value="${c}">${nome}</option>`)
    .join("");
  $("#cargo").addEventListener("change", (ev) => mudar({ cargo: Number(ev.target.value) }));
  $("#uf").addEventListener("change", (ev) => {
    const e = lerEstado();
    mudar({ uf: ev.target.value, u: null, c: e.cargo === 1 ? e.c : null });
  });

  document.querySelector(".barra").addEventListener("click", (ev) => {
    const b = ev.target.closest(".grupo[data-campo] button");
    if (!b || b.disabled) return;
    const campo = b.closest(".grupo").dataset.campo;
    mudar({ [campo]: ["ano", "turno"].includes(campo) ? Number(b.dataset.v) : b.dataset.v });
  });

  const painel = $("#painel");
  painel.addEventListener("click", (ev) => {
    const th = ev.target.closest("th[data-ordem]");
    if (th) {
      const [id, col] = th.dataset.ordem.split(":");
      definirOrdem(id, col);
      return render();
    }
    const alvo = ev.target.closest("[data-ir]");
    if (!alvo) return;
    if (ev.target.closest("a") && (ev.ctrlKey || ev.metaKey || ev.shiftKey)) return; // nova aba
    ev.preventDefault();
    mudar(JSON.parse(alvo.dataset.ir));
  });
  painel.addEventListener("input", (ev) => {
    if (!ev.target.matches("[data-filtro]")) return;
    const q = normalizar(ev.target.value.trim());
    for (const tr of document.querySelectorAll(`#${ev.target.dataset.filtro} tbody tr`)) tr.hidden = q && !tr.dataset.busca?.includes(q);
  });

  // busca de unidade: prefixo primeiro, depois "contém"; Enter escolhe o primeiro
  const busca = $("#busca"), sug = $("#sugestoes");
  let achados = [];
  const escolher = (u) => {
    busca.value = "";
    sug.hidden = true;
    const e = lerEstado();
    mudar({ u: u.cd, uf: u.uf === "ZZ" && e.cargo !== 1 ? "BR" : u.uf });
  };
  busca.addEventListener("input", () => {
    const q = normalizar(busca.value.trim());
    if (q.length < 2) return void (sug.hidden = true);
    const comeca = U.lista.filter((u) => u.chave.startsWith(q));
    const contem = U.lista.filter((u) => !u.chave.startsWith(q) && u.chave.includes(q));
    achados = [...comeca, ...contem].slice(0, 8);
    sug.innerHTML =
      achados.map((u, i) => `<li data-i="${i}">${esc(u.nome)} <small>${u.tipo === "ra" ? "RA · " : ""}${nomeUF(u.uf)}</small></li>`).join("") ||
      "<li>Nada encontrado</li>";
    sug.hidden = false;
  });
  busca.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && achados[0] && !sug.hidden) escolher(achados[0]);
    if (ev.key === "Escape") sug.hidden = true;
  });
  busca.addEventListener("blur", () => setTimeout(() => (sug.hidden = true), 150));
  sug.addEventListener("mousedown", (ev) => {
    const li = ev.target.closest("li[data-i]");
    if (li) escolher(achados[+li.dataset.i]);
  });

  window.addEventListener("popstate", render);
  window.addEventListener("hashchange", render);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    coresDoTema();
    render();
  });

  let aviso;
  definirAvisoCarga((n) => {
    clearTimeout(aviso);
    if (n > 0) aviso = setTimeout(() => ($("#carregando").hidden = false), 150);
    else $("#carregando").hidden = true;
  });
}

// --- início -------------------------------------------------------------------
const malhas = Promise.all([fetch("dados/malha.json").then((r) => r.json()), fetch("dados/ufs.json").then((r) => r.json())]);
await iniciarDados();
const e0 = lerEstado();
corrida(e0.v === "c" ? 1 : e0.cargo, e0.ano, e0.turno); // em paralelo com a criação do mapa
const [malha, ufs] = await malhas;
await criarMapa({
  malha,
  ufs,
  dica: (u) => (atual ? atual.vista.dica(atual.e, atual.ctx, u) : ""),
  clique: (u) => mudar({ u: u.cd }),
});
ligar();
definirRender(render);
await render();
$("#carregando").hidden = true;
// Presidente nos quatro turnos chega em segundo plano: ficha e comparação não esperam rede
for (const [ano, turno] of [[2026, 2], [2022, 2], [2026, 1], [2022, 1]]) corrida(1, ano, turno);
