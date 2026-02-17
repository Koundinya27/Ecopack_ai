console.log("app.js loaded");

let currentResults = [];
let lastRequestId = null;

// Handle form submit -> call /api/recommend
document.getElementById("request-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    product: {
      product_name: document.getElementById("product_name").value,
      product_category: document.getElementById("product_category").value,
      length_cm: parseFloat(document.getElementById("length_cm").value),
      width_cm: parseFloat(document.getElementById("width_cm").value),
      height_cm: parseFloat(document.getElementById("height_cm").value),
      weight_in_kg: parseFloat(document.getElementById("weight_in_kg").value),
      fragility_level: parseInt(document.getElementById("fragility_level").value),
      is_liquid: document.getElementById("is_liquid").checked,
      is_delicate: document.getElementById("is_delicate").checked,
      is_moisture_sensitive: document.getElementById("is_moisture_sensitive").checked,
      is_temperature_sensitive: document.getElementById("is_temperature_sensitive").checked,
    },
    preferences: {
      sustainability_level: document.getElementById("sustainability_level").value,
      budget_min_per_unit: parseFloat(document.getElementById("budget_min").value) || 0,
      budget_max_per_unit: parseFloat(document.getElementById("budget_max").value) || 0,
      total_units: parseInt(document.getElementById("total_units").value),
      prior_protection_level: document.getElementById("prior_protection_level").value,
    },
    packaging: {
      preset: document.getElementById("packaging_preset").value || "",
      box_length_cm: parseFloat(document.getElementById("box_length_cm").value) || 0,
      box_width_cm: parseFloat(document.getElementById("box_width_cm").value) || 0,
      box_height_cm: parseFloat(document.getElementById("box_height_cm").value) || 0,
      material_gsm: parseFloat(document.getElementById("material_gsm").value) || 0,
    },
  };

  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  // save request id for report
  lastRequestId = data.request_id;  // must be here, before renderTable

currentResults = (data.top_materials || []).map(m => ({
  id: m.material_id,                   // this exact key
  name: m.material_name,
  type: m.material_type,
  adjustedMass: (m.packaging_mass_per_unit_kg * 1000).toFixed(1),
  costPerUnit: m.cost_per_unit_inr.toFixed(2),
  totalCO2: m.total_co2_kg.toFixed(2),
  totalCost: m.total_packaging_cost_inr.toFixed(2),
  score: (100 - m.final_score * 100).toFixed(1),
}));

  // render results
  renderResults(data);
});

function renderResults(data) {
  console.log("renderResults called, items:", data.top_materials?.length);
  const tbody = document.getElementById("results-body");
  tbody.innerHTML = "";

  (data.top_materials || []).forEach((m) => {
    const row = document.createElement("tr");
    row.className = "result-row border-b";

    row.innerHTML = `
      <td class="px-6 py-4 text-sm font-medium text-gray-900">${m.material_name}</td>
      <td class="px-6 py-4 text-sm text-gray-700">${m.material_type}</td>
      <td class="px-6 py-4 text-sm text-right text-gray-700">${(m.packaging_mass_per_unit_kg * 1000).toFixed(1)}</td>
      <td class="px-6 py-4 text-sm text-right text-gray-700">${m.cost_per_unit_inr.toFixed(2)}</td>
      <td class="px-6 py-4 text-sm text-right text-gray-700">${m.total_co2_kg.toFixed(2)}</td>
      <td class="px-6 py-4 text-sm text-right text-gray-700">${m.total_packaging_cost_inr.toFixed(2)}</td>
      <td class="px-6 py-4 text-sm text-right font-semibold ${
        m.final_score <= 0.3 ? "text-green-600" :
        m.final_score <= 0.6 ? "text-yellow-600" :
        "text-red-600"
      }">${m.final_score.toFixed(3)}</td>
      <td class="px-6 py-4 text-sm text-right">
        <button
          type="button"
          class="select-btn inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
          data-request-id="${lastRequestId}"
          data-material-id="${m.material_id}"
        >
          Select
        </button>
      </td>
    `;

    tbody.appendChild(row);
  });
}


// View summary report button
document.addEventListener("DOMContentLoaded", () => {
  const reportBtn = document.getElementById("view-report-btn");
  if (!reportBtn) return;

  reportBtn.addEventListener("click", () => {
    if (!lastRequestId) return;
    window.open(`/report/${lastRequestId}`, "_blank");
  });
});

// Category filter buttons
document.addEventListener("DOMContentLoaded", () => {
  const chips = document.querySelectorAll(".filter-chip");

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const type = chip.dataset.type;
      const rows = document.querySelectorAll(".result-row");

      // visual state
      chips.forEach((c) => {
        c.classList.remove("bg-emerald-600", "text-white");
        c.classList.add("bg-emerald-50", "text-emerald-700");
      });
      chip.classList.add("bg-emerald-600", "text-white");
      chip.classList.remove("bg-emerald-50", "text-emerald-700");

      // filter rows
      rows.forEach((row) => {
        const rowType = row.dataset.type;
        if (type === "all" || rowType === type) {
          row.classList.remove("hidden");
        } else {
          row.classList.add("hidden");
        }
      });
    });
  });
});
