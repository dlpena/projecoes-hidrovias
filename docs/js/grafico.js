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

  function marcador(x, y, texto, cor, posicao) {
    return {
      x: [x], y: [y], mode: "markers+text", text: [texto],
      textposition: posicao, cliponaxis: false,
      marker: { color: cor, size: 8 },
      textfont: { size: 11, color: cor, family: "Segoe UI, system-ui, sans-serif" },
      hoverinfo: "skip", showlegend: false,
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

  /** Posições de texto dos mínimos, evitando rótulos sobrepostos. */
  function posicionarRotulos(minimos, amplitudeY) {
    const limY = amplitudeY * 0.07;
    const pos = minimos.map(() => "bottom center");
    for (let i = 0; i < minimos.length; i++) {
      for (let j = i + 1; j < minimos.length; j++) {
        const dDias = Math.abs(new Date(minimos[i].x) - new Date(minimos[j].x)) / 864e5;
        if (dDias < 20 && Math.abs(minimos[i].y - minimos[j].y) < limY) {
          const cima = minimos[i].y >= minimos[j].y ? i : j;
          pos[cima] = pos[cima] === "top center" ? "middle right" : "top center";
        }
      }
    }
    return pos;
  }

  function montarTraces(doc, r) {
    const datas = datasDoAno(r.ano_atual);
    const traces = [];

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
      const minimos = [];
      for (const [serie, cor] of [
        [tj.maior_queda, CORES.maiorQueda],
        [tj.menor_queda, CORES.menorQueda],
        [tj.media, CORES.media],
      ]) {
        const { min, dataMin } = minimoTrajetoria(serie, datas, r.idx_d);
        if (min !== null) minimos.push({ x: dataMin, y: min, cor });
      }
      const posicoes = posicionarRotulos(minimos, faixaY(doc, r));
      minimos.forEach((m, i) => {
        traces.push(marcador(m.x, m.y, String(Math.round(m.y)), m.cor, posicoes[i]));
      });
    }
    return { traces, datas };
  }

  function layoutBase(doc, r) {
    return {
      margin: { l: 58, r: 16, t: 8, b: 34 },
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
      }],
      annotations: [{
        x: r.dia_d, xref: "x", y: 1, yref: "paper",
        text: `último dado ${formatarDataBR(r.dia_d)}`,
        showarrow: false, yanchor: "bottom", xanchor: "left",
        font: { size: 10.5, color: "#888" },
      }],
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
    const datas = datasDoAno(r.ano_atual);
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
          <input type="range" min="1" max="100" step="1" value="10" class="ctl-slider">
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
      <p class="aviso"></p>
      <div class="grafico"></div>
      <p class="estacao-rodape"></p>`;
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
      csv: sec.querySelector(".botao-sec"),
    };
    // range inicial: o menor (≥10 cm) que contém pelo menos 3 anos análogos
    const rangeAuto = Analogia.rangeInicial(doc);
    const estado = { range: rangeAuto, modo: "cm", resultado: null };
    if (rangeAuto > 100) el.slider.max = String(Math.ceil(rangeAuto * 2));
    el.slider.value = String(rangeAuto);
    el.num.value = String(rangeAuto);

    function render() {
      const r = Analogia.calcular(doc, estado.range, estado.modo);
      estado.resultado = r;
      const { traces } = montarTraces(doc, r);
      Plotly.react(el.grafico, traces, layoutBase(doc, r), CONFIG);
      el.contagem.textContent = String(r.selecionados.length);
      el.aviso.textContent = r.aviso || "";
      el.rodape.textContent = r.selecionados.length
        ? `Anos análogos (cota em ${formatarDataBR(r.dia_d).slice(0, 5)} dentro de ±${numeroBR(r.limite_cm)} cm da atual): ${r.selecionados.join(", ")}.`
        : "";
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
        ? String(Math.max(100, Math.ceil(rangeAuto * 2), Math.ceil(novo)))
        : String(Math.max(20, Math.ceil(novo * 2)));
      el.slider.value = String(novo);
      el.num.value = String(novo);
      render();
    }
    el.btnCm.addEventListener("click", () => trocarModo("cm"));
    el.btnPct.addEventListener("click", () => trocarModo("pct"));
    sec.querySelector(".botao-memoria").addEventListener("click", () => {
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      ExportarPDF.gerarMemoria(doc, r);
    });
    el.csv.addEventListener("click", () => {
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
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

  return { montarSecao, datasDoAno, minimoTrajetoria, registro: REGISTRO };
})();
