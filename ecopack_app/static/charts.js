let co2Chart, costChart, scatterChart;

function renderResults(apiData) {
  const tbody = document.querySelector("#results-table tbody");
  tbody.innerHTML = "";

  const labels = [];
  const co2Data = [];
  const costData = [];
  const totalCo2 = [];
  const totalCost = [];
  const scatter = [];

  apiData.top_materials.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${m.material_name}</td>
      <td>${m.material_type}</td>
      
      <td>${m.packaging_mass_per_unit_kg.toFixed(3)}</td>
      <td>${m.cost_per_unit_inr.toFixed(2)}</td>
      <td>${m.total_co2_kg.toFixed(2)}</td>
      <td>${m.total_packaging_cost_inr.toFixed(2)}</td>
      <td>${m.final_score.toFixed(3)}</td>
    `;
    tbody.appendChild(tr);

    labels.push(m.material_name);
    co2Data.push(m.co2_per_kg);
    costData.push(m.cost_per_kg_inr);
    totalCo2.push(m.total_co2_kg);
    totalCost.push(m.total_packaging_cost_inr);
    scatter.push({ x: m.total_packaging_cost_inr, y: m.total_co2_kg });
  });

  document.getElementById("results").style.display = "block";

  if (co2Chart) co2Chart.destroy();
  if (costChart) costChart.destroy();
  if (scatterChart) scatterChart.destroy();

  co2Chart = new Chart(document.getElementById("co2Bar"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Total CO₂ (kg)", data: totalCo2, backgroundColor: "#4caf50" }],
    },
  });

  costChart = new Chart(document.getElementById("costBar"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Total cost (₹)", data: totalCost, backgroundColor: "#2196f3" }],
    },
  });

  scatterChart = new Chart(document.getElementById("costVsCo2"), {
    type: "scatter",
    data: {
      datasets: [{
        label: "Total cost vs total CO₂",
        data: scatter,
        backgroundColor: "#ff9800",
      }],
    },
    options: {
      scales: {
        x: { title: { display: true, text: "Total cost (₹)" } },
        y: { title: { display: true, text: "Total CO₂ (kg)" } },
      },
    },
  });
}
