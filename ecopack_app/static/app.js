console.log("app.js loaded");

// ----------------- GLOBAL STATE -----------------
const defaultConfig = {
  main_title: "Sustainable Packaging Advisor",
  subtitle_text:
    "Find the perfect low-carbon, cost-effective packaging materials for your products with our intelligent recommendation engine.",
  calculate_button_text: "Calculate best material",
  background_color: "#ffffff",
  accent_color: "#10b981",
  text_color: "#1f2937",
  button_color: "#e11d48",
  surface_color: "#f0fdf4",
  font_family: "Plus Jakarta Sans",
};

let config = { ...defaultConfig };
let chartsVisible = false;
let charts = { co2: null, cost: null, scatter: null };
let currentResults = [];
let activeFilterType = "all";
let lastRequestId = null;

// ----------------- PRESET HANDLING -----------------
function loadPreset() {
  const preset = document.getElementById("packaging_preset").value;
  const customDiv = document.getElementById("custom-packaging");

  const presets = {
    "kraft-small": { l: 15, w: 10, h: 8, gsm: 250 },
    "kraft-medium": { l: 20, w: 15, h: 10, gsm: 300 },
    "kraft-large": { l: 25, w: 20, h: 12, gsm: 350 },
    "corrugated-small": { l: 18, w: 12, h: 9, gsm: 400 },
    "corrugated-medium": { l: 25, w: 18, h: 12, gsm: 500 },
    "corrugated-large": { l: 30, w: 22, h: 15, gsm: 600 },
    "recycled-small": { l: 16, w: 11, h: 9, gsm: 280 },
  };

  if (preset && preset !== "custom") {
    customDiv.style.display = "none";
    const dims = presets[preset];
    if (!dims) return;
    document.getElementById("box_length_cm").value = dims.l;
    document.getElementById("box_width_cm").value = dims.w;
    document.getElementById("box_height_cm").value = dims.h;
    document.getElementById("material_gsm").value = dims.gsm;
  } else if (preset === "custom") {
    customDiv.style.display = "block";
  } else {
    customDiv.style.display = "none";
  }
}

// ----------------- TABLE + SUMMARY RENDER -----------------
function getFilteredResults() {
  return activeFilterType === "all"
    ? currentResults
    : currentResults.filter((r) => r.type === activeFilterType);
}

function renderTable(results) {
  const summary = document.getElementById("results-summary");
  const titleEl = document.getElementById("summary-title");
  const subtitleEl = document.getElementById("summary-subtitle");
  const tbody = document.getElementById("results-body");

  if (!results || results.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="px-6 py-6 text-center text-sm text-gray-500">
          No materials match this filter.
        </td>
      </tr>`;
    if (summary) summary.classList.add("hidden");
    return;
  }

  const best = results[0];
  const maxScore = Math.max(...results.map((r) => parseFloat(r.score)));

  summary.classList.remove("hidden");
  titleEl.textContent = `Best material: ${best.name} (${best.type})`;
  subtitleEl.textContent = `Estimated total CO₂: ${best.totalCO2} kg, total cost: ₹${best.totalCost} for ${
    document.getElementById("total_units").value
  } units.`;

  tbody.innerHTML = results
    .map(
      (r, i) => `
      <tr
        class="result-row border-t border-emerald-100 hover:bg-emerald-50/50 cursor-pointer transition-colors ${
          i === 0 ? "bg-emerald-50/30" : ""
        }"
        data-index="${i}"
        data-type="${r.type}"
      >
        <td class="px-6 py-4">
          <div class="flex items-center gap-3">
            ${
              i === 0
                ? '<span class="w-6 h-6 bg-emerald-500 text-white text-xs font-bold rounded-full flex items-center justify-center">1</span>'
                : `<span class="w-6 h-6 bg-gray-200 text-gray-600 text-xs font-medium rounded-full flex items-center justify-center">${
                    i + 1
                  }</span>`
            }
            <span class="font-medium text-gray-800">${r.name}</span>
          </div>
        </td>
        <td class="px-6 py-4 text-gray-600 text-sm">${r.type}</td>
        <td class="px-6 py-4 text-right text-gray-700">${r.adjustedMass}g</td>
        <td class="px-6 py-4 text-right text-gray-700">₹${r.costPerUnit}</td>
        <td class="px-6 py-4 text-right text-gray-700 font-medium">${r.totalCO2}</td>
        <td class="px-6 py-4 text-right text-gray-700">₹${r.totalCost}</td>
        <td class="px-6 py-4 text-right">
          <span class="${
            parseFloat(r.score) === maxScore
              ? "text-emerald-600 font-bold text-lg"
              : "text-gray-700"
          }">
            ${r.score}
          </span>
        </td>
        <td class="px-4 py-2 text-right">
          <button type="button"
            class="material-button select-btn inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
            data-request-id="${lastRequestId}"
            data-material-id="${r.id}">
            Select
          </button>
        </td>
      </tr>
    `
    )
    .join("");

  document.querySelectorAll(".result-row").forEach((row) => {
    row.addEventListener("click", () =>
      highlightMaterial(parseInt(row.dataset.index))
    );
  });
}

// fallback simple table renderer (kept for compatibility)
function renderResults(apiData) {
  const mapped = (apiData.top_materials || []).map((m) => ({
    id: m.material_id,
    name: m.material_name,
    type: m.material_type,
    adjustedMass: (m.packaging_mass_per_unit_kg * 1000).toFixed(1),
    costPerUnit: m.cost_per_unit_inr.toFixed(2),
    totalCO2: m.total_co2_kg.toFixed(2),
    totalCost: m.total_packaging_cost_inr.toFixed(2),
    score: (100 - m.final_score * 100).toFixed(1),
  }));
  currentResults = mapped;
  renderTable(getFilteredResults());
}

// ----------------- CHARTS (TOP-5) -----------------
function createCharts(results) {
  if (!results || results.length === 0) return;

  const labels = results.map((r) => r.name);
  const co2Data = results.map((r) => parseFloat(r.totalCO2));
  const costData = results.map((r) => parseFloat(r.totalCost));

  const chartColors = results.map((_, i) => (i === 0 ? "#e11d48" : "#10b981"));
  const chartBorderColors = results.map((_, i) =>
    i === 0 ? "#be123c" : "#059669"
  );

  if (charts.co2) charts.co2.destroy();
  if (charts.cost) charts.cost.destroy();
  if (charts.scatter) charts.scatter.destroy();

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        grid: { color: "#e5e7eb" },
        ticks: {
          color: "#6b7280",
          font: { family: "Plus Jakarta Sans" },
        },
      },
      y: {
        grid: { color: "#e5e7eb" },
        ticks: {
          color: "#6b7280",
          font: { family: "Plus Jakarta Sans" },
        },
      },
    },
  };

  charts.co2 = new Chart(document.getElementById("co2-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "CO₂ (kg)",
          data: co2Data,
          backgroundColor: chartColors,
          borderColor: chartBorderColors,
          borderWidth: 2,
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...commonOptions,
      scales: {
        ...commonOptions.scales,
        y: {
          ...commonOptions.scales.y,
          title: { display: true, text: "CO₂ (kg)", color: "#374151" },
        },
      },
    },
  });

  charts.cost = new Chart(document.getElementById("cost-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Cost (₹)",
          data: costData,
          backgroundColor: chartColors,
          borderColor: chartBorderColors,
          borderWidth: 2,
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...commonOptions,
      scales: {
        ...commonOptions.scales,
        y: {
          ...commonOptions.scales.y,
          title: { display: true, text: "Cost (₹)", color: "#374151" },
        },
      },
    },
  });

  charts.scatter = new Chart(document.getElementById("scatter-chart"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Materials",
          data: results.map((r) => ({
            x: parseFloat(r.totalCO2),
            y: parseFloat(r.totalCost),
            label: r.name,
          })),
          backgroundColor: chartColors,
          borderColor: chartBorderColors,
          borderWidth: 2,
          pointRadius: 10,
          pointHoverRadius: 14,
        },
      ],
    },
    options: {
      ...commonOptions,
      plugins: {
        tooltip: {
          callbacks: {
            label: (ctx) =>
              `${ctx.raw.label}: CO₂ ${ctx.raw.x}kg, Cost ₹${ctx.raw.y}`,
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "CO₂ (kg)", color: "#374151" } },
        y: { title: { display: true, text: "Cost (₹)", color: "#374151" } },
      },
    },
  });
}

function highlightMaterial(index) {
  if (!charts.co2 || !charts.cost || !charts.scatter) return;
  const colorUpdate = (chart) => {
    chart.data.datasets[0].backgroundColor =
      chart.data.datasets[0].backgroundColor.map((_, i) =>
        i === index ? "#e11d48" : "#10b981"
      );
    chart.update();
  };
  colorUpdate(charts.co2);
  colorUpdate(charts.cost);
  colorUpdate(charts.scatter);
}

// Wrapper to be called by new handler
function renderResultsCharts(apiData) {
  createCharts(getFilteredResults());
}

// ----------------- CONFIG -----------------
function applyConfig(cfg) {
  document.getElementById("main-title").textContent =
    cfg.main_title || defaultConfig.main_title;
  document.getElementById("subtitle").textContent =
    cfg.subtitle_text || defaultConfig.subtitle_text;
  document.getElementById("calculate-btn-text").textContent =
    cfg.calculate_button_text || defaultConfig.calculate_button_text;

  document.body.style.fontFamily = `${
    cfg.font_family || defaultConfig.font_family
  }, sans-serif`;

  const btn = document.getElementById("calculate-btn");
  if (btn) {
    const baseColor = cfg.button_color || defaultConfig.button_color;
    const hoverColor = "#be123c";
    btn.style.backgroundColor = baseColor;
    btn.addEventListener("mouseenter", () => {
      btn.style.backgroundColor = hoverColor;
    });
    btn.addEventListener("mouseleave", () => {
      btn.style.backgroundColor = baseColor;
    });
  }
}

// ----------------- NEW MAIN SUBMIT HANDLER -----------------
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("product-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const length = parseFloat(document.getElementById("length_cm").value) || 0;
    const width = parseFloat(document.getElementById("width_cm").value) || 0;
    const height = parseFloat(document.getElementById("height_cm").value) || 0;
    const weight =
      parseFloat(document.getElementById("weight_in_kg").value) || 0.5;
    const frag =
      parseInt(document.getElementById("fragility_level").value) || 3;
    const totalUnits =
      parseInt(document.getElementById("total_units").value) || 1000;

    const product_category =
      document.getElementById("product_category").value;
    const product_name = document.getElementById("product_name").value;

    const is_liquid = document.getElementById("is_liquid").checked;
    const is_delicate = document.getElementById("is_delicate").checked;
    const is_moisture_sensitive = document.getElementById(
      "is_moisture_sensitive"
    ).checked;
    const is_temperature_sensitive = document.getElementById(
      "is_temperature_sensitive"
    ).checked;

    const sustainability_level =
      document.getElementById("sustainability_level").value;
    const budget_min_per_unit =
      parseFloat(document.getElementById("budget_min").value) || 0;
    const budget_max_per_unit =
      parseFloat(document.getElementById("budget_max").value) || 0;
    const prior_protection_level =
      document.getElementById("prior_protection_level").value;

    const preset = document.getElementById("packaging_preset").value;
    const packaging = {
      preset,
      box_length_cm:
        parseFloat(document.getElementById("box_length_cm").value) || null,
      box_width_cm:
        parseFloat(document.getElementById("box_width_cm").value) || null,
      box_height_cm:
        parseFloat(document.getElementById("box_height_cm").value) || null,
      material_gsm:
        parseFloat(document.getElementById("material_gsm").value) || null,
    };

    const payload = {
      product: {
        product_name,
        product_category,
        length_cm: length,
        width_cm: width,
        height_cm: height,
        weight_in_kg: weight,
        fragility_level: frag,
        is_liquid,
        is_delicate,
        is_moisture_sensitive,
        is_temperature_sensitive,
      },
      preferences: {
        sustainability_level,
        budget_min_per_unit,
        budget_max_per_unit,
        total_units: totalUnits,
        prior_protection_level,
      },
      packaging,
    };

    try {
      const resp = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        console.error("API error", await resp.text());
        alert("Failed to get recommendations from server.");
        return;
      }

      const data = await resp.json();
      lastRequestId = data.request_id;

      const topMaterials = data.top_materials || [];
      const baselines = data.traditional_baselines || [];

      let selectedMaterial = null;
      if (topMaterials.length > 0) {
        selectedMaterial = topMaterials[0];
      }

      function computeReductions(selected, baselineList) {
        if (!selected) return [];
        return baselineList.map((b) => {
          const costRed =
            ((b.cost_per_unit_inr - selected.cost_per_unit_inr) /
              (b.cost_per_unit_inr || 1)) *
            100;
          const co2Red =
            ((b.co2_per_unit_kg - selected.co2_per_unit_kg) /
              (b.co2_per_unit_kg || 1)) *
            100;
          return {
            baselineName: b.name,
            costReductionPct: costRed,
            co2ReductionPct: co2Red,
          };
        });
      }

      const reductions = computeReductions(selectedMaterial, baselines);

      currentResults = (topMaterials || []).map((m) => ({
        id: m.material_id,
        name: m.material_name,
        type: m.material_type,
        adjustedMass: (m.packaging_mass_per_unit_kg * 1000).toFixed(1),
        costPerUnit: m.cost_per_unit_inr.toFixed(2),
        totalCO2: m.total_co2_kg.toFixed(2),
        totalCost: m.total_packaging_cost_inr.toFixed(2),
        score: (100 - m.final_score * 100).toFixed(1),
      }));

      renderTable(getFilteredResults());

      const resultsSection = document.getElementById("results-section");
      if (resultsSection) resultsSection.classList.remove("hidden");

      const emptyState = document.getElementById("results-empty");
      if (emptyState) emptyState.classList.add("hidden");

      const chartsSection = document.getElementById("charts-section");
      if (chartsSection) chartsSection.classList.add("hidden");
      chartsVisible = false;

      const showChartsBtn = document
        .getElementById("show-charts-btn")
        ?.querySelector("span");

      if (showChartsBtn) showChartsBtn.textContent = "Show results in charts";

      const comparisonSection = document.getElementById("comparison-section");
      if (comparisonSection) comparisonSection.classList.remove("hidden");

      resultsSection?.scrollIntoView({ behavior: "smooth", block: "start" });

      if (
        selectedMaterial &&
        baselines.length > 0 &&
        typeof drawReductionCharts === "function"
      ) {
        drawReductionCharts(selectedMaterial, baselines, reductions);
      }
    } catch (err) {
      console.error("Fetch error", err);
      alert("Something went wrong while contacting the recommendation engine.");
    }
  });
});

// show/hide charts button
document.addEventListener("DOMContentLoaded", () => {
  const showChartsBtn = document.getElementById("show-charts-btn");
  if (!showChartsBtn) return;

  showChartsBtn.addEventListener("click", function () {
    const section = document.getElementById("charts-section");
    chartsVisible = !chartsVisible;
    section.classList.toggle("hidden", !chartsVisible);
    this.querySelector("span").textContent = chartsVisible
      ? "Hide charts"
      : "Show results in charts";

    if (chartsVisible) {
      const filtered = getFilteredResults();
      createCharts(filtered);
      document.querySelectorAll(".chart-card").forEach((card) => {
        card.style.opacity = "1";
      });
    }
  });
});

// filter chips
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeFilterType = chip.getAttribute("data-type");

      document.querySelectorAll(".filter-chip").forEach((c) => {
        c.classList.remove("bg-emerald-600", "text-white");
        c.classList.add("bg-emerald-50", "text-emerald-700");
      });
      chip.classList.remove("bg-emerald-50", "text-emerald-700");
      chip.classList.add("bg-emerald-600", "text-white");

      const filtered = getFilteredResults();
      renderTable(filtered);
      if (chartsVisible) createCharts(filtered);
    });
  });
});

// report button (HTML / client-side report; unused for PDF)
document.addEventListener("DOMContentLoaded", () => {
  const reportBtn = document.getElementById("view-report-btn");
  if (!reportBtn) return;
  reportBtn.addEventListener("click", () => {
    if (!lastRequestId) return;
    window.open(`/report/${lastRequestId}`, "_blank");
  });
});

// apply initial config
document.addEventListener("DOMContentLoaded", () => {
  applyConfig(config);
});

// select-btn click handler (confirm_selection + highlight + PDF; stay on Advisor)
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".select-btn");
  if (!btn) return;

  const requestId = btn.dataset.requestId;
  const materialId = btn.dataset.materialId;
  console.log("BIN DATA:", { requestId, materialId });

  if (!requestId || !materialId) {
    alert("Missing request or material id.");
    return;
  }

  const confirmed = window.confirm(
    "Generate report for this selected material?"
  );
  if (!confirmed) return;

  try {
    const res = await fetch("/api/confirm_selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: parseInt(requestId, 10),
        material_id: parseInt(materialId, 10),
      }),
    });

    if (!res.ok) {
      console.error("Selection failed", await res.text());
      alert("Failed to save selection. Try again.");
      return;
    }

    const data = await res.json();

    // clear old highlight
    document
      .querySelectorAll(".material-button.selected")
      .forEach((el) => el.classList.remove("selected"));

    // highlight this button
    btn.classList.add("selected");
    btn.textContent = "Selected";
    btn.disabled = true;

    // open PDF in new tab; stay on Advisor (no redirect)
    if (data.pdf_url) {
      window.open(data.pdf_url, "_blank");
    }
  } catch (err) {
    console.error(err);
    alert("Network error while saving selection.");
  }
});
