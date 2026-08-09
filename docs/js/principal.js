/* Carrega o índice e os JSONs das estações e monta a página. */
"use strict";

(async function () {
  const main = document.getElementById("conteudo");
  const carimbo = document.getElementById("carimbo");
  const nav = document.getElementById("nav-estacoes");

  function dataHoraBR(iso) {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }

  // ajuda (Como funciona?) — independe do carregamento dos dados
  const ajuda = document.getElementById("ajuda");
  document.getElementById("btn-ajuda").addEventListener("click", () => ajuda.showModal());
  document.getElementById("btn-fechar-ajuda").addEventListener("click", () => ajuda.close());
  ajuda.addEventListener("click", (e) => { if (e.target === ajuda) ajuda.close(); });

  try {
    const indice = await Dados.carregarIndice();
    carimbo.textContent = `Atualizado em ${dataHoraBR(indice.atualizado_em)}`;

    for (const e of indice.estacoes) {
      const a = document.createElement("a");
      a.href = `#${e.slug}`;
      a.textContent = e.nome;
      nav.appendChild(a);
    }

    for (const e of indice.estacoes) {
      try {
        Grafico.montarSecao(main, await Dados.carregarEstacao(e.slug));
      } catch (err) {
        const p = document.createElement("p");
        p.className = "erro";
        p.textContent = `Falha ao carregar ${e.nome}: ${err.message}`;
        main.appendChild(p);
      }
    }

    // PDF do conjunto: gerado na hora, com os gráficos como estão na tela
    const btn = document.getElementById("btn-pdf-conjunto");
    btn.disabled = false;
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const original = btn.textContent;
      btn.textContent = "Gerando…";
      try {
        await ExportarPDF.gerarConjunto([...Grafico.registro.values()]);
      } catch (err) {
        alert(`Falha ao gerar o PDF: ${err.message}`);
      } finally {
        btn.textContent = original;
        btn.disabled = false;
      }
    });
  } catch (err) {
    main.innerHTML = `<p class="erro">Falha ao carregar os dados (${err.message}).
      Se abriu o arquivo localmente (file://), sirva a pasta com
      <code>python -m http.server</code>.</p>`;
    carimbo.textContent = "";
  }
})();
