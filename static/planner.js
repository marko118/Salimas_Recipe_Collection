/* ===============================
   Planner v3 – Persistent Version (Revised for Planner.html)
   Uses /api/shopping_list backend
   =============================== */

console.log("Planner v3 – API-linked mode loaded (Planner.html).");

/* --- DOM references (updated IDs) --- */
const listContainer = document.getElementById("categoryGrid");   // ✅ updated
const ingredientInput = document.getElementById("ingredientInput");
const clearBtn = document.getElementById("clearListBtn");        // ✅ updated
const generateBtn = document.getElementById("exportBtn");        // ✅ updated
const saveBtn = document.getElementById("savePlannerBtn");       // ✅ new
const clearMealPlanBtn = document.getElementById("clearMealPlanBtn"); // ✅ new

/* --- Category list --- */
const categories = [
  "Produce", "Dairy & Eggs", "Meat & Fish",
  "Pantry", "Frozen", "Snacks", "Toiletries", "Other"
];

let items = [];

/* ===============================
   1. Fetch & Render
   =============================== */
async function loadShoppingList() {
  const res = await fetch("/api/shopping_list");
  items = await res.json();
  renderShoppingList();
}

function renderShoppingList() {
  listContainer.innerHTML = "";

  categories.forEach(cat => {
    const box = document.createElement("div");
    box.className = "category";
    box.dataset.cat = cat;

    const title = document.createElement("h3");
    title.textContent = cat;
    box.appendChild(title);

    const ul = document.createElement("ul");
    ul.className = "item-list";

    items
      .filter(i => (i.category || "Other") === cat && i.active !== false)
      .forEach(i => {
        const li = document.createElement("li");
        li.className = "item-row";
        li.draggable = true;
        li.dataset.id = i.id;
        li.dataset.category = cat;

        li.innerHTML = `
          <label style="flex:1;">
            <input type="checkbox" class="shop-item" data-id="${i.id}" ${i.checked ? "checked" : ""}>
            <span class="item-name" style="${i.crossed ? "text-decoration:line-through;opacity:0.6;" : ""}">
              ${i.name}
            </span>
          </label>
          <input type="text" class="amount-input" data-id="${i.id}" value="${i.amount || ""}" placeholder="1">
        `;
        ul.appendChild(li);
      });

    box.appendChild(ul);
    listContainer.appendChild(box);
  });

  attachHandlers();
  enableDragDrop();
}

/* ===============================
   2. Handlers & Updates
   =============================== */
function attachHandlers() {
  // checkbox toggle
  document.querySelectorAll(".shop-item").forEach(box => {
    box.onchange = async () => {
      const id = box.dataset.id;
      const checked = box.checked ? 1 : 0;
      await fetch(`/api/shopping_list/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checked })
      });
    };
  });

  // strike-through toggle
  document.querySelectorAll(".item-name").forEach(span => {
    span.onclick = async () => {
      const id = span.closest("label").querySelector(".shop-item").dataset.id;
      const crossed = !span.style.textDecoration.includes("line-through");
      span.style.textDecoration = crossed ? "line-through" : "none";
      span.style.opacity = crossed ? "0.6" : "1";
      await fetch(`/api/shopping_list/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ crossed })
      });
    };

    // delete on double click
    span.ondblclick = async () => {
      const id = span.closest("label").querySelector(".shop-item").dataset.id;
      if (confirm(`Delete "${span.textContent.trim()}"?`)) {
        await fetch(`/api/shopping_list/${id}`, { method: "DELETE" });
        await loadShoppingList();
      }
    };
  });

  // amount change
  document.querySelectorAll(".amount-input").forEach(inp => {
    inp.oninput = async () => {
      const id = inp.dataset.id;
      const amount = inp.value.trim();
      await fetch(`/api/shopping_list/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount })
      });
    };
  });

  // ingredient input → add on Enter
  if (ingredientInput) {
    ingredientInput.addEventListener("keydown", async e => {
      if (e.key === "Enter") {
        e.preventDefault();
        const name = ingredientInput.value.trim();
        if (!name) return;
        const cat = detectCategory(name);
        await addNewItem(name, cat);
        ingredientInput.value = "";
      }
    });
  }
}

/* ===============================
   3. Drag & Drop between categories
   =============================== */
function enableDragDrop() {
  const allCats = document.querySelectorAll(".category");
  let dragged = null;

  document.querySelectorAll(".item-row").forEach(row => {
    row.addEventListener("dragstart", () => {
      dragged = row;
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => {
      row.classList.remove("dragging");
      dragged = null;
    });
  });

  allCats.forEach(catBox => {
    catBox.addEventListener("dragover", e => e.preventDefault());
    catBox.addEventListener("drop", async e => {
      e.preventDefault();
      if (!dragged) return;
      const newCat = catBox.dataset.cat;
      const id = dragged.dataset.id;
      await fetch(`/api/shopping_list/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: newCat })
      });
      await loadShoppingList();
    });
  });
}

/* ===============================
   4. Add new item
   =============================== */
async function addNewItem(name, category) {
  const res = await fetch("/api/shopping_list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, category })
  });
  const data = await res.json();
  items.push({ id: data.id, name, category, checked: true, crossed: false, amount: "" });
  renderShoppingList();
}

/* ===============================
   5. Clear list & meal plan
   =============================== */
if (clearBtn) {
  clearBtn.onclick = async () => {
    if (confirm("Clear current shopping list (keep items in history)?")) {
      await fetch("/api/shopping_list/clear", { method: "POST" });
      await loadShoppingList();
    }
  };
}

if (clearMealPlanBtn) {
  clearMealPlanBtn.onclick = () => {
    if (confirm("Clear all meal plan selections?")) {
      const selects = document.querySelectorAll("#mealGridContainer select");
      selects.forEach(sel => (sel.value = ""));
      console.log("Meal plan cleared");
    }
  };
}

/* ===============================
   6. Save Planner (combined snapshot)
   =============================== */
if (saveBtn) {
  saveBtn.onclick = async () => {
    const plannerData = {
      timestamp: new Date().toISOString(),
      shopping_list: items,
      recipes: JSON.parse(localStorage.getItem("selectedRecipes") || "[]"),
      meal_plan: document.getElementById("mealGridContainer").innerHTML
    };
    await fetch("/api/planner/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(plannerData)
    });
    alert("💾 Planner saved successfully.");
  };
}

/* ===============================
   7. Overlay list
   =============================== */
if (generateBtn) {
  generateBtn.onclick = async () => {
    const overlay = document.getElementById("overlay");
    const content = document.getElementById("overlayContent");
    const dateBox = document.getElementById("overlayDate");

    dateBox.textContent = new Date().toLocaleString();
    content.innerHTML = "";

    categories.forEach(cat => {
      const catItems = items.filter(i => i.category === cat && i.checked && i.active !== false);
      if (!catItems.length) return;
      const header = document.createElement("div");
      header.textContent = cat.toUpperCase() + ":";
      header.style.fontWeight = "bold";
      content.appendChild(header);
      catItems.forEach(i => {
        const line = document.createElement("div");
        line.textContent = `• ${i.name}${i.amount ? ` (${i.amount})` : ""}`;
        if (i.crossed) {
          line.style.textDecoration = "line-through";
          line.style.opacity = "0.6";
        }
        content.appendChild(line);
      });
    });

    overlay.hidden = false;
  };
}

/* ===============================
   8. Category detection
   =============================== */
const KEYMAP = {
  "Dairy & Eggs": ["milk","cheese","cream","butter","yog","egg"],
  "Produce": ["apple","banana","tomato","onion","pepper","carrot","potato","garlic","lettuce","spinach","herb","lemon","lime","mushroom","broccoli"],
  "Meat & Fish": ["chicken","beef","lamb","ham","bacon","pork","turkey","fish","salmon","tuna","sausage","mince"],
  "Frozen": ["frozen","peas","ice","chips","sweetcorn","berries","pizza"],
  "Pantry": ["bread","rice","pasta","oil","salt","flour","spice","sugar","sauce","tin","jar","stock","broth","cereal"],
  "Snacks": ["crisps","bar","chocolate","sweet","biscuit","snack"],
  "Toiletries": ["soap","toothpaste","tooth","colgate","aquafresh","shampoo","roll","tissue"],
  "Other": []
};

function detectCategory(name) {
  const lower = name.toLowerCase();
  for (const [cat, words] of Object.entries(KEYMAP)) {
    if (words.some(w => lower.includes(w))) return cat;
  }
  return "Other";
}

/* ===============================
   9. Init
   =============================== */
document.addEventListener("DOMContentLoaded", loadShoppingList);
