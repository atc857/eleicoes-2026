// Ficha de um município, RA ou cidade do exterior: Presidente 2022 × 2026 nos dois turnos, os mais votados
// dos outros cargos e a participação em cada eleição.

import { CAMPOS, U, corrida, ficha as carregarFicha, linha, nomeCargo, nomeVencedor, saldoPTPL, taxas } from "./dados.js";
import { COR, classeSinal, esc, fmtInt, fmtMargem, fmtPP, fmtPct, ok, pct } from "./formato.js";
import { barras, ir, nomeUF } from "./painel.js";

const tagSituacao = (s) => (/eleito|2º turno/i.test(s) && !/não eleito/i.test(s) ? s : "");

function tabelaPresidente(a, b, cd) {
  const ka = a.idx.get(cd), kb = b.idx.get(cd);
  const [la, lb] = [linha(a, ka), linha(b, kb)];
  const parte = (c, k, s) => (k == null || !c.validos[k] ? null : pct(c.porSigla.get(s)?.v[k] ?? 0, c.validos[k]));
  const tr = (rotulo, x, y, fmt, colorir = false) => {
    const d = ok(x) && ok(y) ? y - x : null;
    return `<tr><td>${rotulo}</td><td>${fmt(x)}</td><td>${fmt(y)}</td><td class="${colorir ? classeSinal(d) : ""}">${fmtPP(d)}</td></tr>`;
  };
  return `<table class="ficha"><thead><tr><th></th><th>2022</th><th>2026</th><th>Variação</th></tr></thead><tbody>
    <tr><td>Mais votado</td><td>${esc(nomeVencedor(a, ka))}</td><td>${esc(nomeVencedor(b, kb))}</td><td></td></tr>
    <tr><td>Margem</td><td>${fmtMargem(ka == null ? null : a.margem[ka])}</td><td>${fmtMargem(kb == null ? null : b.margem[kb])}</td><td></td></tr>
    ${tr("% PT", parte(a, ka, "PT"), parte(b, kb, "PT"), fmtPct)}
    ${tr("% PL", parte(a, ka, "PL"), parte(b, kb, "PL"), fmtPct)}
    ${tr("Saldo PT − PL", saldoPTPL(a, ka), saldoPTPL(b, kb), fmtPP, true)}
    ${tr("Abstenção", la?.pAbst, lb?.pAbst, fmtPct)}
    ${tr("Brancos", la?.pBr, lb?.pBr, fmtPct)}
    ${tr("Nulos", la?.pNu, lb?.pNu, fmtPct)}
    <tr><td>Aptos</td><td>${fmtInt(la?.aptos)}</td><td>${fmtInt(lb?.aptos)}</td><td></td></tr>
  </tbody></table>`;
}

function barrasPresidente(c, cd) {
  const k = c.idx.get(cd);
  if (k == null) return `<p class="sub">Sem dado.</p>`;
  return barras(
    c.candidatos
      .map((x) => ({ x, v: x.v[k] }))
      .filter(({ v }) => v > 0)
      .sort((p, q) => q.v - p.v)
      .map(({ x, v }) => ({ rotulo: `${x.nome} (${x.partido})`, pct: pct(v, c.validos[k]), detalhe: `${fmtPct(pct(v, c.validos[k]))} · ${fmtInt(v)}`, cor: COR[x.partido] })),
  );
}

export async function fichaHtml(e) {
  const u = U.porCd.get(e.u);
  const [p1a, p1b, p2a, p2b, sh] = await Promise.all([
    corrida(1, 2022, 1), corrida(1, 2026, 1), corrida(1, 2022, 2), corrida(1, 2026, 2),
    u.uf === "ZZ" ? null : carregarFicha(u.uf),
  ]);
  const dados = sh?.unidades[u.cd];
  const tipo = u.tipo === "ra" ? "Região Administrativa" : u.uf === "ZZ" ? "Cidade do exterior" : "Município";
  let html = `<div class="cabeca"><div><h2>${esc(u.nome)}</h2><p class="sub">${tipo} · ${nomeUF(u.uf)}</p></div>
    <button class="fechar" ${ir({ u: null })} aria-label="Fechar ficha">✕</button></div>`;

  html += `<h3>Presidente · 2º turno</h3>${tabelaPresidente(p2a, p2b, u.cd)}`;
  html += `<h3>Presidente · 1º turno</h3>${tabelaPresidente(p1a, p1b, u.cd)}`;
  const pAno = e.ano === 2022 ? [p1a, p2a] : [p1b, p2b];
  html += `<h3>Votos para Presidente · ${e.ano}</h3>
    <p class="sub">1º turno</p>${barrasPresidente(pAno[0], u.cd)}<p class="sub">2º turno</p>${barrasPresidente(pAno[1], u.cd)}`;

  // outros cargos: os mais votados na unidade (percentual sobre os válidos do cargo)
  html += `<div class="cabeca"><h3>Outros cargos · ${e.ano}</h3><div class="grupo" role="group" aria-label="Ano">
      ${[2022, 2026].map((a) => `<button ${ir({ ano: a })} aria-pressed="${a === e.ano}">${a}</button>`).join("")}</div></div>`;
  if (!dados) {
    html += `<p class="sub">No exterior só se vota para Presidente.</p>`;
  } else {
    const validos = new Map(dados.part.map((r) => [`${r[0]}-${r[1]}-${r[2]}`, r[3 + CAMPOS.indexOf("validos")]]));
    for (const cargo of [3, 5, 6, 7]) {
      for (const turno of [1, 2]) {
        const chave = `${cargo}-${e.ano}-${turno}`;
        const top = dados.top[chave];
        if (!top) continue;
        const total = validos.get(chave);
        html += `<p class="sub"><b>${nomeCargo(cargo)}</b>${turno === 2 ? " · 2º turno" : ""}${[6, 7].includes(cargo) ? " · 10 mais votados" : ""}</p>`;
        html += barras(
          top.map(([i, v]) => {
            const [nome, partido, nr, situacao] = sh.candidatos[i];
            return {
              rotulo: `${nome} (${partido})`,
              pct: pct(v, total),
              detalhe: `${fmtPct(pct(v, total))} · ${fmtInt(v)}`,
              cor: COR[partido],
              tag: tagSituacao(situacao),
              ir: { v: "r", cargo, ano: e.ano, turno, uf: u.uf, c: nr, m: "candidato", u: null },
            };
          }),
        );
      }
    }
    html += `<p class="sub">Clique num candidato para ver o mapa dos seus votos na UF.</p>`;
  }

  // participação: todas as eleições da unidade
  const linhas = dados
    ? dados.part.map((r) => ({ cargo: r[0], ano: r[1], turno: r[2], ...taxas(Object.fromEntries(CAMPOS.map((f, i) => [f, r[3 + i]]))) }))
    : [[1, 2022, 1, p1a], [1, 2026, 1, p1b], [1, 2022, 2, p2a], [1, 2026, 2, p2b]]
        .map(([cargo, ano, turno, c]) => ({ cargo, ano, turno, ...linha(c, c.idx.get(u.cd)) }))
        .filter((l) => l.aptos != null);
  linhas.sort((p, q) => p.cargo - q.cargo || p.turno - q.turno || p.ano - q.ano);
  html += `<h3>Participação</h3><div class="tabela"><table class="ficha"><thead><tr><th>Eleição</th><th>Aptos</th><th>Compar.</th><th>Abst.</th><th>Brancos</th><th>Nulos</th></tr></thead><tbody>
    ${linhas
      .map(
        (l) => `<tr><td>${nomeCargo(l.cargo)} ${l.turno}ºt ${l.ano}</td><td>${fmtInt(l.aptos)}</td><td>${fmtPct(l.pComp)}</td>
          <td>${fmtPct(l.pAbst)}</td><td>${fmtPct(l.pBr)}</td><td>${fmtPct(l.pNu)}</td></tr>`,
      )
      .join("")}</tbody></table></div>`;
  return html;
}
