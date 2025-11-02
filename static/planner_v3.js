// === Planner v3 — Standard Grocery + Auto-Learning ===
console.log("Planner v3 JS loaded");

const STORAGE_KEY = "salimaPlannerV3";
const LEARN_KEY   = "salimaPlannerV3_Learned";

// --- Standard grocery categories ---
const DEFAULT_CATEGORIES = [
  "Produce","Bakery","Chilled","Dairy & Eggs","Meat & Fish","Frozen",
  "Pantry","Drinks","Snacks & Treats",
  "Household & Cleaning","Toiletries","Other"
];


// --- Keyword map for auto-categorisation ---
const CATEGORY_MAP = {
  "Produce": ["apple","banana","pear","grape","orange","lemon","lime","avocado","tomato","onion","carrot","pepper","potato","lettuce","salad","spinach","broccoli","cauliflower","mushroom","cucumber","herb","garlic","ginger","courgette","strawberry","blueberry","melon"],
  "Chilled": ["potato","gratin","tortilla"],
  "Bakery": ["bread","roll","baguette","wrap","pita","croissant","bun","pastry","cake","muffin","scone"],
  "Dairy & Eggs": ["milk","cheese","butter","cream","yogurt","feta","mozzarella","parmesan","egg"],
  "Meat & Fish": ["chicken","beef","lamb","pork","ham","bacon","turkey","sausage","mince","fish","salmon","tuna","cod","prawn","mackerel"],
  "Frozen": ["frozen","ice","peas","chips","pizza","nuggets","sweetcorn","berries","ice cream","fish fingers"],
  "Pantry": ["rice","pasta","noodle","flour","sugar","salt","spice","herb","oil","vinegar","sauce","ketchup","mayonnaise","mustard","tin","jar","stock","broth","cereal","oats","honey","jam","baking"],
  "Drinks": ["water","juice","soda","cola","tea","coffee","wine","beer","milkshake","smoothie"],
  "Snacks & Treats": ["chocolate","crisps","biscuit","bar","sweet","nuts","popcorn","cracker","dessert","pudding"],
  "Household & Cleaning": ["soap","detergent","bleach","foil","bin","bag","sponge","cloth","roll","paper","towel","cleaner","spray","washing","liquid"],
  "Toiletries": ["toothpaste","toothbrush","shampoo","conditioner","deodorant","razor","tissue","toilet","wipe","handwash","lotion"],
  "Other": []
};

// --- Load / Save helpers ---
function loadJSON(key) {
  try { return JSON.parse(localStorage.getItem(key)) || {}; }
  catch { return {}; }
}
function saveJSON(key, obj) {
  localStorage.setItem(key, JSON.stringify(obj));
}

// --- Toast notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;

  // Optional color variation
  if (type === "success") toast.style.background = "var(--brand-dark)";
  if (type === "error") toast.style.background = "#d9534f";
  if (type === "warn") toast.style.background = "#f0ad4e";

  container.appendChild(toast);

  // Remove after animation completes
  setTimeout(() => toast.remove(), 3000);
}

function learnNewIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (!trimmed) return;
  if (!learned[trimmed]) {
    learned[trimmed] = detectCategory(trimmed);
    saveJSON(LEARN_KEY, learned);
    buildIngredientSuggestions();
    showToast(`✅ Learned “${trimmed}”`, "success");
  }
}

function forgetIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (learned[trimmed]) {
    delete learned[trimmed];
    saveJSON(LEARN_KEY, learned);
    buildIngredientSuggestions();
    showToast(`🗑️ Forgotten “${trimmed}”`, "warn");
  }
}


// --- Ingredient cleaner (lightweight) ---
function cleanIngredient(raw) {
  if (!raw) return "";
  let s = raw.toLowerCase();
  s = s.replace(/\s*\n+\s*/g, " ");     // flatten newlines
  s = s.replace(/^[▢•\-–—]\s*/, "");    // remove bullets
  s = s.replace(/\(.*?\)/g, "");        // remove (optional) etc.
  s = s.replace(/^\s*\d+(\.\d+)?\s*[a-zA-Z%½¼¾⅓⅔⁄]*\s*/, ""); // remove qty/unit
  s = s.split(",")[0];                  // keep before comma
  if (/^(sauce|optional|garnish|for )/i.test(s.trim())) return "";
  s = s.trim().replace(/[.:;]+$/, "");
  s = s.replace(/\btomatoes?\b/, "tomato");
  s = s.replace(/\bcucumbers?\b/, "cucumber");
  s = s.replace(/\bcloves?\b/, "clove");
  s = s.replace(/\s{2,}/g, " ").trim();
  return s;
}

// --- Data stores ---
let data = loadJSON(STORAGE_KEY);
let learned = loadJSON(LEARN_KEY);
DEFAULT_CATEGORIES.forEach(c => { if (!data[c]) data[c] = []; });
saveJSON(STORAGE_KEY, data);

// --- DOM refs (one set only) ---
const grid       = document.getElementById("categoryGrid");
const input      = document.getElementById("ingredientInput");
const addBtn     = document.getElementById("addIngredientBtn");
const clearBtn   = document.getElementById("clearAllBtn");
const exportBtn  = document.getElementById("exportBtn");
const importBtn  = document.getElementById("importFromRecipesBtn");

// --- Detect + Learn ---
function detectCategory(name) {
  const lower = name.toLowerCase();
  if (learned[lower]) return learned[lower];
  for (const [cat, words] of Object.entries(CATEGORY_MAP))
    if (words.some(w => lower.includes(w))) return cat;
  return "Other";
}
function learnCategory(name, newCat) {
  const lower = name.toLowerCase();
  learned[lower] = newCat;
  saveJSON(LEARN_KEY, learned);
}

// --- Render ---
function render() {
  grid.innerHTML = "";
  for (const cat of DEFAULT_CATEGORIES) {
    const items = data[cat] || [];
    const div = document.createElement("div");
    div.className = "category" + (items.length === 0 ? " empty" : "");
    div.innerHTML = `
      <h3>${cat}</h3>
      <ul>
        ${items.map(i => `
          <li draggable="true">
            <input type="checkbox" ${i.checked ? "checked" : ""}>
            <span>${i.name}</span>
          </li>
        `).join("")}
      </ul>`;
    grid.appendChild(div);
  }
  attachHandlers();
}

// --- Event handlers (checkbox, dblclick delete, drag/drop) ---
function attachHandlers() {
  // check/uncheck
  document.querySelectorAll(".category input[type='checkbox']").forEach(box => {
    box.onchange = () => {
      const name = box.nextElementSibling.textContent.trim();
      const cat = box.closest(".category").querySelector("h3").textContent;
      const item = data[cat].find(i => i.name === name);
      if (item) item.checked = box.checked;
      saveJSON(STORAGE_KEY, data);
    };
  });

  // double-click delete
  document.querySelectorAll(".category li").forEach(li => {
    li.ondblclick = () => {
      const name = li.querySelector("span").textContent.trim();
      const cat = li.closest(".category").querySelector("h3").textContent;
      data[cat] = data[cat].filter(i => i.name !== name);
      saveJSON(STORAGE_KEY, data);
      forgetIngredient(name);
      render();
    };
  });

  // drag & drop
  document.querySelectorAll(".category li").forEach(li => {
    li.draggable = true;
    li.addEventListener("dragstart", e => {
      e.dataTransfer.setData("text/plain", li.querySelector("span").textContent.trim());
      li.classList.add("dragging");
    });
    li.addEventListener("dragend", () => li.classList.remove("dragging"));
  });

  document.querySelectorAll(".category").forEach(catDiv => {
    catDiv.addEventListener("dragover", e => {
      e.preventDefault();
      catDiv.classList.add("drag-over");
    });

    catDiv.addEventListener("dragleave", () => catDiv.classList.remove("drag-over"));

    catDiv.addEventListener("drop", e => {
      e.preventDefault();
      const name = e.dataTransfer.getData("text/plain");
      const newCat = catDiv.querySelector("h3").textContent;
      if (!name || !newCat) return;

      for (const cat of DEFAULT_CATEGORIES) {
        const idx = data[cat].findIndex(i => i.name === name);
        if (idx !== -1) {
          const [item] = data[cat].splice(idx, 1);
          data[newCat].push(item);
          break;
        }
      }

      saveJSON(STORAGE_KEY, data);
      render();
    });
  });
} // ✅ this closes attachHandlers() correctly


// --- Add / Clear / Export / Import ---
addBtn.onclick = () => {
  const val = input.value.trim();
  if (!val) return;

  const cat = detectCategory(val);
  const name = val.toLowerCase();
  data[cat].push({ name, checked: true });
  saveJSON(STORAGE_KEY, data);
  learnNewIngredient(name);
  render();
  input.value = "";
};


input.addEventListener("keypress", e => {
  if (e.key === "Enter") { e.preventDefault(); addBtn.click(); }
});

if (clearBtn) {
  clearBtn.onclick = () => {
    if (!confirm("Clear all items?")) return;
    data = {};
    DEFAULT_CATEGORIES.forEach(c => (data[c] = []));
    saveJSON(STORAGE_KEY, data);
    render();
  };
}

if (exportBtn) {
  exportBtn.onclick = () => {
    const overlay = document.getElementById("overlay");
    const out = document.getElementById("overlayContent");
    out.textContent = "";
    for (const cat of DEFAULT_CATEGORIES) {
      const items = data[cat].filter(i => i.checked);
      if (!items.length) continue;
      out.textContent += `${cat.toUpperCase()}:\n`;
      items.forEach(i => (out.textContent += `• ${i.name}\n`));
      out.textContent += "\n";
    }
    overlay.hidden = false;
  };
}
// --- Overlay controls ---
document.getElementById("closeOverlay").onclick = () =>
  (document.getElementById("overlay").hidden = true);

document.getElementById("copyBtn").onclick = () => {
  navigator.clipboard.writeText(
    document.getElementById("overlayContent").textContent
  );
  showToast("📋 Copied to clipboard!", "success");
};

document.getElementById("printBtn").onclick = () => {
  window.print();
  showToast("🖨️ Print dialog opened", "info");
};

// --- Import from selected recipes ---
if (importBtn) {
  importBtn.onclick = async () => {
    const stored = JSON.parse(localStorage.getItem("selectedRecipes") || "[]");
    if (!stored.length) {
      showToast("⚠️ No recipes selected.", "warn");
      return;
    }

    const ids = stored.map(r => (r.id ? r.id : r)).filter(Boolean);
    const resp = await fetch(`/api/selected?ids=${ids.join(",")}`);
    const json = await resp.json();

    if (!json.meals || !json.meals.length) {
      showToast("⚠️ No recipe data returned.", "warn");
      return;
    }

    let added = 0;
    for (const meal of json.meals) {
      const lines = Array.isArray(meal.ingredients)
        ? meal.ingredients.flatMap(t => t.split(/\r?\n|,/g))
        : (meal.ingredients || "").split(/\r?\n|,/g);

      for (const line of lines) {
        const clean = cleanIngredient(line);
        if (!clean) continue;

        const cat = detectCategory(clean);
        const existing = data[cat].find(i => i.name === clean);
        if (existing) {
          existing.qty = (existing.qty || 1) + 1;
        } else {
          data[cat].push({ name: clean, checked: true, qty: 1 });
        }
        added++;
      }
    }

    if (added > 0) {
      saveJSON(STORAGE_KEY, data);
      render();
      showToast(`✅ Added ${added} ingredients.`, "success");
    } else {
      showToast("ℹ️ No new ingredients added.", "info");
    }
  };
}


// --- Build autocomplete list from known items ---
function buildIngredientSuggestions() {
  const datalist = document.getElementById("ingredientSuggestions");
  if (!datalist) return;

  const known = new Set();

  // Add all keywords from category map and saved data
  Object.values(CATEGORY_MAP).flat().forEach(w => known.add(w));
  Object.values(data).flat().forEach(i => known.add(i.name));

  datalist.innerHTML = "";
  [...known].sort().forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    datalist.appendChild(opt);
  });
}

// --- Initial render ---
render();
buildIngredientSuggestions();

// --- Learn new custom ingredients automatically ---
function learnNewIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (!trimmed) return;
  if (!learned[trimmed]) {
    learned[trimmed] = detectCategory(trimmed); // store with detected category
    saveJSON(LEARN_KEY, learned);
    buildIngredientSuggestions(); // refresh autocomplete
  }
}

// --- Forget an ingredient when deleted (double-click) ---
function forgetIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (learned[trimmed]) {
    delete learned[trimmed];
    saveJSON(LEARN_KEY, learned);
    buildIngredientSuggestions();
  }
}
