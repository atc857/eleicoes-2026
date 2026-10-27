// Mapa MapLibre (WebGL): a malha carrega uma vez; trocar o que se vê só muda o feature-state (cor) de cada
// polígono. Sem mapa de fundo: só a superfície do tema (países vizinhos não parecem "sem dado").

import { U } from "./dados.js";
import { $, cssVar, esc, fmtInt, quantil } from "./formato.js";

const BRASIL = [[-74.0, -33.8], [-34.8, 5.3]];
const VAZIO = ["==", ["get", "g"], ""];
let mapa;
let ufEnquadrada = null;

export async function criarMapa({ malha, ufs, dica, clique }) {
  mapa = new maplibregl.Map({
    container: "mapa",
    style: { version: 8, sources: {}, layers: [{ id: "fundo", type: "background", paint: { "background-color": cssVar("--superficie") } }] },
    bounds: BRASIL,
    fitBoundsOptions: { padding: 20 },
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
  });
  mapa.touchZoomRotate.disableRotation();
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  await new Promise((ok) => mapa.on("load", ok));

  mapa.addSource("malha", { type: "geojson", data: malha, promoteId: "g" });
  mapa.addSource("ufs", { type: "geojson", data: ufs });
  mapa.addLayer({ id: "unidades", type: "fill", source: "malha", paint: { "fill-color": cssVar("--sem-dado") } });
  mapa.addLayer({ id: "bordas", type: "line", source: "malha", paint: { "line-width": 0.3 } });
  mapa.addLayer({ id: "ufs", type: "line", source: "ufs", paint: { "line-width": 1 } });
  mapa.addLayer({ id: "sobre", type: "line", source: "malha", filter: VAZIO, paint: { "line-width": 1.5 } });
  mapa.addLayer({ id: "selecao", type: "line", source: "malha", filter: VAZIO, paint: { "line-width": 2.5 } });
  coresDoTema();

  const el = $("#dica");
  mapa.on("mousemove", "unidades", (ev) => {
    const g = ev.features[0].properties.g;
    mapa.setFilter("sobre", ["==", ["get", "g"], g]);
    mapa.getCanvas().style.cursor = "pointer";
    const u = U.porGeo.get(g);
    el.innerHTML = u ? `<b>${esc(u.nome)} / ${u.uf}</b>${dica(u)}` : "";
    el.hidden = false;
    const { width, height } = mapa.getContainer().getBoundingClientRect();
    const x = ev.point.x + 14 + el.offsetWidth > width ? ev.point.x - 14 - el.offsetWidth : ev.point.x + 14;
    const y = Math.max(8, Math.min(ev.point.y + 14, height - el.offsetHeight - 8));
    el.style.transform = `translate(${x}px, ${y}px)`;
  });
  mapa.on("mouseleave", "unidades", () => {
    mapa.setFilter("sobre", VAZIO);
    mapa.getCanvas().style.cursor = "";
    el.hidden = true;
  });
  mapa.on("click", "unidades", (ev) => {
    const u = U.porGeo.get(ev.features[0].properties.g);
    if (u) clique(u);
  });
}

export function coresDoTema() {
  mapa.setPaintProperty("fundo", "background-color", cssVar("--superficie"));
  mapa.setPaintProperty("bordas", "line-color", cssVar("--linha-unidade"));
  mapa.setPaintProperty("ufs", "line-color", cssVar("--linha-uf"));
  mapa.setPaintProperty("sobre", "line-color", cssVar("--selecao"));
  mapa.setPaintProperty("selecao", "line-color", cssVar("--selecao"));
}

// --- escalas ---------------------------------------------------------------------
// Limites pelos quantis do recorte, para os extremos não lavarem o mapa.
export function escalaDivergente(valores, negativo, positivo) {
  const lim = Math.max(1, Math.ceil(quantil(valores.map(Math.abs), 0.98) ?? 1));
  const cores = [...negativo].reverse().concat([cssVar("--meio")], positivo);
  return { cores, paradas: cores.map((_, i) => -lim + (2 * lim * i) / (cores.length - 1)), min: -lim, max: lim };
}

export function escalaSequencial(valores, rampa) {
  const min = Math.floor(quantil(valores, 0.02) ?? 0);
  let max = Math.ceil(quantil(valores, 0.98) ?? 1);
  if (max <= min) max = min + 1;
  return { cores: rampa, paradas: rampa.map((_, i) => min + ((max - min) * i) / (rampa.length - 1)), min, max };
}

// --- pintura ---------------------------------------------------------------------
// spec: { valores: Map(g → número | categoria), dentro: (u) => bool, sel: g | null, uf,
//         escala } para números, ou { valores, categorias: {categoria: cor}, ... } para categorias.
export function pintar(spec) {
  const semDado = cssVar("--sem-dado");
  const cat = !!spec.categorias;
  let cor;
  if (cat) {
    cor = ["match", ["coalesce", ["feature-state", "c"], ""], ...Object.entries(spec.categorias).flat(), semDado];
    if (!Object.keys(spec.categorias).length) cor = semDado;
  } else {
    const rampa = spec.escala.paradas.flatMap((p, i) => [p, spec.escala.cores[i]]);
    cor = ["case", ["==", ["typeof", ["feature-state", "v"]], "number"], ["interpolate", ["linear"], ["feature-state", "v"], ...rampa], semDado];
  }
  mapa.setPaintProperty("unidades", "fill-color", cor);
  mapa.setPaintProperty("unidades", "fill-opacity", ["case", ["boolean", ["feature-state", "fora"], false], 0.25, 1]);
  for (const u of U.lista) {
    if (!u.g) continue;
    const v = spec.valores.get(u.g) ?? null;
    mapa.setFeatureState({ source: "malha", id: u.g }, cat ? { c: v, v: null, fora: !spec.dentro(u) } : { v, c: null, fora: !spec.dentro(u) });
  }
  mapa.setFilter("selecao", ["==", ["get", "g"], spec.sel || ""]);
  if (spec.uf !== ufEnquadrada) {
    ufEnquadrada = spec.uf;
    if (spec.uf === "BR") mapa.fitBounds(BRASIL, { padding: 20, duration: 500 });
    else if (U.limites[spec.uf]) mapa.fitBounds(U.limites[spec.uf], { padding: 30, duration: 500 });
  }
}

// --- legenda ---------------------------------------------------------------------
export function legendaRampa(titulo, escala, marcas, extremos) {
  $("#legenda").innerHTML = `<div class="titulo">${esc(titulo)}</div>
    <div class="rampa" style="background:linear-gradient(to right, ${escala.cores.join(",")})"></div>
    <div class="marcas">${marcas.map((m) => `<span>${m}</span>`).join("")}</div>
    ${extremos ? `<div class="marcas"><span>← ${esc(extremos[0])}</span><span>${esc(extremos[1])} →</span></div>` : ""}`;
}

// itens: [[rótulo, cor, contagem]]; contagem 0 some da legenda
export function legendaCategorias(titulo, itens) {
  $("#legenda").innerHTML = `<div class="titulo">${esc(titulo)}</div><div class="chips">${itens
    .filter(([, , n]) => n)
    .map(([rotulo, cor, n]) => `<span class="chip" style="--c:${cor}">${esc(rotulo)} · ${fmtInt(n)}</span>`)
    .join("")}<span class="chip" style="--c:${cssVar("--sem-dado")}">Sem dado</span></div>`;
}
