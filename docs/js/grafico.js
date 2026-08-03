/* Montagem dos gráficos Plotly, controles de range e export CSV. */
"use strict";

const Grafico = (() => {
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
         CORES.maiorQueda, "dash"],
        [tj.menor_queda,
         `Menor queda (${r.ano_menor_queda}${rotuloQueda(r, r.ano_menor_queda)})`,
         CORES.menorQueda, "dash"],
        [tj.media, `Média (${r.selecionados.length} anos)`, CORES.media, "solid"],
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
      xaxis: {
        tickvals: MESES.map((_, m) => `${r.ano_atual}-${String(m + 1).padStart(2, "0")}-01`),
        ticktext: MESES,
        hoverformat: "%d/%m",
        gridcolor: "#efefec",
        range: [`${r.ano_atual}-01-01`, `${r.ano_atual}-12-31`],
      },
      yaxis: {
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
    displaylogo: false,
    locale: "pt-BR",
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    toImageButtonOptions: { format: "png", width: 1600, height: 800, scale: 2 },
  };

  function gerarCSV(doc, r) {
    const L = [];
    const cab = `${doc.nome} (${doc.rio || ""}) · HidroWeb ${doc.codigo_hidroweb} · telemetria ${doc.estcodigo_telemetria}`;
    L.push(`Memória de cálculo — projeção por analogia;${cab}`);
    L.push(`Gerado em;${new Date().toLocaleString("pt-BR")}`);
    L.push(`Dados atualizados em;${formatarDataBR(doc.ultima_data)};fonte do último dado;${doc.fonte_ultimo_dado}`);
    L.push(`Dia D;${formatarDataBR(r.dia_d)};Cota atual (cm);${numeroBR(r.cota_atual, 0)}`);
    L.push(`Range;±${numeroBR(r.range_valor)} ${r.modo === "cm" ? "cm" : "%"};equivalente em cm;±${numeroBR(r.limite_cm)}`);
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

  /** Cor da célula do heatmap de cobertura: 0% vermelho -> 50% amarelo -> 100% verde. */
  function corCobertura(pct) {
    const mistura = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
    const vermelho = [192, 57, 43], amarelo = [232, 195, 75], verde = [46, 125, 50];
    const rgb = pct <= 50
      ? mistura(vermelho, amarelo, pct / 50)
      : mistura(amarelo, verde, (pct - 50) / 50);
    return `rgb(${rgb.join(",")})`;
  }

  /** Heatmap HTML (1 célula por ano) da cobertura por fonte, para a memória. */
  function heatmapCobertura(doc) {
    const cf = doc.cobertura_fontes;
    if (!cf || !Object.keys(cf).length) return "";
    const ROTULOS = {
      consistido: "HIDRO consistido", bruto: "HIDRO bruto", telemetria: "Telemetria",
    };
    let anoMin = Infinity, anoMax = -Infinity;
    for (const cob of Object.values(cf)) {
      for (const a of Object.keys(cob)) {
        const ano = parseInt(a, 10);
        if (ano < anoMin) anoMin = ano;
        if (ano > anoMax) anoMax = ano;
      }
    }
    const anos = [];
    for (let a = anoMin; a <= anoMax; a++) anos.push(a);

    let linhas = "";
    for (const fonte of ["consistido", "bruto", "telemetria"]) {
      const cob = cf[fonte];
      if (!cob) continue;
      const celulas = anos.map((a) => {
        const pct = cob[String(a)];
        const estilo = pct === undefined ? "" : `background:${corCobertura(pct)}`;
        const titulo = pct === undefined ? `${a}: sem dado` : `${a}: ${pct}% dos dias`;
        return `<div class="hm-cel" style="${estilo}" title="${titulo}"></div>`;
      }).join("");
      linhas += `<div class="hm-linha"><span class="hm-rotulo">${ROTULOS[fonte]}</span>
        <div class="hm-celulas">${celulas}</div></div>`;
    }
    const eixo = anos.map((a) =>
      `<div class="hm-cel hm-eixo">${a % 10 === 0 ? a : ""}</div>`).join("");
    return `
<h2>2. Cobertura por fonte da série integrada</h2>
<div class="heatmap">
  ${linhas}
  <div class="hm-linha"><span class="hm-rotulo"></span><div class="hm-celulas">${eixo}</div></div>
</div>
<p class="nota">Cor = % de dias do ano com dado na fonte (verde 100% · amarelo 50% ·
vermelho 0%; branco = sem dado). A série integrada usa, dia a dia, a fonte de maior
prioridade disponível (consistido &gt; bruto &gt; telemetria). A telemetria é consultada
apenas na janela recente ainda não coberta pelo histórico congelado do HIDRO.</p>`;
  }

  /** Abre a memória de cálculo formatada em nova janela e dispara a impressão
   * (o usuário salva como PDF). Estrutura de leitura: parâmetros -> cobertura
   * -> candidatos -> projeções -> série dia a dia. */
  function abrirMemoriaPDF(doc, r) {
    const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const datas = datasDoAno(r.ano_atual);
    const obs = doc.anos[String(r.ano_atual)];
    const tj = r.trajetorias;

    const linhasCand = r.candidatos.map((c) => `
      <tr class="${c.selecionado ? "sel" : ""}">
        <td>${c.ano}</td>
        <td>${esc((doc.fonte_por_ano || {})[String(c.ano)] || "")}</td>
        <td class="n">${numeroBR(c.cota_em_d, 0)}</td>
        <td class="n">${c.dias_tolerancia === null ? "" : c.dias_tolerancia}</td>
        <td class="n">${c.cobertura === null ? "" : numeroBR(c.cobertura * 100, 0)}</td>
        <td class="n">${numeroBR(c.min_pos_d, 0)}</td>
        <td class="n">${numeroBR(c.delta, 0)}</td>
        <td>${c.selecionado ? "<strong>sim</strong>" : "não"}</td>
        <td>${esc(c.motivo || "")}</td>
      </tr>`).join("");

    let linhasProj = "";
    if (tj) {
      for (const [nome, serie, ano] of [
        ["Maior queda", tj.maior_queda, r.ano_maior_queda],
        ["Menor queda", tj.menor_queda, r.ano_menor_queda],
        ["Média", tj.media, `${r.selecionados.length} anos`],
      ]) {
        const { min, dataMin } = minimoTrajetoria(serie, datas, r.idx_d);
        const queda = min === null ? null : r.cota_atual - min;
        linhasProj += `<tr><td>${nome}</td><td>${ano}</td>
          <td class="n">${min === null ? "" : numeroBR(min, 0)}</td>
          <td>${dataMin ? formatarDataBR(dataMin) : ""}</td>
          <td class="n">${queda === null ? "" : numeroBR(queda, 0)}</td></tr>`;
      }
    }

    let linhasSerie = "";
    for (let i = 0; i < 366; i++) {
      if (datas[i] === null) continue;
      const temObs = obs[i] !== null && obs[i] !== undefined;
      const temProj = tj && i >= r.idx_d;
      if (!temObs && !temProj) continue;
      const interp = temProj && (tj.maior_queda_interp[i] || tj.menor_queda_interp[i]);
      linhasSerie += `<tr><td>${formatarDataBR(datas[i])}</td>
        <td class="n">${temObs ? numeroBR(obs[i], 0) : ""}</td>
        <td class="n">${temProj ? numeroBR(tj.maior_queda[i]) : ""}</td>
        <td class="n">${temProj ? numeroBR(tj.menor_queda[i]) : ""}</td>
        <td class="n">${temProj ? numeroBR(tj.media[i]) : ""}</td>
        <td>${interp ? "sim" : ""}</td></tr>`;
    }

    const html = `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Memória de cálculo — ${esc(doc.nome)}</title>
<style>
  body { font-family: "Segoe UI", system-ui, sans-serif; color: #1a1a1a;
         margin: 24px; font-size: 12px; line-height: 1.4; }
  h1 { font-size: 18px; margin: 0 0 2px; }
  h2 { font-size: 14px; margin: 18px 0 6px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
  .meta { color: #555; margin: 0 0 4px; }
  table { border-collapse: collapse; width: 100%; margin: 6px 0; }
  th, td { border: 1px solid #ddd; padding: 3px 7px; text-align: left; }
  th { background: #f2f1ee; font-weight: 600; }
  td.n { text-align: right; font-variant-numeric: tabular-nums; }
  tr.sel { background: #eef5fb; }
  .nota { color: #777; font-size: 11px; }
  .heatmap { margin: 8px 0 2px; }
  .hm-linha { display: flex; align-items: center; margin-bottom: 2px; }
  .hm-rotulo { width: 110px; flex: none; font-size: 11px; color: #555; padding-right: 6px; }
  .hm-celulas { display: flex; flex: 1; gap: 0; }
  .hm-cel { flex: 1; height: 14px; background: #fff;
            print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .hm-eixo { height: 12px; font-size: 8px; color: #777; overflow: visible;
             white-space: nowrap; text-align: left; }
  @media print { body { margin: 10mm; } h2 { break-after: avoid; } tr { break-inside: avoid; } }
</style></head><body>
<h1>Memória de cálculo — projeção por analogia</h1>
<p class="meta"><strong>${esc(doc.nome)}</strong> · rio ${esc(doc.rio || "—")} ·
  HidroWeb ${doc.codigo_hidroweb} · equip. ${doc.estcodigo_telemetria} ·
  gerado em ${new Date().toLocaleString("pt-BR")}</p>

<h2>1. Parâmetros</h2>
<table>
  <tr><th>Dia D (último dado)</th><td>${formatarDataBR(r.dia_d)} (${esc(doc.fonte_ultimo_dado)})</td>
      <th>Cota atual</th><td class="n">${numeroBR(r.cota_atual, 0)} cm</td></tr>
  <tr><th>Range</th><td>±${numeroBR(r.range_valor)} ${r.modo === "cm" ? "cm" : "%"}
      (equivale a ±${numeroBR(r.limite_cm)} cm)</td>
      <th>Anos análogos</th><td class="n">${r.selecionados.length}</td></tr>
</table>
<p class="nota">Regras: cota do candidato no dia D com tolerância de ±3 dias (mais próximo
primeiro; empate favorece o dia anterior); seleção se |cota − cota atual| ≤ range; exige-se
≥80% de cobertura entre D e 31/dez e dado nos últimos 10 dias do ano; delta de queda =
cota em D − mínimo pós-D; trajetórias deslocadas para coincidir com a cota atual em D;
lacunas internas interpoladas linearmente (marcadas na seção 4).</p>
${r.aviso ? `<p class="nota"><strong>Aviso:</strong> ${esc(r.aviso)}</p>` : ""}
${heatmapCobertura(doc)}

<h2>3. Universo de anos candidatos</h2>
<table>
  <tr><th>Ano</th><th>Fonte dos dados</th><th>Cota em D (cm)</th><th>Tolerância (dias)</th>
      <th>Cobertura pós-D (%)</th><th>Mín. pós-D (cm)</th><th>Delta de queda (cm)</th>
      <th>Selecionado</th><th>Motivo de exclusão</th></tr>
  ${linhasCand}
</table>

<h2>4. Projeções resultantes</h2>
${tj ? `<table>
  <tr><th>Curva</th><th>Ano de referência</th><th>Mínimo projetado (cm)</th><th>Data do mínimo</th>
      <th>Queda desde a cota atual (cm)</th></tr>
  ${linhasProj}
</table>` : "<p class='nota'>Sem projeção (nenhum ano análogo no range).</p>"}

<h2>5. Série dia a dia (${r.ano_atual})</h2>
<table>
  <tr><th>Data</th><th>Observado (cm)</th><th>Proj. maior queda (cm)</th>
      <th>Proj. menor queda (cm)</th><th>Proj. média (cm)</th><th>Interpolado</th></tr>
  ${linhasSerie}
</table>
<p class="nota">Fonte: data lake da ANA (banco HIDRO e telemetria) · série integrada
(consistido &gt; bruto &gt; telemetria). Documento gerado no navegador — use
"Salvar como PDF" na janela de impressão.</p>
</body></html>`;

    // iframe oculto + print(): não depende de pop-up (bloqueado em ambientes corporativos)
    const anterior = document.getElementById("frame-memoria");
    if (anterior) anterior.remove();
    const frame = document.createElement("iframe");
    frame.id = "frame-memoria";
    frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
    frame.addEventListener("load", () => {
      if (window.__semImprimir) return; // usado nos testes automatizados
      frame.contentWindow.focus();
      frame.contentWindow.print();
    });
    document.body.appendChild(frame);
    frame.srcdoc = html;
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
        <label>Range <input type="range" min="1" max="100" step="1" value="10" class="ctl-slider">
          <input type="number" min="0.5" max="500" step="0.5" value="10" class="ctl-num">
          <span class="ctl-unidade">cm</span></label>
        <span class="modo">
          <button type="button" class="ctl-cm ativo">± cm</button>
          <button type="button" class="ctl-pct">± %</button>
        </span>
        <span>Anos análogos: <span class="contagem">–</span></span>
        <span class="acoes">
          <button type="button" class="botao-csv botao-memoria">Memória de cálculo (PDF)</button>
          <button type="button" class="botao-csv botao-sec">CSV</button>
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
      memoria: sec.querySelector(".botao-memoria"),
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
      estado.modo = modo;
      el.btnCm.classList.toggle("ativo", modo === "cm");
      el.btnPct.classList.toggle("ativo", modo === "pct");
      el.unidade.textContent = modo === "cm" ? "cm" : "%";
      const padrao = modo === "cm" ? rangeAuto : 2;
      estado.range = padrao;
      el.slider.max = modo === "cm" ? String(Math.max(100, Math.ceil(rangeAuto * 2))) : "20";
      el.slider.value = String(padrao);
      el.num.value = String(padrao);
      render();
    }
    el.btnCm.addEventListener("click", () => trocarModo("cm"));
    el.btnPct.addEventListener("click", () => trocarModo("pct"));
    el.memoria.addEventListener("click", () => {
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      abrirMemoriaPDF(doc, r);
    });
    el.csv.addEventListener("click", () => {
      const r = estado.resultado || Analogia.calcular(doc, estado.range, estado.modo);
      baixarCSV(`analogia_${doc.slug}_${doc.ultima_data}.csv`, gerarCSV(doc, r));
    });

    render();
  }

  return { montarSecao };
})();
