// charts.js

let co2Chart, costChart, scatterChart;
let co2ReductionChart, costReductionChart;

/**
 * Render per-request results charts based on API response.
 * - Bar: total CO₂ per material
 * - Bar: total cost per material
 * - Scatter: total cost vs total CO₂
 */
function renderResultsCharts(apiData) {
  const tbody = document.querySelector("#results-table tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const labels = [];
  const totalCo2 = [];
  const totalCost = [];
  const scatter = [];

  (apiData.top_materials || []).forEach((m) => {
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
    totalCo2.push(m.total_co2_kg);
    totalCost.push(m.total_packaging_cost_inr);
    scatter.push({ x: m.total_packaging_cost_inr, y: m.total_co2_kg });
  });

  const resultsSection = document.getElementById("results");
  if (resultsSection) {
    resultsSection.style.display = "block";
  }

  if (co2Chart) co2Chart.destroy();
  if (costChart) costChart.destroy();
  if (scatterChart) scatterChart.destroy();

  const co2Ctx = document.getElementById("co2-chart");
  if (co2Ctx) {
    co2Chart = new Chart(co2Ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Total CO₂ (kg)",
            data: totalCo2,
            backgroundColor: "#4caf50",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  const costCtx = document.getElementById("cost-chart");
  if (costCtx) {
    costChart = new Chart(costCtx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Total cost (₹)",
            data: totalCost,
            backgroundColor: "#2196f3",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  const scatterCtx = document.getElementById("scatter-chart");
  if (scatterCtx) {
    scatterChart = new Chart(scatterCtx, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Total cost vs total CO₂",
            data: scatter,
            backgroundColor: "#ff9800",
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "Total cost (₹)" } },
          y: { title: { display: true, text: "Total CO₂ (kg)" } },
        },
      },
    });
  }
}

/**
 * Draw traditional vs selected per-unit comparison charts.
 * - Bar: CO₂ per unit (selected vs each traditional baseline)
 * - Bar: Cost per unit (selected vs each traditional baseline)
 */
function drawReductionCharts(selected, baselines, reductions) {
  if (!selected || !baselines || !baselines.length) return;

  const labels = ["Selected"].concat(baselines.map((b) => b.name));
  const co2Data = [selected.co2_per_unit_kg].concat(
    baselines.map((b) => b.co2_per_unit_kg)
  );
  const costData = [selected.cost_per_unit_inr].concat(
    baselines.map((b) => b.cost_per_unit_inr)
  );

  if (co2ReductionChart) co2ReductionChart.destroy();
  if (costReductionChart) costReductionChart.destroy();

  const ctxCo2 = document.getElementById("co2ReductionChart");
  if (ctxCo2) {
    co2ReductionChart = new Chart(ctxCo2, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "CO₂ per unit (kg)",
            data: co2Data,
            backgroundColor: ["#16a34a"].concat(
              baselines.map(() => "#9ca3af")
            ),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  const ctxCost = document.getElementById("costReductionChart");
  if (ctxCost) {
    costReductionChart = new Chart(ctxCost, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Cost per unit (₹)",
            data: costData,
            backgroundColor: ["#2563eb"].concat(
              baselines.map(() => "#9ca3af")
            ),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }
}
