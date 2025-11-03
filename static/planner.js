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
//function loadJSON(key) {
//  try { return JSON.parse(localStorage.getItem(key)) || {}; }
//  catch { return {}; }
//}
//function saveJSON(key, obj) {
//  localStorage.setItem(key, JSON.stringify(obj));
//}

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
// --- Temporary in-memory learned map (keeps old code happy) ---
let learned = {};


function learnNewIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (!trimmed) return;
  if (!learned[trimmed]) {
    learned[trimmed] = detectCategory(trimmed);
    saveServerData();

    buildIngredientSuggestions();
    showToast(`✅ Learned “${trimmed}”`, "success");
  }
}

function forgetIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (learned[trimmed]) {
    delete learned[trimmed];
    saveServerData();

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
let data = {};

//let learned = loadJSON(LEARN_KEY);
DEFAULT_CATEGORIES.forEach(c => { if (!data[c]) data[c] = []; });
//saveServerData();


// === Shared Shopping List API helpers ===
async function loadServerData() {
  try {
    const resp = await fetch("/api/shopping_list");
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const list = await resp.json();

    // Reset and rebuild local data
    data = {};
    for (const row of list) {
      if (!data[row.category]) data[row.category] = [];
      data[row.category].push({
        name: row.name,
        checked: !!row.checked,
        note: row.note || ""
      });
    }

    // Only render once data is ready
    render();
    console.log("✅ Loaded shopping list from server:", list.length, "items");
  } catch (err) {
    console.error("⚠️ Failed to load shopping list:", err);
    showToast("Could not load shared shopping list", "error");
  }
}


async function saveServerData() {
  const flat = [];
  for (const cat in data) {
    for (const item of data[cat]) {
      flat.push({
        category: cat,
        name: item.name,
        checked: item.checked,
        note: item.note || ""
      });
    }
  }
  await fetch("/api/shopping_list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(flat)
  });
}


// --- DOM refs (one set only) ---
const grid       = document.getElementById("categoryGrid");
const input      = document.getElementById("ingredientInput");
const addBtn     = document.getElementById("addIngredientBtn");
const clearBtn   = document.getElementById("clearAllBtn");
const exportBtn  = document.getElementById("exportBtn");
const clearListBtn = document.getElementById("clearListBtn");
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
  saveServerData();

}

// --- Render ---
function render() {
  // ✅ Debug: show what categories and items are about to be drawn
  console.log("🧱 Rendering:", Object.entries(data).filter(([c, a]) => a.length));

  // Clear the existing grid on screen
  grid.innerHTML = "";

  // Loop through all categories and build their boxes
  for (const cat of DEFAULT_CATEGORIES) {
    const items = data[cat] || [];

    // Create a container for this category
    const div = document.createElement("div");
    div.className = "category" + (items.length === 0 ? " empty" : "");

    // Build the inner HTML for that category
    div.innerHTML = `
      <h3>${cat}</h3>
      <ul>
        ${items.map(i => `
          <li draggable="true">
            <input type="checkbox" ${i.checked ? "checked" : ""}>
            <span>${i.name}</span>
            <input type="text" class="qty-note" value="${i.note || ''}" placeholder="1">
          </li>
        `).join("")}
      </ul>
    `;

    // Add this category box to the page grid
    grid.appendChild(div);
  }

  // Re-attach all button, checkbox, and drag/drop handlers
  attachHandlers();
}


// === Pressing Enter in qty-note confirms entry ===
document.addEventListener("keydown", e => {
  if (e.target.classList.contains("qty-note") && e.key === "Enter") {
    e.preventDefault();         // stop form submission or newline
    e.target.blur();            // ✅ exit edit mode (commits visually)
  }
});

// --- Event handlers (checkbox, dblclick delete, drag/drop) ---
function attachHandlers() {
  // check/uncheck
  document.querySelectorAll(".category input[type='checkbox']").forEach(box => {
    box.onchange = () => {
      const name = box.nextElementSibling.textContent.trim();
      const cat = box.closest(".category").querySelector("h3").textContent;
      const item = data[cat].find(i => i.name === name);
      if (item) item.checked = box.checked;
      saveServerData();

    };
  });

  // double-click delete
  document.querySelectorAll(".category li").forEach(li => {
    li.ondblclick = () => {
      const name = li.querySelector("span").textContent.trim();
      const cat = li.closest(".category").querySelector("h3").textContent;
      data[cat] = data[cat].filter(i => i.name !== name);
      saveServerData();

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
  // Skip categories that don’t exist yet
  if (!data[cat]) continue;

  const idx = data[cat].findIndex(i => i.name === name);
  if (idx !== -1) {
    const [item] = data[cat].splice(idx, 1);

    // Ensure the target category exists
    if (!data[newCat]) data[newCat] = [];

    data[newCat].push(item);
    saveServerData();  // auto-save immediately after drop
    showToast(`↔️ Moved “${name}” to ${newCat}`, "info");
    break;
  }
}


      saveServerData();

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
// Make sure the category exists first
if (!data[cat]) data[cat] = [];

  // ✅ Prevent duplicates
  const exists = data[cat].some(i => i.name === name);
  if (exists) {
    showToast(`ℹ️ “${name}” already in ${cat}.`, "info");
    input.value = "";
    return;
  }

  // Add a fresh item (no qty)
  data[cat].push({ name, checked: true });
  saveServerData();

  learnNewIngredient(name);
  render();
  input.value = "";
};



input.addEventListener("keypress", e => {
  if (e.key === "Enter") { e.preventDefault(); addBtn.click(); }
});

if (clearBtn) {
  clearBtn.onclick = async () => {
    if (!confirm("⚠️ This will clear the entire shopping list for everyone. Continue?"))
      return;

    // Clear only locally first
    data = {};
    DEFAULT_CATEGORIES.forEach(c => (data[c] = []));
    render();

    // Ask for second confirmation before saving
    const confirmSave = confirm("✅ Clear list on server as well?");
    if (confirmSave) {
      await saveServerData();
      showToast("🧹 Shopping list cleared everywhere.", "info");
    } else {
      showToast("🧼 Cleared locally only — server list kept safe.", "warn");
    }
  };
}


// --- Generate / Export shopping list to overlay ---
if (exportBtn) {
  exportBtn.onclick = () => {
    console.log("🟢 Generate List clicked");
    const overlay = document.getElementById("overlay");
    const out = document.getElementById("overlayContent");
    if (!overlay || !out) {
      showToast("Overlay not found.", "error");
      return;
    }

    out.innerHTML = "";
    let any = false;

    for (const cat of DEFAULT_CATEGORIES) {
      const items = data[cat];
      if (!Array.isArray(items) || items.length === 0) continue;

      const header = document.createElement("div");
      header.textContent = cat.toUpperCase() + ":";
      header.style.marginTop = "0.8em";
      header.style.fontWeight = "bold";
      header.style.breakAfter = "avoid-column"; // ✅ keeps category with its items

      out.appendChild(header);

      items.forEach(i => {
        any = true;
        const line = document.createElement("div");
        line.className = "overlay-item";
        line.textContent = `• ${i.name}${i.note ? " (" + i.note + ")" : ""}`;
        line.style.cursor = "pointer";

        if (i.crossed) {
          line.classList.add("crossed");
        }

        line.onclick = () => {
          i.crossed = !i.crossed;
          line.classList.toggle("crossed", i.crossed);
          saveServerData(); // persist cross state
        };

        out.appendChild(line);
      });
    }

    if (!any) {
      out.textContent = "No items in your shopping list.";
      return;
    }

    document.getElementById("overlayTitle").textContent = "🧾 Shopping List";
    document.getElementById("overlayDate").textContent =
      "Generated " + new Date().toLocaleString();

    overlay.hidden = false;
    overlay.scrollTo({ top: 0, behavior: "instant" });
    showToast("🧾 List generated — ready to cross off, copy, or print.", "success");
  };
}

// --- Overlay controls ---
document.getElementById("closeOverlay").onclick = () => {
  document.getElementById("overlay").hidden = true;
};

// --- Copy list (include ✔ for crossed items) ---
// --- Copy list (include category headers and crossed items) ---
document.getElementById("copyBtn").onclick = () => {
  const content = document.getElementById("overlayContent");
  let text = "";
  let currentHeader = "";

  content.childNodes.forEach(node => {
    if (node.nodeType === 1 && node.style.fontWeight === "bold") {
      // It's a category header
      currentHeader = node.textContent.trim();
      text += `\n${currentHeader}\n`;
    } else if (node.classList && node.classList.contains("overlay-item")) {
      // It's an ingredient line
      const lineText = node.textContent.trim();
      if (node.classList.contains("crossed")) {
        text += `✔ ${lineText} (done)\n`;
      } else {
        text += `• ${lineText}\n`;
      }
    }
  });

  navigator.clipboard.writeText(text.trim());
  showToast("📋 List copied with categories!", "success");
};


// --- Print shopping list ---
document.getElementById("printBtn").onclick = () => {
  const overlay = document.getElementById("overlay");

  // ✅ Force layout reflow before printing (prevents blank pages)
  overlay.offsetHeight; // triggers browser to recompute layout

  window.print();
  showToast("🖨️ Print dialog opened", "info");
};



// --- Import from selected recipes (detect checked boxes inside recipe cards) ---
if (importBtn) {
  importBtn.onclick = async () => {
    console.log("🟢 Add to List clicked");

    // Find all checked ingredient boxes within any recipe card
    const checkedBoxes = document.querySelectorAll(
      "#recipesContainer .recipe-card li input[type='checkbox']:checked"
    );
    console.log("✅ Found checked ingredients:", checkedBoxes.length);

    if (checkedBoxes.length === 0) {
      showToast("⚠️ No ingredients checked.", "warn");
      return;
    }

    let added = 0;

    checkedBoxes.forEach(box => {
      // Get the ingredient name (text node next to checkbox)
      const nameNode = box.parentElement;
      if (!nameNode) return;

      const text = nameNode.textContent.trim();
      const clean = cleanIngredient(text);
      if (!clean) return;

      const cat = detectCategory(clean);
      if (!data[cat]) data[cat] = [];

      const exists = data[cat].some(i => i.name === clean);
      if (exists) return;

      // Add as a new item (unchecked by default in list)
      data[cat].push({ name: clean, checked: false });
      added++;
    });

    if (added > 0) {
      await saveServerData();
      render();
      showToast(`✅ Added ${added} ingredients to shopping list.`, "success");
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


// --- Load shared data from the server ---
loadServerData();

// --- Initial render ---
//render();
buildIngredientSuggestions();



// --- Learn new custom ingredients automatically ---
function learnNewIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (!trimmed) return;
  if (!learned[trimmed]) {
    learned[trimmed] = detectCategory(trimmed); // store with detected category
    saveServerData();

    buildIngredientSuggestions(); // refresh autocomplete
  }
}
// === Custom Suggestion Dropdown v2 (live + keyboard) ===
const suggestBox = document.getElementById("suggestBox");
let currentIndex = -1;
let currentSuggestions = [];

// Build live suggestion list from learned + category map + existing data
function getAllSuggestions() {
  const known = new Set();
  Object.values(CATEGORY_MAP).flat().forEach(w => known.add(w.toLowerCase()));
  Object.keys(learned).forEach(k => known.add(k.toLowerCase()));
  Object.values(data).flat().forEach(i => known.add(i.name.toLowerCase()));
  return [...known].sort();
}

function showCustomSuggestions(query) {
  const all = getAllSuggestions();
  // Prioritize words that start with query, then those containing it later
const lowerQ = query.toLowerCase();
const starts = [];
const contains = [];

for (const v of all) {
  if (v.startsWith(lowerQ)) starts.push(v);
  else if (v.includes(lowerQ)) contains.push(v);
}

currentSuggestions = [...starts, ...contains].slice(0, 15);


  if (currentSuggestions.length === 0) {
    suggestBox.hidden = true;
    return;
  }

  suggestBox.innerHTML = currentSuggestions
    .map((v, i) => `<div class="suggest-item" data-index="${i}">${v}</div>`)
    .join("");
  suggestBox.hidden = false;
  currentIndex = -1;

  suggestBox.querySelectorAll(".suggest-item").forEach(div => {
    div.onclick = () => selectSuggestion(parseInt(div.dataset.index));
  });
}

function selectSuggestion(i) {
  const val = currentSuggestions[i];
  if (!val) return;
  input.value = val;
  addBtn.click();           // instantly add item
  input.value = "";         // ✅ clear the text box
  suggestBox.hidden = true;
  currentIndex = -1;
}


// Input typing
input.addEventListener("input", e => {
  const val = input.value.trim();
  if (val.length === 0) {
    suggestBox.hidden = true;
    return;
  }
  showCustomSuggestions(val);
});

// Keyboard navigation
input.addEventListener("keydown", e => {
  const items = suggestBox.querySelectorAll(".suggest-item");

  // --- Arrow key navigation ---
  if (!suggestBox.hidden && items.length > 0) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      currentIndex = (currentIndex + 1) % items.length;
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      currentIndex = (currentIndex - 1 + items.length) % items.length;
    } else if (e.key === "Enter") {
      e.preventDefault();
      // If a suggestion is highlighted
      if (currentIndex >= 0) {
        selectSuggestion(currentIndex);
        return;
      }
      // ✅ Otherwise, check for exact match or just add what’s typed
      const val = input.value.trim().toLowerCase();
      if (!val) return;
      const all = getAllSuggestions();
      if (all.includes(val)) {
        // Add matching known ingredient
        input.value = val;
        addBtn.click();
        input.value = "";
      } else {
        // Add new ingredient
        addBtn.click();
      }
      suggestBox.hidden = true;
      currentIndex = -1;
      return;
    } else if (e.key === "Escape") {
      suggestBox.hidden = true;
      return;
    }

    items.forEach((it, i) => {
      it.classList.toggle("active", i === currentIndex);
      if (i === currentIndex) it.scrollIntoView({ block: "nearest" });
    });
  }

  // --- When list hidden, allow Enter to add typed item normally ---
  if (e.key === "Enter" && (suggestBox.hidden || items.length === 0)) {
    e.preventDefault();
    addBtn.click();
    input.value = "";
  }
});


// Click outside closes box
document.addEventListener("click", e => {
  if (!suggestBox.contains(e.target) && e.target !== input) {
    suggestBox.hidden = true;
  }
});


// --- Forget an ingredient when deleted (double-click) ---
function forgetIngredient(name) {
  const trimmed = name.toLowerCase().trim();
  if (learned[trimmed]) {
    delete learned[trimmed];
    saveServerData();

    buildIngredientSuggestions();
  }
}

// === Clear Shopping List (double-tap confirm) ===
if (clearListBtn) {
  let confirmTimeout;

  clearListBtn.addEventListener("click", () => {
    // First tap: ask for confirmation
    if (!clearListBtn.dataset.confirm) {
      clearListBtn.dataset.confirm = "true";
      clearListBtn.textContent = "Confirm?";
      clearListBtn.style.background = "#d55";
      clearListBtn.style.color = "#fff";

      clearTimeout(confirmTimeout);
      confirmTimeout = setTimeout(() => {
        clearListBtn.dataset.confirm = "";
        clearListBtn.textContent = "Clear";
        clearListBtn.style.background = "";
        clearListBtn.style.color = "";
      }, 2000); // 2 seconds to confirm
      return;
    }

    // Second tap within 2 seconds: clear everything
    clearListBtn.dataset.confirm = "";
    clearListBtn.textContent = "Clear";
    clearListBtn.style.background = "";
    clearListBtn.style.color = "";

    for (const cat in data) data[cat] = [];
    saveServerData();

    render();
    showToast("🧹 Shopping list cleared.", "info");
  });
}
