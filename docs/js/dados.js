/* Carrega e mescla os dois arquivos por estação (histórico + ano corrente)
 * num único objeto `doc`, no mesmo formato que grafico.js/analogia.js sempre
 * esperaram. Ver pipeline/exportar_json.py para o porquê da divisão. */
"use strict";

const Dados = (() => {
  async function buscarJSON(caminho) {
    const r = await fetch(caminho, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${caminho}: HTTP ${r.status}`);
    return r.json();
  }

  /** Mescla histórico + atual num único doc (anos, fonte_por_ano, cobertura_fontes). */
  function mesclar(historico, atual) {
    return {
      slug: atual.slug,
      nome: atual.nome,
      rio: atual.rio,
      codigo_hidroweb: atual.codigo_hidroweb,
      estcodigo_telemetria: atual.estcodigo_telemetria,
      variavel: atual.variavel,
      grandeza: atual.grandeza,
      unidade: atual.unidade,
      gerado_em: atual.gerado_em,
      ultima_data: atual.ultima_data,
      ultimo_valor: atual.ultimo_valor,
      fonte_ultimo_dado: atual.fonte_ultimo_dado,
      sintetica: atual.sintetica || null,
      fonte_por_ano: { ...historico.fonte_por_ano, ...atual.fonte_por_ano },
      cobertura_fontes: mesclarCobertura(historico.cobertura_fontes, atual.cobertura_fontes),
      anos: { ...historico.anos, ...atual.anos },
    };
  }

  function mesclarCobertura(a, b) {
    const fontes = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
    const out = {};
    for (const f of fontes) out[f] = { ...(a || {})[f], ...(b || {})[f] };
    return out;
  }

  /** Busca e mescla os dois arquivos de uma estação. */
  async function carregarEstacao(slug, base = "dados/") {
    const [historico, atual] = await Promise.all([
      buscarJSON(`${base}${slug}_historico.json`),
      buscarJSON(`${base}${slug}_atual.json`),
    ]);
    return mesclar(historico, atual);
  }

  async function carregarIndice(base = "dados/") {
    return buscarJSON(`${base}indice.json`);
  }

  return { carregarEstacao, carregarIndice };
})();
