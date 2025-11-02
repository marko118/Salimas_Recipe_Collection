// === Planner v3 — 4-Day Meal Plan Grid ===
console.log("planner_grid.js loaded");

const mealContainer = document.getElementById("mealGridContainer");
const dayToggle = document.getElementById("dayToggle");
const PLAN_KEY = "salimaMealPlan";

// --- Data helpers ---
function loadPlan() {
  try { return JSON.parse(localStorage.getItem(PLAN_KEY)) || {}; }
  catch { return {}; }
}
function savePlan(plan) {
  localStorage.setItem(PLAN_KEY, JSON.stringify(plan));
}

// --- Build grid ---
function buildMealGrid(start = "sun") {
  const plan = loadPlan();
  mealContainer.innerHTML = "";

  const days = start === "sun"
    ? ["Sunday", "Monday", "Tuesday", "Wednesday"]
    : ["Wednesday", "Thursday", "Friday", "Sunday"];

  const table = document.createElement("table");
  table.className = "meal-grid-table";
  table.innerHTML = `
    <thead>
      <tr><th>Day</th><th>Lunch</th><th>Dinner</th></tr>
    </thead>
    <tbody>
      ${days.map(day => `
        <tr>
          <td>${day}</td>
          <td contenteditable="true" data-day="${day}" data-slot="lunch">${plan[day]?.lunch || ""}</td>
          <td contenteditable="true" data-day="${day}" data-slot="dinner">${plan[day]?.dinner || ""}</td>
        </tr>
      `).join("")}
    </tbody>
  `;
  mealContainer.appendChild(table);

  attachMealHandlers();
}

// --- Handle typing / saving ---
function attachMealHandlers() {
  mealContainer.querySelectorAll("[contenteditable]").forEach(cell => {
    cell.addEventListener("input", () => {
      const day = cell.dataset.day;
      const slot = cell.dataset.slot;
      const plan = loadPlan();
      if (!plan[day]) plan[day] = {};
      plan[day][slot] = cell.textContent.trim();
      savePlan(plan);
    });
  });
}

// --- Listen to toggle changes ---
if (dayToggle) {
  dayToggle.addEventListener("change", e => {
    buildMealGrid(e.target.value);
  });
}
// --- Drag & Drop support ---
function enableDragAndDrop() {
  mealContainer.querySelectorAll("[contenteditable]").forEach(cell => {
    cell.addEventListener("dragover", e => {
      e.preventDefault();
      cell.classList.add("drag-over");
    });

    cell.addEventListener("dragleave", () => {
      cell.classList.remove("drag-over");
    });

    cell.addEventListener("drop", e => {
      e.preventDefault();
      const text = e.dataTransfer.getData("text/plain");
      cell.classList.remove("drag-over");
      if (!text) return;

      // insert recipe name
      cell.textContent = text;

      // persist to localStorage
      const day = cell.dataset.day;
      const slot = cell.dataset.slot;
      const plan = loadPlan();
      if (!plan[day]) plan[day] = {};
      plan[day][slot] = text;
      savePlan(plan);
    });
  });
}

// --- Initial load ---
buildMealGrid(dayToggle ? dayToggle.value : "sun");
