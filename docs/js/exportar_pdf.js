/* Geração dos PDFs no navegador (jsPDF + autotable, vendorizados), sempre a
 * partir do estado ATUAL da visualização (range/unidade ajustados pelo usuário):
 * - memória de cálculo por estação;
 * - PDF do conjunto (capa + 1 página por estação com a imagem do gráfico). */
"use strict";

const ExportarPDF = (() => {
  const MARGEM = 15; // mm

  // fontes padrão do jsPDF são latin-1: troca os símbolos fora dela
  const t = (s) => String(s)
    .replace(/≥/g, ">=").replace(/≤/g, "<=").replace(/−/g, "-").replace(/→/g, "->");

  const fmt = (v, casas = 1) =>
    v === null || v === undefined ? "" : v.toFixed(casas).replace(".", ",");

  const rotuloRange = (r) =>
    `±${fmt(r.range_valor, r.modo === "cm" ? 0 : 1)} ${r.modo === "cm" ? "cm" : "%"}`;

  /* 0% vermelho -> 50% amarelo -> 100% verde (mesma escala do pipeline antigo) */
  function corCobertura(pct) {
    const mistura = (a, b, tt) => a.map((v, i) => Math.round(v + (b[i] - v) * tt));
    const vermelho = [192, 57, 43], amarelo = [232, 195, 75], verde = [46, 125, 50];
    return pct <= 50
      ? mistura(vermelho, amarelo, pct / 50)
      : mistura(amarelo, verde, (pct - 50) / 50);
  }

  function tituloSecao(pdf, texto, y) {
    if (y > 270) { pdf.addPage(); y = MARGEM; }
    pdf.setFont("helvetica", "bold").setFontSize(11.5).setTextColor(26);
    pdf.text(t(texto), MARGEM, y);
    return y + 5;
  }

  function nota(pdf, texto, y, largura) {
    pdf.setFont("helvetica", "normal").setFontSize(7.5).setTextColor(110);
    const linhas = pdf.splitTextToSize(t(texto), largura);
    pdf.text(linhas, MARGEM, y);
    return y + linhas.length * 3.2 + 2;
  }

  const GRADE = {
    theme: "grid",
    styles: { fontSize: 7.5, cellPadding: 1.2, lineColor: [221, 221, 221],
              lineWidth: 0.15, textColor: [40, 40, 40] },
    headStyles: { fillColor: [242, 241, 238], textColor: [26, 26, 26],
                  fontStyle: "bold" },
    margin: { left: MARGEM, right: MARGEM },
  };

  function desenharHeatmap(pdf, docE, y, largura) {
    const cf = docE.cobertura_fontes;
    if (!cf || !Object.keys(cf).length) return y;
    const ROTULOS = { consistido: "HIDRO consistido", bruto: "HIDRO bruto",
                      telemetria: "Telemetria" };
    let anoMin = Infinity, anoMax = -Infinity;
    for (const cob of Object.values(cf)) {
      for (const a of Object.keys(cob)) {
        const ano = parseInt(a, 10);
        if (ano < anoMin) anoMin = ano;
        if (ano > anoMax) anoMax = ano;
      }
    }
    const n = anoMax - anoMin + 1;
    const rotuloW = 28, altura = 4;
    const celW = (largura - rotuloW) / n;
    for (const fonte of ["consistido", "bruto", "telemetria"]) {
      const cob = cf[fonte];
      if (!cob) continue;
      pdf.setFont("helvetica", "normal").setFontSize(6.5).setTextColor(85);
      pdf.text(ROTULOS[fonte], MARGEM, y + altura - 1);
      for (let i = 0; i < n; i++) {
        const pct = cob[String(anoMin + i)];
        if (pct !== undefined) {
          const [cr, cg, cb] = corCobertura(pct);
          pdf.setFillColor(cr, cg, cb);
          pdf.rect(MARGEM + rotuloW + i * celW, y, celW, altura, "F");
        }
      }
      y += altura + 0.6;
    }
    pdf.setFontSize(5.5).setTextColor(120);
    for (let i = 0; i < n; i++) {
      const ano = anoMin + i;
      if (ano % 10 === 0) pdf.text(String(ano), MARGEM + rotuloW + i * celW, y + 2.5);
    }
    return y + 5;
  }

  /* ---------------- memória de cálculo (retrato) ---------------- */

  function memoriaDoc(docE, r) {
    const pdf = new window.jspdf.jsPDF({ unit: "mm", format: "a4" });
    const largura = 210 - 2 * MARGEM;
    let y = MARGEM + 3;

    pdf.setFont("helvetica", "bold").setFontSize(15).setTextColor(26);
    pdf.text("Memória de cálculo — projeção por analogia", MARGEM, y);
    y += 6;
    pdf.setFont("helvetica", "normal").setFontSize(9).setTextColor(60);
    pdf.text(t(`${docE.nome} · rio ${docE.rio || "—"} · HidroWeb ${docE.codigo_hidroweb} · ` +
               `equip. ${docE.estcodigo_telemetria} · gerado em ${new Date().toLocaleString("pt-BR")}`),
             MARGEM, y);
    y += 8;

    y = tituloSecao(pdf, "1. Parâmetros", y);
    const dataD = r.dia_d.split("-").reverse().join("/");
    pdf.autoTable({
      ...GRADE, startY: y,
      body: [
        ["Dia D (último dado)", `${dataD} (${docE.fonte_ultimo_dado})`,
         "Cota atual", `${fmt(r.cota_atual, 0)} cm`],
        ["Range (o visualizado)", t(`${rotuloRange(r)} (equivale a ±${fmt(r.limite_cm)} cm)`),
         "Anos análogos", String(r.selecionados.length)],
      ],
      columnStyles: { 0: { fontStyle: "bold", cellWidth: 40 }, 2: { fontStyle: "bold", cellWidth: 30 } },
    });
    y = pdf.lastAutoTable.finalY + 3;
    y = nota(pdf,
      "Regras: cota do candidato no dia D com tolerância de ±3 dias (mais próximo primeiro; " +
      "empate favorece o dia anterior); seleção se |cota − cota atual| ≤ range; exige-se ≥80% " +
      "de cobertura entre D e 31/dez e dado nos últimos 10 dias do ano; delta de queda = cota " +
      "em D − mínimo pós-D; trajetórias deslocadas para coincidir com a cota atual em D; " +
      "lacunas internas interpoladas linearmente (marcadas na seção 5). Este documento reflete " +
      "o range ajustado na tela no momento da exportação.", y, largura);
    if (r.aviso) y = nota(pdf, `Aviso: ${r.aviso}`, y, largura);

    y = tituloSecao(pdf, "2. Cobertura por fonte da série integrada", y + 1);
    y = desenharHeatmap(pdf, docE, y, largura);
    y = nota(pdf,
      "Cor = % de dias do ano com dado na fonte (verde 100% · amarelo 50% · vermelho 0%; " +
      "branco = sem dado). A série integrada usa, dia a dia, a fonte de maior prioridade " +
      "disponível (consistido > bruto > telemetria). A telemetria é consultada apenas na " +
      "janela recente ainda não coberta pelo histórico congelado do HIDRO.", y, largura);

    y = tituloSecao(pdf, "3. Universo de anos candidatos", y + 1);
    const fpa = docE.fonte_por_ano || {};
    const selecionadas = new Set();
    const corpo = r.candidatos.map((c, i) => {
      if (c.selecionado) selecionadas.add(i);
      return [
        String(c.ano), fpa[String(c.ano)] || "", fmt(c.cota_em_d, 0),
        c.dias_tolerancia === null ? "" : String(c.dias_tolerancia),
        c.cobertura === null ? "" : fmt(c.cobertura * 100, 0),
        fmt(c.min_pos_d, 0), fmt(c.delta, 0),
        c.selecionado ? "sim" : "não", c.motivo || "",
      ];
    });
    pdf.autoTable({
      ...GRADE, startY: y,
      head: [["Ano", "Fonte", "Cota em D\n(cm)", "Toler.\n(dias)", "Cobert.\npós-D (%)",
              "Mín. pós-D\n(cm)", "Delta queda\n(cm)", "Selec.", "Motivo de exclusão"]],
      body: corpo,
      columnStyles: { 2: { halign: "right" }, 3: { halign: "right" }, 4: { halign: "right" },
                      5: { halign: "right" }, 6: { halign: "right" } },
      didParseCell: (d) => {
        if (d.section === "body" && selecionadas.has(d.row.index)) {
          d.cell.styles.fillColor = [238, 245, 251];
        }
      },
    });
    y = pdf.lastAutoTable.finalY + 6;

    y = tituloSecao(pdf, "4. Projeções resultantes", y);
    const tj = r.trajetorias;
    if (tj) {
      const datas = Grafico.datasDoAno(r.ano_atual);
      const linhas = [];
      for (const [nome, serie, ano] of [
        ["Maior queda", tj.maior_queda, String(r.ano_maior_queda)],
        ["Menor queda", tj.menor_queda, String(r.ano_menor_queda)],
        ["Média", tj.media, `${r.selecionados.length} anos`],
      ]) {
        const { min, dataMin } = Grafico.minimoTrajetoria(serie, datas, r.idx_d);
        linhas.push([nome, ano, fmt(min, 0),
                     dataMin ? dataMin.split("-").reverse().join("/") : "",
                     min === null ? "" : fmt(r.cota_atual - min, 0)]);
      }
      pdf.autoTable({
        ...GRADE, startY: y,
        head: [["Curva", "Ano de referência", "Mínimo projetado (cm)",
                "Data do mínimo", "Queda desde a cota atual (cm)"]],
        body: linhas,
        columnStyles: { 2: { halign: "right" }, 4: { halign: "right" } },
      });
      y = pdf.lastAutoTable.finalY + 6;
    } else {
      y = nota(pdf, "Sem projeção (nenhum ano análogo no range).", y, largura) + 3;
    }

    y = tituloSecao(pdf, `5. Série dia a dia (${r.ano_atual})`, y);
    const datas = Grafico.datasDoAno(r.ano_atual);
    const obs = docE.anos[String(r.ano_atual)];
    const serieCorpo = [];
    for (let i = 0; i < 366; i++) {
      if (datas[i] === null) continue;
      const temObs = obs[i] !== null && obs[i] !== undefined;
      const temProj = tj && i >= r.idx_d;
      if (!temObs && !temProj) continue;
      const interp = temProj && (tj.maior_queda_interp[i] || tj.menor_queda_interp[i]);
      serieCorpo.push([
        datas[i].split("-").reverse().join("/"),
        temObs ? fmt(obs[i], 0) : "",
        temProj ? fmt(tj.maior_queda[i]) : "",
        temProj ? fmt(tj.menor_queda[i]) : "",
        temProj ? fmt(tj.media[i]) : "",
        interp ? "sim" : "",
      ]);
    }
    pdf.autoTable({
      ...GRADE, startY: y,
      head: [["Data", "Observado (cm)", "Proj. maior queda (cm)",
              "Proj. menor queda (cm)", "Proj. média (cm)", "Interpolado"]],
      body: serieCorpo,
      columnStyles: { 1: { halign: "right" }, 2: { halign: "right" },
                      3: { halign: "right" }, 4: { halign: "right" } },
    });
    y = pdf.lastAutoTable.finalY + 4;
    nota(pdf, "Fonte: data lake da ANA (banco HIDRO e telemetria) · série integrada " +
              "(consistido > bruto > telemetria).", Math.min(y, 285), largura);
    return pdf;
  }

  function gerarMemoria(docE, r) {
    const unid = r.modo === "cm" ? "cm" : "pct";
    memoriaDoc(docE, r).save(
      `memoria_${docE.slug}_${docE.ultima_data}_${String(r.range_valor).replace(".", ",")}${unid}.pdf`);
  }

  /* ---------------- conjunto (paisagem, capa + 1 página/estação) ---------------- */

  async function conjuntoDoc(registros) {
    const pdf = new window.jspdf.jsPDF({ unit: "mm", format: "a4", orientation: "landscape" });
    const larguraPg = 297, larguraUtil = larguraPg - 2 * MARGEM;

    pdf.setFont("helvetica", "bold").setFontSize(20).setTextColor(26);
    pdf.text("Projeções de Nível — Estações-Chave para Hidrovias", larguraPg / 2, 45,
             { align: "center" });
    pdf.setFont("helvetica", "normal").setFontSize(11).setTextColor(60);
    pdf.text(t("Projeção por analogia · série integrada (HIDRO consistido > bruto > telemetria) · cotas em cm"),
             larguraPg / 2, 54, { align: "center" });
    pdf.text(t(`Gerado do site em ${new Date().toLocaleString("pt-BR")} — com os ranges ajustados na tela`),
             larguraPg / 2, 61, { align: "center" });

    const corpo = registros.map(({ doc, resultado }) => [
      doc.nome, doc.rio || "—",
      doc.ultima_data.split("-").reverse().join("/"), String(doc.ultimo_valor),
      t(rotuloRange(resultado)), String(resultado.selecionados.length),
    ]);
    pdf.autoTable({
      ...GRADE, startY: 75,
      styles: { ...GRADE.styles, fontSize: 9, cellPadding: 1.8 },
      head: [["Estação", "Rio", "Último dado", "Cota (cm)", "Range (visualizado)", "Anos análogos"]],
      body: corpo,
      columnStyles: { 3: { halign: "right" }, 5: { halign: "right" } },
      margin: { left: 60, right: 60 },
    });
    pdf.setFontSize(8.5).setTextColor(110);
    pdf.text(t("Fonte: data lake da ANA (banco HIDRO e telemetria) · memória de cálculo individual disponível no site"),
             larguraPg / 2, 200, { align: "center" });

    for (const { doc, resultado, grafico } of registros) {
      const png = await Plotly.toImage(grafico, { format: "png", width: 1400, height: 680, scale: 2 });
      pdf.addPage();
      pdf.setFont("helvetica", "bold").setFontSize(14).setTextColor(26);
      pdf.text(doc.nome, MARGEM, MARGEM + 2);
      pdf.setFont("helvetica", "normal").setFontSize(9).setTextColor(85);
      pdf.text(t(`rio ${doc.rio || "—"} · HidroWeb ${doc.codigo_hidroweb} · equip. ${doc.estcodigo_telemetria} · ` +
                 `último dado ${doc.ultima_data.split("-").reverse().join("/")} (${doc.ultimo_valor} cm, ` +
                 `${doc.fonte_ultimo_dado}) · range ${rotuloRange(resultado)}`),
               MARGEM, MARGEM + 8);
      const altura = larguraUtil * 680 / 1400;
      pdf.addImage(png, "PNG", MARGEM, MARGEM + 12, larguraUtil, altura);
      pdf.setFontSize(8).setTextColor(110);
      let rodape = resultado.selecionados.length
        ? t(`Anos análogos (±${fmt(resultado.limite_cm)} cm da cota atual ${fmt(resultado.cota_atual, 0)} cm): ` +
            resultado.selecionados.join(", "))
        : "Nenhum ano análogo no range.";
      if (resultado.aviso) rodape += t(` · Aviso: ${resultado.aviso}`);
      pdf.text(rodape, MARGEM, 200);
    }
    return pdf;
  }

  async function gerarConjunto(registros) {
    const hoje = new Date().toISOString().slice(0, 10);
    (await conjuntoDoc(registros)).save(`projecoes_conjunto_${hoje}.pdf`);
  }

  return { gerarMemoria, gerarConjunto, _memoriaDoc: memoriaDoc, _conjuntoDoc: conjuntoDoc };
})();
