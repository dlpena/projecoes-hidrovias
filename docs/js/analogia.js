/* Algoritmo de projeção por analogia — ESPELHO de pipeline/analogia.py.
 * Qualquer mudança de regra deve ser aplicada nos dois arquivos.
 * Funções puras: sem DOM, recebem o JSON da estação e parâmetros.
 * Datas em UTC (Date.UTC) para não depender do fuso do navegador. */
"use strict";

const Analogia = (() => {
  const TOLERANCIA_DIAS = 3;
  const COBERTURA_MINIMA = 0.8;
  const DIAS_FIM_JANELA = 10;
  const MIN_ANALOGOS = 3;
  const CICLO_MEIO_DIAS = 182;           // ciclo de 365 dias centrado em D
  const CICLO_COBERTURA_MINIMA = 0.7;
  const PERIODO_CICLO = 365;

  const OFFSETS_MES = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
  const IDX_29FEV = 59;
  const DIA_MS = 864e5;

  const indiceDia = (mes, dia) => OFFSETS_MES[mes - 1] + dia - 1;
  const bissexto = (ano) => ano % 4 === 0 && (ano % 100 !== 0 || ano % 400 === 0);

  const paraData = (iso) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d));
  };
  const paraISO = (dt) => dt.toISOString().slice(0, 10);
  const somaDias = (dt, k) => new Date(dt.getTime() + k * DIA_MS);

  /** Último dia do mês que fica `meses` meses após o mês de D (o mês de D não
   * conta). Sem `meses`, 31/dez do ano de D. Espelho de fim_horizonte(). */
  function fimHorizonte(ultimaData, meses) {
    const y = Number(ultimaData.slice(0, 4));
    const m = Number(ultimaData.slice(5, 7));
    if (meses === null || meses === undefined) return `${y}-12-31`;
    return paraISO(new Date(Date.UTC(y, m + meses, 0)));  // dia 0 = último do mês anterior
  }

  /** Mesmo dia/mês `desloc` anos adiante; null se 29/fev inexistente. */
  function dataAnaloga(dt, desloc) {
    const y = dt.getUTCFullYear() + desloc, m = dt.getUTCMonth() + 1, d = dt.getUTCDate();
    if (m === 2 && d === 29 && !bissexto(y)) return null;
    return [y, m, d];
  }

  function valor(anos, analoga) {
    if (analoga === null) return null;
    const serie = anos[String(analoga[0])];
    if (!serie) return null;
    const v = serie[indiceDia(analoga[1], analoga[2])];
    return v === null || v === undefined ? null : Number(v);
  }

  function cotaEmD(anos, d0, desloc) {
    for (let desvio = 0; desvio <= TOLERANCIA_DIAS; desvio++) {
      const deltas = desvio === 0 ? [0] : [-desvio, desvio];
      for (const delta of deltas) {
        const v = valor(anos, dataAnaloga(somaDias(d0, delta), desloc));
        if (v !== null) return [v, delta];
      }
    }
    return [null, null];
  }

  /** Dias (relativos a D) do mínimo e do máximo do análogo no ciclo centrado em D.
   * Empate -> o primeiro. Menos de 70% de dias com dado -> [null, null]. */
  function extremosCiclo(anos, d0, desloc) {
    const vals = [];
    for (let k = -CICLO_MEIO_DIAS; k <= CICLO_MEIO_DIAS; k++) {
      const v = valor(anos, dataAnaloga(somaDias(d0, k), desloc));
      if (v !== null) vals.push([k, v]);
    }
    if (vals.length < CICLO_COBERTURA_MINIMA * (2 * CICLO_MEIO_DIAS + 1)) return [null, null];
    let [kMin, vMin] = vals[0];
    let [kMax, vMax] = vals[0];
    for (let i = 1; i < vals.length; i++) {
      const [k, v] = vals[i];
      if (v < vMin) { kMin = k; vMin = v; }
      if (v > vMax) { kMax = k; vMax = v; }
    }
    return [kMin, kMax];
  }

  /** Média e desvio-padrão circulares (em dias) num ciclo de 365 dias. */
  function mediaCircular(dias) {
    const w = (2 * Math.PI) / PERIODO_CICLO;
    let s = 0.0, c = 0.0;
    for (const d of dias) {
      s += Math.sin(w * d);
      c += Math.cos(w * d);
    }
    s /= dias.length;
    c /= dias.length;
    const r = Math.min(Math.hypot(s, c), 1.0);
    const media = Math.atan2(s, c) / w;
    let desvio;
    if (r >= 1.0 - 1e-12) desvio = 0.0;           // ruído de arredondamento: análogos concordam
    else if (r > 1e-12) desvio = Math.sqrt(-2.0 * Math.log(r)) / w;
    else desvio = Infinity;
    return [media, desvio];
  }

  /* Comparação lexicográfica de chaves [a, b]: true se x > y. */
  const maiorChave = (x, y) => x[0] > y[0] || (x[0] === y[0] && x[1] > y[1]);
  /* max/min por chave; empate -> o primeiro (ano mais antigo), como max()/min() do Python. */
  function maxPor(lista, chave) {
    let m = lista[0];
    for (const c of lista) if (maiorChave(chave(c), chave(m))) m = c;
    return m;
  }
  function minPor(lista, chave) {
    let m = lista[0];
    for (const c of lista) if (maiorChave(chave(m), chave(c))) m = c;
    return m;
  }

  function interpolar(valores) {
    const n = valores.length;
    const out = valores.slice();
    const flags = new Array(n).fill(false);
    const comDado = [];
    for (let i = 0; i < n; i++) if (valores[i] !== null && valores[i] !== undefined) comDado.push(i);
    if (comDado.length < 2) return [out, flags];
    for (let k = 0; k + 1 < comDado.length; k++) {
      const a = comDado[k], b = comDado[k + 1];
      if (b - a > 1) {
        const va = Number(valores[a]), vb = Number(valores[b]);
        for (let i = a + 1; i < b; i++) {
          out[i] = va + ((vb - va) * (i - a)) / (b - a);
          flags[i] = true;
        }
      }
    }
    return [out, flags];
  }

  /** Menor range inteiro (cm, >= minimo) que seleciona pelo menos minAnalogos anos.
   * Espelho de analogia.range_inicial(). */
  function rangeInicial(doc, minAnalogos = MIN_ANALOGOS, minimo = 50.0, horizonteMeses = null) {
    const r = calcular(doc, Infinity, "cm", horizonteMeses);
    const dists = r.candidatos
      .filter((c) => c.selecionado)
      .map((c) => Math.abs(c.cota_em_d - r.cota_atual))
      .sort((a, b) => a - b);
    if (!dists.length) return minimo;
    const alvo = dists.length >= minAnalogos ? dists[minAnalogos - 1] : dists[dists.length - 1];
    return Math.max(minimo, Math.ceil(alvo));
  }

  /** Calcula a analogia. modo: "cm" ou "pct"; horizonteMeses: meses inteiros após o
   * mês de D (null = até 31/dez). Espelho de analogia.calcular(). */
  function calcular(doc, rangeValor = 10.0, modo = "cm", horizonteMeses = null) {
    const anos = doc.anos;
    const d0 = paraData(doc.ultima_data);
    const anoAtual = d0.getUTCFullYear();
    const idxD = indiceDia(d0.getUTCMonth() + 1, d0.getUTCDate());
    const cotaAtual = Number(anos[String(anoAtual)][idxD]);

    const fimISO = fimHorizonte(doc.ultima_data, horizonteMeses);
    const nDias = Math.round((paraData(fimISO) - d0) / DIA_MS) + 1;
    const datas = [];
    for (let k = 0; k < nDias; k++) datas.push(somaDias(d0, k));

    const limite = modo === "cm" ? rangeValor : (Math.abs(cotaAtual) * rangeValor) / 100.0;

    const candidatos = [];
    const janelas = new Map();
    for (const chave of Object.keys(anos).sort()) {
      const ano = parseInt(chave, 10);
      if (ano === anoAtual) continue;
      const desloc = ano - anoAtual;
      const cand = {
        ano, cota_em_d: null, dias_tolerancia: null, cobertura: null,
        min_pos_d: null, delta: null, max_pos_d: null, subida: null,
        dia_min_ciclo: null, dia_max_ciclo: null,
        selecionado: false, motivo: null,
      };
      const [cotaD, desvio] = cotaEmD(anos, d0, desloc);
      if (cotaD === null) {
        cand.motivo = "sem dado no dia D";
        candidatos.push(cand);
        continue;
      }
      cand.cota_em_d = cotaD;
      cand.dias_tolerancia = desvio;

      const analogas = datas.map((t) => dataAnaloga(t, desloc));
      const valores = analogas.map((a) => valor(anos, a));
      const pos = [];
      for (let k = 0; k < nDias; k++) if (analogas[k] !== null) pos.push(k);
      const comDado = pos.filter((k) => valores[k] !== null);
      cand.cobertura = pos.length ? comDado.length / pos.length : 0.0;
      if (comDado.length) {
        const minimo = Math.min(...comDado.map((k) => valores[k]));
        const maximo = Math.max(...comDado.map((k) => valores[k]));
        cand.min_pos_d = minimo;
        cand.delta = cotaD - minimo;
        cand.max_pos_d = maximo;
        cand.subida = maximo - cotaD;
      }

      if (Math.abs(cotaD - cotaAtual) > limite) {
        cand.motivo = "fora do intervalo";
        candidatos.push(cand);
        continue;
      }

      const fimJanela = comDado.filter((k) => k >= nDias - DIAS_FIM_JANELA);
      if (cand.cobertura < COBERTURA_MINIMA || fimJanela.length === 0) {
        cand.motivo = "série incompleta pós-D";
        candidatos.push(cand);
        continue;
      }

      cand.selecionado = true;
      [cand.dia_min_ciclo, cand.dia_max_ciclo] = extremosCiclo(anos, d0, desloc);
      candidatos.push(cand);
      janelas.set(ano, valores);
    }

    const selecionados = candidatos.filter((c) => c.selecionado);

    const resultado = {
      ano_atual: anoAtual,
      dia_d: doc.ultima_data,
      idx_d: idxD,
      cota_atual: cotaAtual,
      range_valor: rangeValor,
      modo,
      limite_cm: limite,
      horizonte_meses: horizonteMeses,
      fim_horizonte: fimISO,
      datas_proj: datas.map(paraISO),
      candidatos,
      selecionados: selecionados.map((c) => c.ano),
      regime: null,
      ciclo: null,
      ano_inferior: null,
      criterio_inferior: null,
      ano_superior: null,
      criterio_superior: null,
      trajetorias: null,
      aviso: null,
    };
    if (!selecionados.length) {
      resultado.aviso = "Nenhum ano análogo no intervalo — amplie o intervalo.";
      return resultado;
    }
    if (selecionados.length < MIN_ANALOGOS) {
      resultado.aviso = `Apenas ${selecionados.length} ano(s) análogo(s) — amplie o intervalo.`;
    }

    // regime pelo conjunto: data média do mínimo e do máximo dos ciclos
    const ciclos = selecionados.filter((c) => c.dia_min_ciclo !== null);
    let regime = "descida";
    if (ciclos.length) {
      const [mMin, dpMin] = mediaCircular(ciclos.map((c) => c.dia_min_ciclo));
      const [mMax, dpMax] = mediaCircular(ciclos.map((c) => c.dia_max_ciclo));
      const proximo = (m) => (m > 0 ? m : m + PERIODO_CICLO);
      regime = proximo(mMin) < proximo(mMax) ? "descida" : "subida";
      resultado.ciclo = {
        n: ciclos.length,
        media_min: mMin, desvio_min: dpMin,
        data_media_min: paraISO(somaDias(d0, Math.round(mMin))),
        media_max: mMax, desvio_max: dpMax,
        data_media_max: paraISO(somaDias(d0, Math.round(mMax))),
      };
    }

    const chaveQueda = (c) => [c.delta, -c.subida];
    const chaveSubida = (c) => [c.subida, -c.delta];
    let inferior, superior, critInf, critSup;
    if (regime === "descida") {
      inferior = maxPor(selecionados, chaveQueda); critInf = "maior_queda";
      superior = minPor(selecionados, chaveQueda); critSup = "menor_queda";
    } else {
      inferior = minPor(selecionados, chaveSubida); critInf = "menor_subida";
      superior = maxPor(selecionados, chaveSubida); critSup = "maior_subida";
    }
    resultado.regime = regime;
    resultado.ano_inferior = inferior.ano;
    resultado.criterio_inferior = critInf;
    resultado.ano_superior = superior.ano;
    resultado.criterio_superior = critSup;

    const porAno = new Map();
    for (const c of selecionados) {
      const offset = cotaAtual - c.cota_em_d;
      const bruta = janelas.get(c.ano).map((v) => (v === null ? null : v + offset));
      porAno.set(c.ano, interpolar(bruta));
    }

    const media = new Array(nDias).fill(null);
    for (let k = 0; k < nDias; k++) {
      const vals = [];
      for (const [cheia] of porAno.values()) {
        if (cheia[k] !== null) vals.push(cheia[k]);
      }
      if (vals.length) media[k] = vals.reduce((s, v) => s + v, 0) / vals.length;
    }

    const todas = {};
    for (const [a, [cheia]] of porAno.entries()) todas[String(a)] = cheia;

    resultado.trajetorias = {
      inferior: porAno.get(inferior.ano)[0],
      inferior_interp: porAno.get(inferior.ano)[1],
      superior: porAno.get(superior.ano)[0],
      superior_interp: porAno.get(superior.ano)[1],
      media,
      todas,
    };
    return resultado;
  }

  return { calcular, rangeInicial, fimHorizonte, indiceDia, bissexto, IDX_29FEV, MIN_ANALOGOS };
})();

/* Para testes de paridade com Node (ignora no navegador). */
if (typeof module !== "undefined" && module.exports) module.exports = Analogia;
