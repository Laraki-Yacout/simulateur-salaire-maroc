// Histogramme de la page /statistiques (données préparées côté serveur).
(function () {
  "use strict";

  const canvas = document.getElementById("histogramme");
  const source = document.getElementById("donnees-histogramme");
  if (!canvas || !source || typeof Chart === "undefined") return;

  const donnees = JSON.parse(source.textContent);
  const css = getComputedStyle(document.documentElement);
  const couleur = (nom) => css.getPropertyValue(nom).trim();

  Chart.defaults.font.family = couleur("--sans");
  Chart.defaults.color = couleur("--encre-douce");

  new Chart(canvas, {
    type: "bar",
    data: {
      labels: donnees.etiquettes,
      datasets: [{
        data: donnees.valeurs,
        backgroundColor: donnees.valeurs.map((_, i) =>
          i === donnees.indexMediane ? couleur("--bordeaux-fonce") : couleur("--rose")
        ),
        hoverBackgroundColor: couleur("--bordeaux"),
        borderRadius: 0,
        categoryPercentage: 0.92,
        barPercentage: 1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: couleur("--encre"),
          titleColor: couleur("--creme"),
          bodyColor: couleur("--creme"),
          cornerRadius: 0,
          displayColors: false,
          padding: 10,
          callbacks: {
            title: (items) => donnees.titres[items[0].dataIndex],
            label: (item) => {
              const nombre = item.parsed.y;
              const texte = nombre + (nombre > 1 ? " contributions" : " contribution");
              return item.dataIndex === donnees.indexMediane ? [texte, "Contient la médiane"] : texte;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: couleur("--encre") },
          ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 8 },
          title: { display: true, text: "Salaire mensuel (milliers de DH)" },
        },
        y: {
          beginAtZero: true,
          grid: { color: couleur("--filet") },
          border: { display: false },
          ticks: { precision: 0 },
        },
      },
    },
  });
})();
