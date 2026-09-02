/* Página "Histórico completo": 1 gráfico por estação com todos os anos da
 * série integrada, a média e o ano vigente em destaque (com o valor mais
 * recente marcado). Reusa Dados.js para carregar/mesclar histórico + atual,
 * e os mesmos estilos/paleta de grafico.js para manter a aparência do site. */
"use strict";

(async function () {
  const main = document.getElementById("conteudo-historico");
  const carimbo = document.getElementById("carimbo");
  const nav = document.getElementById("nav-estacoes");

  const COR_VIGENTE = "#1a1a1a";
  const COR_MEDIA = "#009E73";
  const COR_FUNDO = "#e4e4e4";
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"];

  function dataHoraBR(iso) {
    return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }
  function formatarDataBR(iso) {
    return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
  }

  function traceAno(serie, datas, nome, cor, largura, unidade, opts = {}) {
    const x = [], y = [];
    for (let i = 0; i < 366; i++) {
      if (datas[i] !== null) {
        x.push(datas[i]);
        y.push(serie && serie[i] !== undefined ? serie[i] : null);
      }
    }
    return {
      x, y, name: nome, mode: "lines",
      line: { color: cor, width: largura, dash: opts.dash },
      hovertemplate: opts.semHover ? undefined : `${nome}: %{y:.0f} ${unidade}<extra></extra>`,
      hoverinfo: opts.semHover ? "skip" : undefined,
      showlegend: opts.legenda !== false,
      connectgaps: false,
    };
  }

  function marcadorValor(x, y, texto, cor, posicao) {
    return {
      x: [x], y: [y], mode: "markers+text", text: [texto],
      textposition: posicao, cliponaxis: false,
      marker: { color: cor, size: 8 },
      textfont: { size: 11, color: cor, family: "Segoe UI, system-ui, sans-serif" },
      hoverinfo: "skip", showlegend: false,
    };
  }

  function mediaHistorica(doc, anoAtual) {
    const anos = Object.keys(doc.anos).map(Number).filter((a) => a !== anoAtual);
    const media = new Array(366).fill(null);
    for (let i = 0; i < 366; i++) {
      const vals = [];
      for (const a of anos) {
        const v = doc.anos[String(a)][i];
        if (v !== null && v !== undefined) vals.push(v);
      }
      if (vals.length >= 3) media[i] = vals.reduce((s, v) => s + v, 0) / vals.length;
    }
    return {
      media,
      nAnos: anos.length,
      anoIni: Math.min(...anos),
      anoFim: Math.max(...anos),
    };
  }

  /** Mínimo da média no calendário: {valor, data ISO} (null se não houver). */
  function minimoDaMedia(media, datas) {
    let min = null, dataMin = null;
    for (let i = 0; i < 366; i++) {
      if (datas[i] !== null && media[i] !== null) {
        if (min === null || media[i] < min) { min = media[i]; dataMin = datas[i]; }
      }
    }
    return { min, dataMin };
  }

  function layout(doc, anoAtual) {
    return {
      margin: { l: 58, r: 16, t: 8, b: 34 },
      separators: ",.",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Segoe UI, system-ui, sans-serif", size: 12, color: "#555" },
      dragmode: false,
      xaxis: {
        fixedrange: true,
        tickvals: MESES.map((_, m) => `${anoAtual}-${String(m + 1).padStart(2, "0")}-01`),
        ticktext: MESES,
        hoverformat: "%d/%m",
        gridcolor: "#efefec",
        range: [`${anoAtual}-01-01`, `${anoAtual}-12-31`],
      },
      yaxis: {
        fixedrange: true,
        title: { text: `${doc.grandeza || "Cota"} (${doc.unidade || "cm"})`, font: { size: 12 } },
        tickformat: ",d",
        nticks: 14,
        gridcolor: "#efefec",
        // séries sintéticas: profundidade <= 0 significa passo emerso — o zero é referência
        zeroline: !!doc.sintetica,
        zerolinecolor: "#b3261e",
        zerolinewidth: 1,
      },
      legend: {
        orientation: "h", y: 1.02, yanchor: "bottom", x: 0,
        font: { size: 11.5, color: "#1a1a1a" },
      },
      hovermode: "x unified",
    };
  }

  const CONFIG = { responsive: true, displayModeBar: false, scrollZoom: false, doubleClick: false };

  /** datas[i] = "YYYY-MM-DD" do índice i no ano dado (espelho de Grafico.datasDoAno). */
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

  function montarEstacao(doc) {
    const anoAtual = parseInt(doc.ultima_data.slice(0, 4), 10);
    const datas = datasDoAno(anoAtual);
    const unidade = doc.unidade || "cm";

    const s = doc.sintetica;
    const sec = document.createElement("section");
    sec.className = "estacao" + (s ? " sintetica" : "");
    sec.id = `hist-${doc.slug}`;
    const codigos = s
      ? `rio ${doc.rio || "—"} · série calculada de ${s.bases.map((b) => b.nome).join(" e ")} ·`
      : `rio ${doc.rio || "—"} · HidroWeb ${doc.codigo_hidroweb} ·
          equip. ${doc.estcodigo_telemetria} ·`;
    const metodologia = s ? `
      <p class="estacao-metodologia"><strong>Série sintética</strong> — ${s.descricao}
        <code>${s.formula_texto}</code> · Fonte do método: ${s.fonte_metodo}.
        Publicada em cm inteiros; cada dia só existe quando ambas as bases têm dado. ${s.nota_sinal}</p>` : "";
    sec.innerHTML = `
      <div class="estacao-cabecalho">
        <h2>${doc.nome}</h2>
        <span class="estacao-codigos">${codigos}
          <a href="index.html#${doc.slug}" class="link-secundario">ver projeção →</a></span>
        <span class="estacao-ultimo">Último dado: <strong>${formatarDataBR(doc.ultima_data)}</strong>
          · ${doc.ultimo_valor} ${unidade} (${s ? "calculada · bases em " : ""}${doc.fonte_ultimo_dado})</span>
      </div>${metodologia}
      <div class="grafico"></div>`;
    main.appendChild(sec);

    const traces = [];
    for (const chave of Object.keys(doc.anos).sort()) {
      const ano = Number(chave);
      if (ano === anoAtual) continue;
      traces.push(traceAno(doc.anos[chave], datas, String(ano), COR_FUNDO, 1, unidade,
                           { legenda: false }));
    }
    const { media, nAnos, anoIni, anoFim } = mediaHistorica(doc, anoAtual);
    traces.push(traceAno(media, datas, `Média (${anoIni}–${anoFim} · ${nAnos} anos)`,
                         COR_MEDIA, 2.2, unidade, { dash: "dot" }));
    traces.push(traceAno(doc.anos[String(anoAtual)], datas, `Observado ${anoAtual}`,
                         COR_VIGENTE, 2.5, unidade));
    traces.push(marcadorValor(doc.ultima_data, doc.ultimo_valor,
                              String(Math.round(doc.ultimo_valor)), COR_VIGENTE, "top center"));

    // mínimo da média no ano, com valor e data (dia/mês)
    const { min, dataMin } = minimoDaMedia(media, datas);
    if (min !== null) {
      traces.push(marcadorValor(dataMin, min,
                                `${Math.round(min)} (${dataMin.slice(8, 10)}/${dataMin.slice(5, 7)})`,
                                COR_MEDIA, "bottom center"));
    }

    Plotly.newPlot(sec.querySelector(".grafico"), traces, layout(doc, anoAtual), CONFIG);
  }

  try {
    const indice = await Dados.carregarIndice();
    carimbo.textContent = `Atualizado em ${dataHoraBR(indice.atualizado_em)}`;
    for (const e of indice.estacoes) {
      const a = document.createElement("a");
      a.href = `#hist-${e.slug}`;
      a.textContent = e.nome;
      if (e.tipo === "sintetica") a.className = "sintetica";
      nav.appendChild(a);
    }
    for (const e of indice.estacoes) {
      try {
        montarEstacao(await Dados.carregarEstacao(e.slug));
      } catch (err) {
        const p = document.createElement("p");
        p.className = "erro";
        p.textContent = `Falha ao carregar ${e.nome}: ${err.message}`;
        main.appendChild(p);
      }
    }
  } catch (err) {
    main.innerHTML = `<p class="erro">Falha ao carregar os dados (${err.message}).
      Se abriu o arquivo localmente (file://), sirva a pasta com
      <code>python -m http.server</code>.</p>`;
    carimbo.textContent = "";
  }
})();
