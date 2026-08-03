/* Algoritmo de projeção por analogia — ESPELHO de pipeline/analogia.py.
 * Qualquer mudança de regra deve ser aplicada nos dois arquivos.
 * Funções puras: sem DOM, recebem o JSON da estação e parâmetros. */
"use strict";

const Analogia = (() => {
  const TOLERANCIA_DIAS = 3;
  const COBERTURA_MINIMA = 0.8;
  const DIAS_FIM_ANO = 10;
  const MIN_ANALOGOS = 3;

  const OFFSETS_MES = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
  const IDX_29FEV = 59;

  const indiceDia = (mes, dia) => OFFSETS_MES[mes - 1] + dia - 1;
  const bissexto = (ano) => ano % 4 === 0 && (ano % 100 !== 0 || ano % 400 === 0);

  function posicoesValidas(ano, ini, fim = 366) {
    const pos = [];
    for (let i = ini; i < fim; i++) {
      if (i !== IDX_29FEV || bissexto(ano)) pos.push(i);
    }
    return pos;
  }

  function cotaEmD(serie, idxD, ano) {
    for (let desvio = 0; desvio <= TOLERANCIA_DIAS; desvio++) {
      const deltas = desvio === 0 ? [0] : [-desvio, desvio];
      for (const delta of deltas) {
        const i = idxD + delta;
        if (i >= 0 && i < 366 && (i !== IDX_29FEV || bissexto(ano))) {
          const v = serie[i];
          if (v !== null && v !== undefined) return [Number(v), delta];
        }
      }
    }
    return [null, null];
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
  function rangeInicial(doc, minAnalogos = MIN_ANALOGOS, minimo = 10.0) {
    const r = calcular(doc, Infinity, "cm");
    const dists = r.candidatos
      .filter((c) => c.selecionado)
      .map((c) => Math.abs(c.cota_em_d - r.cota_atual))
      .sort((a, b) => a - b);
    if (!dists.length) return minimo;
    const alvo = dists.length >= minAnalogos ? dists[minAnalogos - 1] : dists[dists.length - 1];
    return Math.max(minimo, Math.ceil(alvo));
  }

  /** Calcula a analogia. modo: "cm" ou "pct". Espelho de analogia.calcular(). */
  function calcular(doc, rangeValor = 10.0, modo = "cm") {
    const anos = doc.anos;
    const anoAtual = parseInt(doc.ultima_data.slice(0, 4), 10);
    const mesD = parseInt(doc.ultima_data.slice(5, 7), 10);
    const diaD = parseInt(doc.ultima_data.slice(8, 10), 10);
    const idxD = indiceDia(mesD, diaD);
    const cotaAtual = Number(anos[String(anoAtual)][idxD]);

    const limite = modo === "cm" ? rangeValor : (Math.abs(cotaAtual) * rangeValor) / 100.0;

    const candidatos = [];
    for (const chave of Object.keys(anos).sort()) {
      const ano = parseInt(chave, 10);
      if (ano === anoAtual) continue;
      const serie = anos[chave];
      const cand = {
        ano, cota_em_d: null, dias_tolerancia: null, cobertura: null,
        min_pos_d: null, delta: null, selecionado: false, motivo: null,
      };
      const [cotaD, desvio] = cotaEmD(serie, idxD, ano);
      if (cotaD === null) {
        cand.motivo = "sem dado no dia D";
        candidatos.push(cand);
        continue;
      }
      cand.cota_em_d = cotaD;
      cand.dias_tolerancia = desvio;

      const pos = posicoesValidas(ano, idxD);
      const comDado = pos.filter((i) => serie[i] !== null && serie[i] !== undefined);
      cand.cobertura = pos.length ? comDado.length / pos.length : 0.0;
      if (comDado.length) {
        const minimo = Math.min(...comDado.map((i) => Number(serie[i])));
        cand.min_pos_d = minimo;
        cand.delta = cotaD - minimo;
      }

      if (Math.abs(cotaD - cotaAtual) > limite) {
        cand.motivo = "fora do range";
        candidatos.push(cand);
        continue;
      }

      const fimAno = comDado.filter((i) => i >= 366 - DIAS_FIM_ANO);
      if (cand.cobertura < COBERTURA_MINIMA || fimAno.length === 0) {
        cand.motivo = "série incompleta pós-D";
        candidatos.push(cand);
        continue;
      }

      cand.selecionado = true;
      candidatos.push(cand);
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
      candidatos,
      selecionados: selecionados.map((c) => c.ano),
      ano_maior_queda: null,
      ano_menor_queda: null,
      trajetorias: null,
      aviso: null,
    };
    if (!selecionados.length) {
      resultado.aviso = "Nenhum ano análogo no range — amplie o range.";
      return resultado;
    }
    if (selecionados.length < MIN_ANALOGOS) {
      resultado.aviso = `Apenas ${selecionados.length} ano(s) análogo(s) — amplie o range.`;
    }

    let maior = selecionados[0], menor = selecionados[0];
    for (const c of selecionados) {
      if (c.delta > maior.delta) maior = c;
      if (c.delta < menor.delta) menor = c;
    }
    resultado.ano_maior_queda = maior.ano;
    resultado.ano_menor_queda = menor.ano;

    const porAno = new Map();
    for (const c of selecionados) {
      const serie = anos[String(c.ano)];
      const offset = cotaAtual - c.cota_em_d;
      const bruta = new Array(366).fill(null);
      for (let i = idxD; i < 366; i++) {
        if (serie[i] !== null && serie[i] !== undefined) bruta[i] = Number(serie[i]) + offset;
      }
      porAno.set(c.ano, interpolar(bruta));
    }

    const media = new Array(366).fill(null);
    for (let i = idxD; i < 366; i++) {
      const vals = [];
      for (const [cheia] of porAno.values()) {
        if (cheia[i] !== null) vals.push(cheia[i]);
      }
      if (vals.length) media[i] = vals.reduce((s, v) => s + v, 0) / vals.length;
    }

    const todas = {};
    for (const [a, [cheia]] of porAno.entries()) todas[String(a)] = cheia;

    resultado.trajetorias = {
      maior_queda: porAno.get(maior.ano)[0],
      maior_queda_interp: porAno.get(maior.ano)[1],
      menor_queda: porAno.get(menor.ano)[0],
      menor_queda_interp: porAno.get(menor.ano)[1],
      media,
      todas,
    };
    return resultado;
  }

  return { calcular, rangeInicial, indiceDia, bissexto, IDX_29FEV, MIN_ANALOGOS };
})();

/* Para testes de paridade com Node (ignora no navegador). */
if (typeof module !== "undefined" && module.exports) module.exports = Analogia;
