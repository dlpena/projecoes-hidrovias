/* Montagem dos gráficos Plotly, controles de range e export CSV. */
"use strict";

const Grafico = (() => {
  const REGISTRO = new Map(); // slug -> {doc, grafico, resultado atual} p/ o PDF do conjunto
  const CORES = {
    observado: "#1a1a1a",
    maiorQueda: "#D55E00",
    menorQueda: "#0072B2",
    media: "#009E73",
    anoAnalogo: "#b5b5b5",
    anoComum: "#e4e4e4",
    diaD: "#888",
    pontoControle1: "#C0392B",
    pontoControle2: "#E0A526",
  };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"];

  /** datas[i] = "YYYY-MM-DD" do índice i no ano dado (null p/ 29/fev inexistente). */
  function datasDoAno(ano) {
    const datas = new Array(366).fill(null);
    for (let m = 1; m <= 12; m++) {
      const nDias = new Date(ano, m, 0).getDate();
      for (let d = 1; d <= nDias; d++) {
        datas[Analogia.indiceDia(m, d)] =
          `${ano}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      }
    }
    return datas;
  }

  function traceAno(serie, datas, nome, cor, largura, visivelHover) {
    const x = [], y = [];
    for (let i = 0; i < 366; i++) {
      if (datas[i] !== null) {
        x.push(datas[i]);
        y.push(serie[i] === undefined ? null : serie[i]);
      }
    }
    return {
      x, y, name: nome, mode: "lines",
      line: { color: cor, width: largura },
      hoverinfo: visivelHover ? undefined : "skip",
      hovertemplate: visivelHover ? `${nome}: %{y:.0f} cm<extra></extra>` : undefined,
      showlegend: false, connectgaps: false,
    };
  }

  function formatarDataBR(iso) {
    return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
  }

  function numeroBR(v, casas = 1) {
    return v === null || v === undefined ? "" : v.toFixed(casas).replace(".", ",");
  }

  /** Mínimo (valor, data) de uma trajetória a partir do dia D. */
  function minimoTrajetoria(serie, datas, idxD) {
    let min = null, dataMin = null;
    for (let i = idxD; i < 366; i++) {
      if (datas[i] !== null && serie[i] !== null && serie[i] !== undefined) {
        if (min === null || serie[i] < min) { min = serie[i]; dataMin = datas[i]; }
      }
    }
    return { min, dataMin };
  }

  /**
   * Toques da trajetória na cota `alvo` a partir do dia D (data interpolada linearmente
   * entre os dois dias vizinhos do cruzamento). `entrada` = primeiro cruzamento em queda,
   * `saida` = primeiro cruzamento em subida depois da entrada — se a trajetória já começa
   * abaixo do alvo, só há saída. null quando o toque não ocorre até 31/dez.
   */
  function cruzamentosTrajetoria(serie, datas, idxD, alvo) {
    const toques = [];
    let anterior = null; // { data, valor }
    for (let i = idxD; i < 366; i++) {
      if (datas[i] === null || serie[i] === null || serie[i] === undefined) continue;
      const valor = serie[i];
      if (anterior !== null && valor !== anterior.valor) {
        const a = anterior.valor - alvo, b = valor - alvo;
        if (a === 0 && (!toques.length || toques[toques.length - 1].data !== anterior.data)) {
          toques.push({ data: anterior.data, sentido: b < 0 ? "entrada" : "saida" });
        } else if ((a > 0 && b <= 0) || (a < 0 && b >= 0)) {
          const frac = a / (a - b);
          const t0 = new Date(`${anterior.data}T00:00:00`).getTime();
          const t1 = new Date(`${datas[i]}T00:00:00`).getTime();
          toques.push({
            data: new Date(t0 + frac * (t1 - t0)).toISOString().slice(0, 10),
            sentido: a > 0 ? "entrada" : "saida",
          });
        }
      }
      anterior = { data: datas[i], valor };
    }
    const iEntrada = toques.findIndex((t) => t.sentido === "entrada");
    const entrada = iEntrada >= 0 ? toques[iEntrada] : null;
    const saida = toques.slice(iEntrada + 1).find((t) => t.sentido === "saida") || null;
    return { entrada, saida };
  }

  function marcador(x, y, texto, cor, posicao) {
    return {
      x: [x], y: [y], mode: "markers+text", text: [texto],
      textposition: posicao, cliponaxis: false,
      marker: { color: cor, size: 8 },
      textfont: { size: 11, color: cor, family: "Segoe UI, system-ui, sans-serif" },
      hoverinfo: "skip", showlegend: false,
    };
  }

  /** Marcador sem texto embutido — o rótulo vira annotation posicionada em pixels (ver posicionarRotulos). */
  function marcadorSemTexto(x, y, cor, simbolo = "circle") {
    return {
      x: [x], y: [y], mode: "markers", cliponaxis: false,
      marker: { color: cor, size: 8, symbol: simbolo },
      hoverinfo: "skip", showlegend: false,
    };
  }

  /**
   * Annotation de rótulo posicionada em pixels a partir do deslocamento calculado por
   * posicionarRotulos. `chip` desenha um fundo branco semi-opaco atrás do texto — essencial
   * quando o rótulo pode cair sobre o feixe de curvas cinzas dos anos análogos.
   */
  function rotuloPonto(x, y, texto, cor, deslocamento, chip = false) {
    return {
      x, y, xref: "x", yref: "y", text: texto,
      xanchor: "center", yanchor: "middle",
      font: { size: 11, color: cor, family: "Segoe UI, system-ui, sans-serif" },
      ...(chip ? { bgcolor: "rgba(255,255,255,0.92)", borderpad: 1 } : {}),
      ...(deslocamento.comSeta
        ? { showarrow: true, ax: deslocamento.ax, ay: deslocamento.ay, axref: "pixel", ayref: "pixel",
            arrowhead: 0, arrowwidth: 1, arrowcolor: cor, standoff: 3 }
        : { showarrow: false, xshift: deslocamento.xshift, yshift: deslocamento.yshift }),
    };
  }

  /** Rótulo da queda para a legenda: " · queda 191 cm" (ou "subida" se negativa). */
  function rotuloQueda(r, ano) {
    const c = r.candidatos.find((c) => c.ano === ano);
    if (!c || c.delta === null) return "";
    return c.delta >= 0
      ? ` · queda ${Math.round(c.delta)} cm`
      : ` · subida ${Math.round(-c.delta)} cm`;
  }

  /** Amplitude vertical dos dados plotados (para calibrar a anticolisão). */
  function faixaY(doc, r) {
    let min = Infinity, max = -Infinity;
    const varre = (serie) => {
      for (let i = 0; i < 366; i++) {
        const v = serie[i];
        if (v !== null && v !== undefined) {
          if (v < min) min = v;
          if (v > max) max = v;
        }
      }
    };
    varre(doc.anos[String(r.ano_atual)]);
    if (r.trajetorias) {
      Object.values(r.trajetorias.todas).forEach(varre);
      varre(r.trajetorias.maior_queda);
      varre(r.trajetorias.menor_queda);
    }
    return max > min ? max - min : 1;
  }

  // Rótulo isolado (sem colisão): só desloca em pixels (yshift: +acima/-abaixo), sem
  // linha-guia — não precisa, é óbvio a quem pertence.
  const DESLOCAMENTO_PADRAO = { comSeta: false, xshift: 0, yshift: -14 };

  /**
   * Deslocamento do k-ésimo rótulo (0 = ponto mais alto) de um cluster de `total` pontos que
   * colidiriam entre si. Os extremos vão na vertical AFASTANDO-SE um do outro (o mais alto
   * sobe, o mais baixo desce), sem linha-guia. Os do meio vão na diagonal E ganham uma
   * linha-guia curta até o marcador (ax/ay, convenção do Plotly: ay negativo = acima) — só o
   * deslocamento não bastava: "de lado" cai em cima da linha pontilhada, e longe demais sem
   * guia parece "solto" do ponto.
   */
  function deslocamentoDoCluster(k, total) {
    if (k === 0) return { comSeta: false, xshift: 0, yshift: 18 };           // mais alto: acima
    if (k === total - 1) return { comSeta: false, xshift: 0, yshift: -18 };  // mais baixo: abaixo
    return { comSeta: true, ax: k % 2 === 1 ? 24 : -24, ay: -14 };           // meio: diagonal + guia
  }

  /**
   * Agrupa mínimos que colidiriam visualmente (próximos em data e em valor) e devolve,
   * por índice, o deslocamento em pixels do rótulo — garantindo separação mesmo quando os
   * mínimos praticamente coincidem em x/y (ex.: maior/menor queda e média a poucos cm/m³ e
   * poucos dias um do outro).
   */
  function posicionarRotulos(minimos, amplitudeY) {
    const limY = amplitudeY * 0.07;
    const n = minimos.length;
    const adjacentes = Array.from({ length: n }, () => []);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dDias = Math.abs(new Date(minimos[i].x) - new Date(minimos[j].x)) / 864e5;
        if (dDias < 20 && Math.abs(minimos[i].y - minimos[j].y) < limY) {
          adjacentes[i].push(j);
          adjacentes[j].push(i);
        }
      }
    }
    const deslocamentos = minimos.map(() => DESLOCAMENTO_PADRAO);
    const visitado = new Array(n).fill(false);
    for (let i = 0; i < n; i++) {
      if (visitado[i]) continue;
      const cluster = [i];
      visitado[i] = true;
      for (let k = 0; k < cluster.length; k++) {
        for (const viz of adjacentes[cluster[k]]) {
          if (!visitado[viz]) { visitado[viz] = true; cluster.push(viz); }
        }
      }
      if (cluster.length > 1) {
        cluster.sort((a, b) => minimos[b].y - minimos[a].y); // mais alto primeiro
        cluster.forEach((idx, k) => {
          deslocamentos[idx] = deslocamentoDoCluster(k, cluster.length);
        });
      }
    }
    return deslocamentos;
  }

  /**
   * Marcadores + rótulos "dd/mm" de onde as 3 projeções tocam os pontos de controle (a cota
   * do toque é a do próprio PC, então só a data interessa).
   * Triângulo p/ baixo = toque de entrada (curva caindo), p/ cima = toque de saída (subindo).
   * O rótulo desloca-se na VERTICAL a partir do toque, com linha-guia reta, e o lado é dado
   * pela curva: maior queda ABAIXO (é a curva mais baixa — embaixo dela há menos traçado),
   * menor queda ACIMA (curva mais alta), média no primeiro lado livre. As curvas de lado fixo
   * são posicionadas antes para a média se encaixar por último.
   */
  function tracesCruzamentosControle(r, datas, pontos, amplitudeY, larguraGrafico) {
    const traces = [];
    const anotacoes = [];
    const tj = r.trajetorias;
    const curvas = [
      [tj.maior_queda, CORES.maiorQueda, "maior"],
      [tj.menor_queda, CORES.menorQueda, "menor"],
      [tj.media, CORES.media, "media"],
    ];
    const toques = [];
    for (const alvo of [pontos.pc1, pontos.pc2]) {
      if (alvo === null || alvo === undefined || !isFinite(alvo)) continue;
      for (const [serie, cor, curva] of curvas) {
        const { entrada, saida } = cruzamentosTrajetoria(serie, datas, r.idx_d, alvo);
        if (entrada) toques.push({ x: entrada.data, y: alvo, cor, curva, sentido: "entrada" });
        if (saida) toques.push({ x: saida.data, y: alvo, cor, curva, sentido: "saida" });
      }
    }
    // média por último; dentro de cada grupo, por data (estabiliza a anticolisão)
    toques.sort((a, b) =>
      (a.curva === "media") - (b.curva === "media") || new Date(a.x) - new Date(b.x));
    // Anticolisão em pixels estimados nos dois eixos: px/dia sai da largura do plot (margens
    // l=58 e r=70 descontadas) e px/cm da altura útil (~396px) sobre a amplitude com a folga
    // do autorange (~6% por lado). Cada rótulo (~36x17px com o chip) pega o menor nível livre
    // no seu lado, afastando-se da linha 19px por nível (+1 = abaixo na tela, -1 = acima).
    const pxDia = Math.max(1.5, ((larguraGrafico || 1100) - 128) / 366);
    const pxCm = 396 / (amplitudeY * 1.12);
    const diaAno = (iso) =>
      (new Date(`${iso}T00:00:00`) - new Date(`${r.ano_atual}-01-01T00:00:00`)) / 864e5;
    const cx = toques.map((p) => diaAno(p.x) * pxDia);
    const LADO_FIXO = { maior: 1, menor: -1 };
    const pos = toques.map(() => null); // { dir, nivel } depois de posicionado
    const sRotulo = (y, dir, n) => -y * pxCm + dir * (20 + n * 19);
    const livre = (i, dir, n) => {
      for (let j = 0; j < toques.length; j++) {
        if (j === i || pos[j] === null) continue;
        if (Math.abs(cx[i] - cx[j]) < 46 &&
            Math.abs(sRotulo(toques[i].y, dir, n) -
                     sRotulo(toques[j].y, pos[j].dir, pos[j].nivel)) < 18) return false;
      }
      return true;
    };
    toques.forEach((p, i) => {
      const lados = p.curva === "media" ? [-1, 1] : [LADO_FIXO[p.curva]];
      busca: for (let n = 0; ; n++) {
        for (const dir of lados) {
          if (livre(i, dir, n)) { pos[i] = { dir, nivel: n }; break busca; }
        }
      }
    });
    toques.forEach((p, i) => {
      traces.push(marcadorSemTexto(p.x, p.y, p.cor,
                                   p.sentido === "entrada" ? "triangle-down" : "triangle-up"));
      anotacoes.push(rotuloPonto(
        p.x, p.y, formatarDataBR(p.x).slice(0, 5), p.cor,
        { comSeta: true, ax: 0, ay: pos[i].dir * (20 + pos[i].nivel * 19) }, true));
    });
    return { traces, anotacoes };
  }

  function montarTraces(doc, r, pontos, larguraGrafico) {
    const datas = datasDoAno(r.ano_atual);
    const traces = [];
    const anotacoesRotulos = [];

    // trajetórias deslocadas dos anos análogos, apenas após o dia D (fundo)
    if (r.trajetorias) {
      for (const [ano, serie] of Object.entries(r.trajetorias.todas)) {
        const t = traceAno(serie, datas, ano, CORES.anoAnalogo, 1, true);
        t.hovertemplate = `${ano} (análogo): %{y:.0f} cm<extra></extra>`;
        traces.push(t);
      }
      const tj = r.trajetorias;
      const proj = [
        [tj.maior_queda,
         `Maior queda (${r.ano_maior_queda}${rotuloQueda(r, r.ano_maior_queda)})`,
         CORES.maiorQueda, "solid"],
        [tj.menor_queda,
         `Menor queda (${r.ano_menor_queda}${rotuloQueda(r, r.ano_menor_queda)})`,
         CORES.menorQueda, "solid"],
        [tj.media, `Média (${r.selecionados.length} anos)`, CORES.media, "dot"],
      ];
      for (const [serie, nome, cor, traco] of proj) {
        const t = traceAno(serie, datas, nome, cor, 2, true);
        t.line.dash = traco;
        t.showlegend = true;
        traces.push(t);
      }
    }

    const tObs = traceAno(doc.anos[String(r.ano_atual)], datas,
                          `Observado ${r.ano_atual}`, CORES.observado, 2.5, true);
    tObs.showlegend = true;
    traces.push(tObs);

    // marcadores com valores: último dado e mínimos das 3 projeções
    traces.push(marcador(r.dia_d, r.cota_atual, String(Math.round(r.cota_atual)),
                         CORES.observado, "top center"));
    if (r.trajetorias) {
      const tj = r.trajetorias;
      const amplitudeY = faixaY(doc, r);
      const minimos = [];
      for (const [serie, cor] of [
        [tj.maior_queda, CORES.maiorQueda],
        [tj.menor_queda, CORES.menorQueda],
        [tj.media, CORES.media],
      ]) {
        const { min, dataMin } = minimoTrajetoria(serie, datas, r.idx_d);
        if (min !== null) minimos.push({ x: dataMin, y: min, cor });
      }
      const deslocamentos = posicionarRotulos(minimos, amplitudeY);
      minimos.forEach((m, i) => {
        traces.push(marcadorSemTexto(m.x, m.y, m.cor));
        anotacoesRotulos.push(rotuloPonto(m.x, m.y, String(Math.round(m.y)), m.cor, deslocamentos[i]));
      });

      const { traces: tracesCruz, anotacoes: anotacoesCruz } =
        tracesCruzamentosControle(r, datas, pontos || {}, amplitudeY, larguraGrafico);
      traces.push(...tracesCruz);
      anotacoesRotulos.push(...anotacoesCruz);
    }
    return { traces, datas, anotacoesRotulos };
  }

  /** Linhas horizontais e rótulos dos pontos de controle (cotas de referência definidas pelo usuário). */
  function shapesPontosControle(pontos) {
    const shapes = [];
    const anotacoes = [];
    const defs = [
      { valor: pontos.pc1, cor: CORES.pontoControle1 },
      { valor: pontos.pc2, cor: CORES.pontoControle2 },
    ];
    for (const d of defs) {
      if (d.valor === null || d.valor === undefined || !isFinite(d.valor)) continue;
      shapes.push({
        type: "line", xref: "paper", yref: "y",
        x0: 0, x1: 1, y0: d.valor, y1: d.valor,
        line: { color: d.cor, width: 1.5 },
      });
      anotacoes.push({
        x: 1, xref: "paper", y: d.valor, yref: "y",
        text: `${Math.round(d.valor)} cm`, showarrow: false,
        xanchor: "left", yanchor: "middle", xshift: 8,
        font: { size: 11, color: d.cor, family: "Segoe UI, system-ui, sans-serif" },
      });
    }
    return { shapes, anotacoes };
  }

  function layoutBase(doc, r, pontos) {
    const { shapes: shapesPC, anotacoes: anotacoesPC } = shapesPontosControle(pontos || {});
    return {
      margin: { l: 58, r: shapesPC.length ? 70 : 16, t: 8, b: 34 },
      separators: ",.",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Segoe UI, system-ui, sans-serif", size: 12, color: "#555" },
      dragmode: false,   // sem zoom/pan por clique-e-arraste
      xaxis: {
        fixedrange: true,
        tickvals: MESES.map((_, m) => `${r.ano_atual}-${String(m + 1).padStart(2, "0")}-01`),
        ticktext: MESES,
        hoverformat: "%d/%m",
        gridcolor: "#efefec",
        range: [`${r.ano_atual}-01-01`, `${r.ano_atual}-12-31`],
      },
      yaxis: {
        fixedrange: true,
        title: { text: "Cota (cm)", font: { size: 12 } },
        tickformat: ",d",   // valor inteiro com separador de milhar (sem "k")
        nticks: 14,         // passo menor entre os ticks
        gridcolor: "#efefec",
        zeroline: false,
      },
      legend: {
        orientation: "h", y: 1.02, yanchor: "bottom", x: 0,
        font: { size: 11.5, color: "#1a1a1a" },
      },
      hovermode: "x unified",
      shapes: [{
        type: "line", xref: "x", yref: "paper",
        x0: r.dia_d, x1: r.dia_d, y0: 0, y1: 1,
        line: { color: CORES.diaD, width: 1, dash: "dot" },
      }, ...shapesPC],
      annotations: [{
        x: r.dia_d, xref: "x", y: 1, yref: "paper",
        text: `último dado ${formatarDataBR(r.dia_d)}`,
        showarrow: false, yanchor: "bottom", xanchor: "left",
        font: { size: 10.5, color: "#888" },
      }, ...anotacoesPC],
    };
  }

  const CONFIG = {
    responsive: true,
    displayModeBar: false,   // sem comandos de manipulação (zoom, pan etc.)
    scrollZoom: false,
    doubleClick: false,
  };

  function gerarCSV(doc, r) {
    const L = [];
    const cab = `${doc.nome} (${doc.rio || ""}) · HidroWeb ${doc.codigo_hidroweb} · telemetria ${doc.estcodigo_telemetria}`;
    L.push(`Memória de cálculo — projeção por analogia;${cab}`);
    L.push(`Gerado em;${new Date().toLocaleString("pt-BR")}`);
    L.push(`Dados atualizados em;${formatarDataBR(doc.ultima_data)};fonte do último dado;${doc.fonte_ultimo_dado}`);
    L.push(`Dia D;${formatarDataBR(r.dia_d)};Cota atual (cm);${numeroBR(r.cota_atual, 0)}`);
    L.push(`Intervalo (cota atual ±);${numeroBR(r.range_valor)} ${r.modo === "cm" ? "cm" : "%"};equivalente em cm;±${numeroBR(r.limite_cm)}`);
    const datasCSV = datasDoAno(r.ano_atual);
    for (const [n, pc] of [["1", r.pc1], ["2", r.pc2]]) {
      if (pc === null || pc === undefined) continue;
      L.push(`Ponto de controle ${n} (cm);${numeroBR(pc, 0)}`);
      if (r.trajetorias) {
        for (const [nome, serie] of [
          ["maior_queda", r.trajetorias.maior_queda],
          ["menor_queda", r.trajetorias.menor_queda],
          ["media", r.trajetorias.media],
        ]) {
          const { entrada, saida } = cruzamentosTrajetoria(serie, datasCSV, r.idx_d, pc);
          L.push([`Toques no ponto de controle ${n} (${nome})`,
                  "entrada", entrada ? formatarDataBR(entrada.data) : "não atinge",
                  "saída", saida ? formatarDataBR(saida.data) : "—"].join(";"));
        }
      }
    }
    L.push(`Regras;tolerância ±3 dias no dia D;cobertura pós-D ≥80% e dado nos últimos 10 dias do ano`);
    L.push("");
    L.push("BLOCO 1 — Anos candidatos (universo completo e seleção)");
    L.push("ano;fonte_dos_dados;cota_em_D_cm;dias_tolerancia;cobertura_pos_D_%;min_pos_D_cm;delta_queda_cm;selecionado;motivo_exclusao");
    for (const c of r.candidatos) {
      L.push([
        c.ano,
        (doc.fonte_por_ano || {})[String(c.ano)] || "",
        numeroBR(c.cota_em_d, 0),
        c.dias_tolerancia === null ? "" : c.dias_tolerancia,
        c.cobertura === null ? "" : numeroBR(c.cobertura * 100),
        numeroBR(c.min_pos_d, 0),
        numeroBR(c.delta, 0),
        c.selecionado ? "sim" : "não",
        c.motivo || "",
      ].join(";"));
    }
    L.push("");
    L.push("BLOCO 2 — Séries do gráfico (dia a dia do ano corrente)");
    L.push("data;observado_cm;proj_maior_queda_cm;proj_menor_queda_cm;proj_media_cm;interpolado");
    const datas = datasCSV;
    const obs = doc.anos[String(r.ano_atual)];
    const tj = r.trajetorias;
    for (let i = 0; i < 366; i++) {
      if (datas[i] === null) continue;
      const temProj = tj && i >= r.idx_d;
      const interp = temProj && (tj.maior_queda_interp[i] || tj.menor_queda_interp[i]);
      const linha = [
        formatarDataBR(datas[i]),
        obs[i] === null || obs[i] === undefined ? "" : numeroBR(obs[i], 0),
        temProj ? numeroBR(tj.maior_queda[i]) : "",
        temProj ? numeroBR(tj.menor_queda[i]) : "",
        temProj ? numeroBR(tj.media[i]) : "",
        temProj && interp ? "sim" : "",
      ];
      if (linha.slice(1).some((v) => v !== "")) L.push(linha.join(";"));
    }
    return L.join("\r\n");
  }

  function baixarCSV(nomeArquivo, conteudo) {
    const blob = new Blob(["﻿" + conteudo], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nomeArquivo;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /** Cria a seção completa da estação dentro de `main`. */
  function montarSecao(main, doc) {
    const sec = document.createElement("section");
    sec.className = "estacao";
    sec.id = doc.slug;
    sec.innerHTML = `
      <div class="estacao-cabecalho">
        <h2>${doc.nome}</h2>
        <span class="estacao-codigos">rio ${doc.rio || "—"} · HidroWeb ${doc.codigo_hidroweb} · equip. ${doc.estcodigo_telemetria}</span>
        <span class="estacao-ultimo">Último dado: <strong>${formatarDataBR(doc.ultima_data)}</strong>
          · ${doc.ultimo_valor} cm (${doc.fonte_ultimo_dado})</span>
      </div>
      <div class="controles">
        <label title="Entram como análogos os anos em que a cota, neste mesmo dia do calendário, estava até este valor acima ou abaixo da cota atual.">
          Intervalo (cota atual ±)
          <input type="range" min="1" max="500" step="1" value="10" class="ctl-slider">
          <input type="number" min="0.5" max="500" step="0.5" value="10" class="ctl-num">
          <span class="ctl-unidade">cm</span></label>
        <span class="modo">
          <button type="button" class="ctl-cm ativo">± cm</button>
          <button type="button" class="ctl-pct">± %</button>
        </span>
        <span>Anos análogos: <span class="contagem">–</span></span>
        <span class="acoes">
          <button type="button" class="botao-csv botao-memoria"
             title="Memória de cálculo em PDF com o intervalo ajustado nos controles">Memória de cálculo (PDF)</button>
          <button type="button" class="botao-csv botao-sec" title="Memória de cálculo em CSV com o intervalo ajustado nos controles">CSV</button>
        </span>
      </div>
      <div class="controles-referencia">
        <label title="Linha horizontal de referência desenhada no gráfico (ex.: cota mínima navegável).">
          Cota do Ponto de controle 1
          <input type="number" step="1" class="ctl-pc1" placeholder="cm">
          <span>cm</span></label>
        <label class="pc-datas" title="Exibir no gráfico as datas em que cada projeção entra abaixo desta cota e em que volta a subir.">
          <input type="checkbox" class="ctl-pc1-datas" checked> datas</label>
        <label title="Linha horizontal de referência desenhada no gráfico.">
          Cota do Ponto de controle 2
          <input type="number" step="1" class="ctl-pc2" placeholder="cm">
          <span>cm</span></label>
        <label class="pc-datas" title="Exibir no gráfico as datas em que cada projeção entra abaixo desta cota e em que volta a subir.">
          <input type="checkbox" class="ctl-pc2-datas" checked> datas</label>
      </div>
      <p class="aviso"></p>
      <div class="grafico"></div>
      <p class="estacao-rodape"></p>
      <p class="cruzamentos-pc"></p>`;
    main.appendChild(sec);

    const el = {
      slider: sec.querySelector(".ctl-slider"),
      num: sec.querySelector(".ctl-num"),
      unidade: sec.querySelector(".ctl-unidade"),
      btnCm: sec.querySelector(".ctl-cm"),
      btnPct: sec.querySelector(".ctl-pct"),
      contagem: sec.querySelector(".contagem"),
      aviso: sec.querySelector(".aviso"),
      grafico: sec.querySelector(".grafico"),
      rodape: sec.querySelector(".estacao-rodape"),
      cruzamentos: sec.querySelector(".cruzamentos-pc"),
      csv: sec.querySelector(".botao-sec"),
      pc1: sec.querySelector(".ctl-pc1"),
      pc2: sec.querySelector(".ctl-pc2"),
      pc1Datas: sec.querySelector(".ctl-pc1-datas"),
      pc2Datas: sec.querySelector(".ctl-pc2-datas"),
    };
    // intervalo inicial: o menor (≥50 cm) que contém pelo menos 3 anos análogos
    const rangeAuto = Analogia.rangeInicial(doc);
    const estado = { range: rangeAuto, modo: "cm", resultado: null,
                     pc1: null, pc2: null, cruz1: true, cruz2: true };
    if (rangeAuto > 500) el.slider.max = String(Math.ceil(rangeAuto * 2));
    el.slider.value = String(rangeAuto);
    el.num.value = String(rangeAuto);

    /** Texto-resumo de quando cada projeção cruza os pontos de controle definidos. */
    function textoCruzamentos(r, datas, pontos) {
      if (!r.trajetorias) return "";
      const curvas = [
        ["maior queda", r.trajetorias.maior_queda],
        ["menor queda", r.trajetorias.menor_queda],
        ["média", r.trajetorias.media],
      ];
      const linhas = [];
      for (const [n, alvo] of [["1", pontos.pc1], ["2", pontos.pc2]]) {
        if (alvo === null || alvo === undefined || !isFinite(alvo)) continue;
        const partes = curvas.map(([nome, serie]) => {
          const { entrada, saida } = cruzamentosTrajetoria(serie, datas, r.idx_d, alvo);
          if (!entrada && !saida) return `${nome} não atinge`;
          const seg = [];
          if (entrada) seg.push(`entra em ${formatarDataBR(entrada.data).slice(0, 5)}`);
          if (saida) seg.push(`sai em ${formatarDataBR(saida.data).slice(0, 5)}`);
          return `${nome} ${seg.join(" e ")}`;
        });
        linhas.push(`Ponto de controle ${n} (${numeroBR(alvo, 0)} cm): ${partes.join(" · ")}.`);
      }
      return linhas.join(" ");
    }

    function render() {
      const r = Analogia.calcular(doc, estado.range, estado.modo);
      estado.resultado = r;
      const pontos = { pc1: estado.pc1, pc2: estado.pc2 };
      // no gráfico, só entram os toques dos PCs com o checkbox "datas" marcado
      const pontosCruz = { pc1: estado.cruz1 ? estado.pc1 : null,
                           pc2: estado.cruz2 ? estado.pc2 : null };
      const { traces, datas, anotacoesRotulos } = montarTraces(doc, r, pontosCruz, el.grafico.clientWidth);
      const layout = layoutBase(doc, r, pontos);
      layout.annotations = layout.annotations.concat(anotacoesRotulos);
      Plotly.react(el.grafico, traces, layout, CONFIG);
      el.contagem.textContent = String(r.selecionados.length);
      el.aviso.textContent = r.aviso || "";
      el.rodape.textContent = r.selecionados.length
        ? `Anos análogos (cota em ${formatarDataBR(r.dia_d).slice(0, 5)} dentro de ±${numeroBR(r.limite_cm)} cm da atual): ${r.selecionados.join(", ")}.`
        : "";
      el.cruzamentos.textContent = textoCruzamentos(r, datas, pontos);
    }

    let timer = null;
    function agendarRender() {
      clearTimeout(timer);
      timer = setTimeout(render, 150);
    }

    el.slider.addEventListener("input", () => {
      el.num.value = el.slider.value;
      estado.range = Number(el.slider.value);
      agendarRender();
    });
    el.num.addEventListener("input", () => {
      const v = Number(el.num.value);
      if (!isFinite(v) || v <= 0) return;
      estado.range = v;
      el.slider.value = String(Math.min(100, v));
      agendarRender();
    });
    function trocarModo(modo) {
      if (modo === estado.modo) return;
      // mantém o range equivalente ao trocar de unidade (cm <-> % da cota atual)
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      const cota = Math.abs(r.cota_atual) || 1;
      const novo = modo === "pct"
        ? Math.round((estado.range / cota) * 1000) / 10   // cm -> %, 1 casa decimal
        : Math.max(1, Math.round((cota * estado.range) / 100));  // % -> cm
      estado.modo = modo;
      estado.range = novo;
      el.btnCm.classList.toggle("ativo", modo === "cm");
      el.btnPct.classList.toggle("ativo", modo === "pct");
      el.unidade.textContent = modo === "cm" ? "cm" : "%";
      el.slider.step = modo === "cm" ? "1" : "0.1";
      el.slider.max = modo === "cm"
        ? String(Math.max(500, Math.ceil(rangeAuto * 2), Math.ceil(novo)))
        : String(Math.max(20, Math.ceil(novo * 2)));
      el.slider.value = String(novo);
      el.num.value = String(novo);
      render();
    }
    el.btnCm.addEventListener("click", () => trocarModo("cm"));
    el.btnPct.addEventListener("click", () => trocarModo("pct"));

    function lerPontoControle(input) {
      const v = Number(input.value);
      return input.value !== "" && isFinite(v) ? v : null;
    }
    el.pc1.addEventListener("input", () => {
      estado.pc1 = lerPontoControle(el.pc1);
      agendarRender();
    });
    el.pc2.addEventListener("input", () => {
      estado.pc2 = lerPontoControle(el.pc2);
      agendarRender();
    });
    el.pc1Datas.addEventListener("change", () => {
      estado.cruz1 = el.pc1Datas.checked;
      agendarRender();
    });
    el.pc2Datas.addEventListener("change", () => {
      estado.cruz2 = el.pc2Datas.checked;
      agendarRender();
    });

    function resultadoComPontosControle() {
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      return { ...r, pc1: estado.pc1, pc2: estado.pc2 };
    }
    sec.querySelector(".botao-memoria").addEventListener("click", () => {
      ExportarPDF.gerarMemoria(doc, resultadoComPontosControle());
    });
    el.csv.addEventListener("click", () => {
      const r = resultadoComPontosControle();
      baixarCSV(`analogia_${doc.slug}_${doc.ultima_data}.csv`, gerarCSV(doc, r));
    });

    REGISTRO.set(doc.slug, {
      doc,
      grafico: el.grafico,
      get resultado() {
        return estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      },
    });

    render();
  }

  return { montarSecao, datasDoAno, minimoTrajetoria, cruzamentosTrajetoria, registro: REGISTRO };
})();
