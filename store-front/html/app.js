// FIAP Store - front. Toda chamada vai para /api, que o Ingress encaminha para a store-api.
const AMOSTRAS = 12;  // chamadas ao /api/plataforma para descobrir replicas e zonas

const $ = (id) => document.getElementById(id);
const brl = (v) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString("pt-BR") : "-");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function avisar(msg) {
  const el = $("aviso");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => (el.hidden = true), 4000);
}

async function api(caminho, opcoes) {
  const resp = await fetch(caminho, { cache: "no-store", ...opcoes });
  if (!resp.ok) {
    let detalhe = "";
    try { detalhe = (await resp.json()).detail || ""; } catch (_) {}
    throw new Error(`${caminho}: HTTP ${resp.status} ${detalhe}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------- painel da plataforma

function itemHtml(v) {
  return `<li class="${esc(v.status)}">
    <div class="cab"><span>${esc(v.titulo)}</span><span class="cap">cap. ${esc(v.capitulo)}</span></div>
    <div class="det">${esc(v.detalhe)}</div></li>`;
}

async function carregarPlataforma() {
  const btn = $("btn-recheck");
  btn.disabled = true;
  const pods = new Map();     // pod -> {zona, versao}
  let ultimo = null;
  for (let i = 0; i < AMOSTRAS; i++) {
    try {
      const d = await api("/api/plataforma");
      pods.set(d.pod, { zona: d.zona, versao: d.versao });
      ultimo = d;
    } catch (e) { /* um pod pode estar reiniciando; segue amostrando */ }
  }
  btn.disabled = false;

  if (!ultimo) {
    $("versao").textContent = "API indisponível";
    $("verificacoes").innerHTML = itemHtml({ status: "falha", titulo: "API inacessível", capitulo: "5 - Ingress",
      detalhe: "nenhuma resposta de /api/plataforma: confira o Ingress e o Service store-api" });
    $("resumo-replicas").innerHTML = "";
    return;
  }

  // versoes vistas: durante um rolling update aparecem duas
  const versoes = {};
  pods.forEach((p) => (versoes[p.versao] = (versoes[p.versao] || 0) + 1));
  const listaVersoes = Object.keys(versoes);
  const badge = $("versao");
  badge.className = "versao " + (listaVersoes.length === 1 ? (listaVersoes[0].startsWith("2") ? "v2" : "v1") : "");
  badge.textContent = listaVersoes.length === 1
    ? `API v${listaVersoes[0]}`
    : "Rollout em andamento: " + listaVersoes.map((v) => `v${v} (${versoes[v]})`).join(" + ");

  const zonas = new Set([...pods.values()].map((p) => p.zona).filter(Boolean));
  const https = location.protocol === "https:";
  const extras = [
    { status: pods.size >= 3 ? "ok" : "falha", titulo: "Réplicas da store-api atendendo", capitulo: "4 - Réplicas",
      detalhe: `${pods.size} pod(s) distintos em ${AMOSTRAS} chamadas: ${[...pods.keys()].join(", ")}` },
    { status: zonas.size >= 2 ? "ok" : (zonas.size === 1 ? "falha" : "aviso"), titulo: "Réplicas em zonas diferentes",
      capitulo: "4 / 6 - Alta disponibilidade",
      detalhe: zonas.size ? `zonas: ${[...zonas].join(", ")}` : "zona desconhecida (ver item de RBAC)" },
    { status: https ? "ok" : "falha", titulo: "Acesso por HTTPS", capitulo: "5 - Ingress TLS",
      detalhe: https ? "página servida com TLS" : "página servida em HTTP puro" },
  ];

  $("resumo-replicas").innerHTML = [
    ["Pods vistos", pods.size], ["Zonas", zonas.size || "?"], ["Ambiente", ultimo.ambiente],
    ["Namespace", ultimo.namespace || "?"],
  ].map(([k, v]) => `<div class="chip">${esc(k)}<b>${esc(v)}</b></div>`).join("");

  const todas = [...extras, ...ultimo.verificacoes];
  const ordem = { falha: 0, aviso: 1, ok: 2 };
  todas.sort((a, b) => ordem[a.status] - ordem[b.status]);
  $("verificacoes").innerHTML = todas.map(itemHtml).join("");
}

// ---------------------------------------------------------------- loja

async function carregarProdutos() {
  try {
    const produtos = await api("/api/produtos");
    $("produtos").innerHTML = produtos.map((p) => `
      <div class="produto">
        <span>${esc(p.nome)}</span>
        <span class="preco">${brl(p.preco)}</span>
        <button data-id="${p.id}">Comprar</button>
      </div>`).join("") || '<p class="nota">Catálogo vazio: o Job db-migrate rodou?</p>';
  } catch (e) {
    $("produtos").innerHTML = `<p class="nota">Não foi possível carregar o catálogo (${esc(e.message)}).</p>`;
  }
}

async function carregarPedidos() {
  try {
    const { resumo, pedidos } = await api("/api/pedidos?limite=15");
    $("resumo-pedidos").textContent = `${resumo.pendentes} pendentes · ${resumo.processados} processados`;
    $("pedidos").innerHTML = pedidos.map((p) => `<tr>
      <td>${p.id}</td><td>${esc(p.produto)}</td><td>${p.quantidade}</td><td>${brl(p.valor)}</td>
      <td class="st-${esc(p.status)}">${esc(p.status)}</td><td>${esc(p.criado_por)}</td>
      <td>${esc(p.processado_por || "-")}</td></tr>`).join("");
  } catch (e) { /* silencioso: o painel ja mostra o problema */ }
}

async function carregarRelatorios() {
  try {
    const rels = await api("/api/relatorios?limite=5");
    $("relatorios").innerHTML = rels.map((r) => `<tr>
      <td>${new Date(r.gerado_em).toLocaleString("pt-BR")}</td><td>${esc(r.gerado_por)}</td>
      <td>${r.total_pedidos}</td><td>${r.processados}</td><td>${r.pendentes}</td><td>${brl(r.valor_total)}</td>
      </tr>`).join("") || '<tr><td colspan="6" class="nota">Nenhum relatório ainda.</td></tr>';
  } catch (e) { /* idem */ }
}

$("produtos").addEventListener("click", async (ev) => {
  const id = ev.target.dataset && ev.target.dataset.id;
  if (!id) return;
  try {
    const r = await api("/api/pedidos", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ produto_id: Number(id), quantidade: 1 }) });
    avisar(`Pedido #${r.id} criado`);
    carregarPedidos();
  } catch (e) { avisar(e.message); }
});

$("btn-lote").addEventListener("click", async () => {
  const btn = $("btn-lote");
  btn.disabled = true;
  try {
    const r = await api("/api/pedidos/lote?quantidade=50", { method: "POST" });
    avisar(`${r.criados} pedidos criados (#${r.primeiro} a #${r.ultimo})`);
    carregarPedidos();
  } catch (e) { avisar(e.message); }
  btn.disabled = false;
});

$("btn-recheck").addEventListener("click", carregarPlataforma);

carregarPlataforma();
carregarProdutos();
carregarPedidos();
carregarRelatorios();
setInterval(carregarPedidos, 3000);
setInterval(carregarRelatorios, 15000);
setInterval(carregarPlataforma, 20000);
