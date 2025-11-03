/* ===============================
   Planner v3 – Persistent Version
   Uses /api/shopping_list backend
   =============================== */

console.log("Planner v3 – API-linked mode loaded.");

/* --- DOM references --- */
const listContainer = document.getElementById("shopping-categories");
const addIngredientsBtn = document.getElementById("addIngredientsBtn");
const clearBtn = document.getElementById("clearShoppingBtn");
const generateBtn = document.getElementById("generateListBtn");

/* --- Category list (update as needed) --- */
const categories = [
  "Produce", "Dairy & Eggs", "Meat & Fish",
  "Pantry", "Frozen", "Snacks", "Toiletries", "Other"
];

/* --- In-memory cache of current items --- */
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

    /* --- Add-item box --- */
    const addBox = document.createElement("input");
    addBox.type = "text";
    addBox.className = "add-item";
    addBox.placeholder = `Add ${cat.toLowerCase()} item...`;
    addBox.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        const name = addBox.value.trim();
        if (name) {
          addNewItem(name, cat);
          addBox.value = "";
        }
      }
    });

    box.appendChild(ul);
    box.appendChild(addBox);
    listContainer.appendChild(box);
  });

  attachHandlers();
}

/* ===============================
   2. Handlers & Updates
   =============================== */
function attachHandlers() {
  // Checkbox toggle
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

  // Strike-through on item name
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

    // Double-click delete
    span.ondblclick = async () => {
      const id = span.closest("label").querySelector(".shop-item").dataset.id;
      if (confirm(`Delete "${span.textContent.trim()}"?`)) {
        await fetch(`/api/shopping_list/${id}`, { method: "DELETE" });
        await loadShoppingList();
      }
    };
  });

  // Amount change
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
}

/* ===============================
   3. Add new item
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
   4. Add Ingredients from Meals
   =============================== */
if (addIngredientsBtn) {
  addIngredientsBtn.onclick = async () => {
    const checkedBoxes = document.querySelectorAll("#meals .meal .checkbox:checked");
    let added = 0;

    for (const box of checkedBoxes) {
      const name = box.parentNode.textContent.trim();
      if (!name) continue;
      const exists = items.some(i => i.name.toLowerCase() === name.toLowerCase());
      if (!exists) {
        const category = detectCategory(name);
        await addNewItem(name, category);
        added++;
      }
    }
    alert(`✅ Added ${added} new ingredients to the shopping list.`);
  };
}

/* ===============================
   5. Clear list (non-destructive)
   =============================== */
if (clearBtn) {
  clearBtn.onclick = async () => {
    if (confirm("Clear current list (keep items in history)?")) {
      await fetch("/api/shopping_list/clear", { method: "POST" });
      await loadShoppingList();
    }
  };
}

/* ===============================
   6. Generate overlay list
   =============================== */
if (generateBtn) {
  generateBtn.onclick = async () => {
    const overlay = document.getElementById("listOverlay");
    const list = document.getElementById("finalList");
    list.innerHTML = "";

    categories.forEach(cat => {
      const catItems = items.filter(i => i.category === cat && i.checked && i.active !== false);
      if (!catItems.length) return;
      const header = document.createElement("div");
      header.textContent = cat.toUpperCase() + ":";
      header.style.fontWeight = "bold";
      list.appendChild(header);
      catItems.forEach(i => {
        const line = document.createElement("div");
        line.textContent = `• ${i.name}${i.amount ? ` (${i.amount})` : ""}`;
        if (i.crossed) {
          line.style.textDecoration = "line-through";
          line.style.opacity = "0.6";
        }
        list.appendChild(line);
      });
    });

    overlay.style.display = "block";
    document.body.classList.add("overlay-active");
  };
}

/* ===============================
   7. Category detection (same logic)
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
   8. Init
   =============================== */
document.addEventListener("DOMContentLoaded", loadShoppingList);
