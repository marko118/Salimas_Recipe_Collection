from flask import Flask, render_template, request, redirect, url_for, abort
import sqlite3
from tag_list import INGREDIENT_TAGS, TYPE_TAGS, OTHER_TAGS, OCCASION_TAGS
from pathlib import Path
import re
import spacy

import json
from pathlib import Path

TAGS_PATH = Path(__file__).with_name("tags.json")

def load_tags_json():
    if TAGS_PATH.exists():
        with TAGS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tags_json(data: dict):
    with TAGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

DB_PATH = "recipes_v2.db"
app = Flask(__name__)

# Load spaCy model once
nlp = spacy.load("en_core_web_md")

# ---------------------------
# Database helpers
# ---------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

# === JSON field helpers ===
import json

def parse_json_field(value):
    """Return a Python list from a JSON string, or empty list."""
    if not value:
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []

def to_json(value):
    """Ensure Python lists are safely stored as JSON strings."""
    if isinstance(value, list):
        return json.dumps(value)
    return value or "[]"
def init_db():
    """Create table if missing; ensure 'method' column exists."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ingredients TEXT,
                method TEXT
            )
        """)
        # If DB existed before and lacks 'method', add it
        c.execute("PRAGMA table_info(recipes)")
        cols = [row[1] for row in c.fetchall()]
        if "method" not in cols:
            c.execute("ALTER TABLE recipes ADD COLUMN method TEXT")
        conn.commit()

        if "image_url" not in cols:
            c.execute("ALTER TABLE recipes ADD COLUMN image_url TEXT")

        if "tags" not in cols:
            c.execute("ALTER TABLE recipes ADD COLUMN tags TEXT")

def delete_recipe(recipe_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()


def get_all_recipes():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, ingredients, method, image_url, tags FROM recipes ORDER BY id DESC")
        return c.fetchall()

def update_recipe(recipe_id, name, ingredients, method, image_url, tags, linked_recipe, notes):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE recipes
            SET
                name = ?,
                ingredients = ?,
                method = ?,
                image_url = ?,
                tags = ?,
                linked_recipe = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name, ingredients, method, image_url, tags, linked_recipe, notes, recipe_id))
        conn.commit()




def get_recipe(recipe_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, name, ingredients, method, tags,
                   category, source, linked_recipe, image_url, notes,
                   created_at, updated_at
            FROM recipes
            WHERE id = ?
        """, (recipe_id,))
        row = c.fetchone()
        return row



def add_recipe_to_db(name, ingredients, method, image_url, tags):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO recipes (name, ingredients, method, image_url, tags) VALUES (?, ?, ?, ?, ?)",
            (name, ingredients, method, image_url, tags),
        )
        conn.commit()

# ---------------------------
# Ingredient parsing helpers
# ---------------------------
FRACTION_MAP = {
    "½": "1/2", "¼": "1/4", "¾": "3/4",
    "⅓": "1/3", "⅔": "2/3",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}

UNITS = {
    "g","kg","mg","ml","l","tbsp","tsp","cup","cups","oz","fl oz","lb","lbs","pound","pounds",
    "clove","cloves","slice","slices","can","cans","tin","tins","pack","packs"
}

def _normalize_fractions(s: str) -> str:
    for sym, ascii_frac in FRACTION_MAP.items():
        s = s.replace(sym, ascii_frac)
    return s

def parse_ingredient_line(line: str):
    """
    Parse lines like:
      '200 g penne'
      '1 1/2 cups milk'
      '2 cloves garlic, crushed'
      'penne'          (no amount)
    Returns dict: {amount, unit, item, note}
    """
    original = line.strip()
    if not original:
        return None
    s = _normalize_fractions(original)

    # Try to capture amount (number or fraction), optional unit, then item
    # amount can be: 200 | 1/2 | 1 1/2 | 0.5
    m = re.match(
        r"""^\s*
        (?P<amount>(\d+(?:\.\d+)?)|(\d+\s+\d+/\d+)|(\d+/\d+))?
        \s*
        (?P<unit>[a-zA-Z]+(?:\s*oz)?)?
        \s*
        (?P<rest>.+?)
        \s*$""",
        s, re.VERBOSE
    )

    amount = unit = item = note = ""

    if m:
        amount = (m.group("amount") or "").strip()
        unit = (m.group("unit") or "").strip().lower()
        rest = (m.group("rest") or "").strip()
        # If unit isn't a known unit and we have an amount, maybe unit actually part of item
        if unit and unit not in UNITS and amount:
            rest = (unit + " " + rest).strip()
            unit = ""
        # Split item vs note on comma
        parts = [p.strip() for p in rest.split(",", 1)]
        item = parts[0]
        if len(parts) == 2:
            note = parts[1]
    else:
        item = original  # fallback

    return {"amount": amount, "unit": unit, "item": item, "note": note}

def parse_ingredients_block(block: str):
    """Split on newlines, parse each non-empty line."""
    lines = (block or "").splitlines()
    parsed = []
    for ln in lines:
        p = parse_ingredient_line(ln)
        if p:
            parsed.append(p)
    return parsed

# ---------------------------
# Search helpers
# ---------------------------
# ---------------------------
# Search helpers  (REPLACEMENT)
# ---------------------------
import re

def recipe_score(query: str, name: str, ingredients: str, method: str) -> float:
    """
    Semantic similarity between query and combined recipe text (0..1).
    Includes the recipe *name* so title-only searches score correctly.
    """
    # Defensive: allow running without spaCy loaded or on very small devices
    try:
        q_doc = nlp(query)
        t_doc = nlp(" ".join([name or "", ingredients or "", method or ""]))
        return q_doc.similarity(t_doc)
    except Exception:
        # If NLP isn't available, fall back to a simple lexical score (0/1)
        return 1.0 if lexical_hit(query, name, ingredients, method) else 0.0


def _normalize(s: str) -> str:
    """Lowercase, keep letters/numbers, collapse whitespace."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _tokenize(s: str) -> list[str]:
    """Normalized word list for prefix/substring checks."""
    t = _normalize(s)
    return t.split() if t else []


def lexical_hit(query: str, name: str, ingredients: str, method: str) -> bool:
    """
    Lexical fallback with better partial matching.
    - Prefix matches: 'pas' -> 'pasta', 'passata', 'pastry'
    - Substring matches anywhere in the combined text
    - Singular-ish fallbacks: 'beans' -> 'bean'
    - Lemma overlap (spaCy), if available
    Searches the combined text of NAME + INGREDIENTS + METHOD.
    """
    q = _normalize(query)
    text = " ".join([_normalize(name), _normalize(ingredients), _normalize(method)]).strip()

    if not q or not text:
        return False

    # 1) Prefix match against tokenized words (fast, very forgiving)
    words = text.split()
    if any(w.startswith(q) for w in words):
        return True

    # 2) Substring anywhere
    if q in text:
        return True

    # 3) Simple singular-ish fallbacks
    if q.endswith("s") and q[:-1] in text:
        return True
    if q.endswith("'s") and q[:-2] in text:
        return True

    # 4) Lemma overlap if spaCy is available (ignore failures gracefully)
    try:
        q_lemmas = {t.lemma_.lower() for t in nlp(query) if t.is_alpha}
        t_lemmas = {t.lemma_.lower() for t in nlp(text) if t.is_alpha}
        if q_lemmas and t_lemmas and any(l in t_lemmas for l in q_lemmas):
            return True
    except Exception:
        pass

    return False

# ---------------------------
# Routes
# ---------------------------

@app.route("/recipes")
def recipe_list_home():
    rows = get_all_recipes()
    recipes = [
        {
            "id": r[0],
            "name": r[1],
            "ingredients": r[2] or "",
            "method": r[3] or "",
            "image_url": r[4] or "",
            "tags": r[5] or ""
        }
        for r in rows
    ]
    return render_template("recipes.html", recipes=recipes)





@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    row = get_recipe(recipe_id)
    if not row:
        abort(404)

    (
        rid, name, ingredients, method, tags,
        category, source, linked_recipe, image_url, notes,
        created_at, updated_at
    ) = row

    import json
    try:
        if ingredients and ingredients.strip().startswith("["):
            ingredients_parsed = json.loads(ingredients)
            if isinstance(ingredients_parsed, str):
                ingredients_parsed = json.loads(ingredients_parsed)
        else:
            text = (ingredients or "").replace(",", "\n")
            ingredients_parsed = [i.strip() for i in text.splitlines() if i.strip()]
    except Exception:
        text = (ingredients or "").replace(",", "\n").replace("[", "").replace("]", "").replace('"', "")
        ingredients_parsed = [i.strip() for i in text.splitlines() if i.strip()]

    return render_template(
        "recipe_detail.html",
        id=rid,
        name=name,
        ingredients=ingredients_parsed,
        raw_ingredients=ingredients or "",
        method=method or "",
        image_url=image_url or "",
        tags=tags or "",
        linked_recipe=linked_recipe or "",
        notes=notes or ""
    )




@app.route("/add", methods=["GET", "POST"])
def add_recipe():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        method = request.form.get("method", "").strip()
        image_url = request.form.get("image_url", "").strip()
        # gather tags from checkboxes + free text
        chosen = request.form.getlist("tags")
        extras = request.form.get("extra_tags", "").strip()
        if extras:
            chosen.extend([t.strip() for t in extras.split(",") if t.strip()])
        tags = ",".join(chosen)

        if name:
            add_recipe_to_db(name, ingredients, method, image_url, tags)
            return redirect(url_for("recipe_list"))

    # ✅ This part runs when we need to show the form (GET request)
    tags_dict = load_tags_json()   # read your new tags.json file
    return render_template(
        "add.html",
        ingredient_tags=tags_dict.get("Ingredients", []),
        type_tags=tags_dict.get("Type", []),
        other_tags=tags_dict.get("Other", []),
        occasion_tags=tags_dict.get("Occasion", [])
    )


@app.route("/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    row = get_recipe(recipe_id)
    if not row:
        abort(404)

    # Unpack all fields (in your DB order)
    (
        rid, name, ingredients, method, tags,
        category, source, linked_recipe, image_url,
        notes, created_at, updated_at
    ) = row

    # --- Handle save (POST) ---
    if request.method == "POST":
        name = request.form["name"]
        ingredients = request.form["ingredients"]
        method = request.form["method"]
        image_url = request.form.get("image_url", "")
        tags = ",".join(request.form.getlist("tags"))
        linked_recipe = request.form.get("linked_recipe", "")
        notes = request.form.get("notes", "")

        update_recipe(
            recipe_id,
            name,
            ingredients,
            method,
            image_url,
            tags,
            linked_recipe,
            notes
        )
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    # --- When page is loaded normally (GET) ---
    existing_tags = set((tags or "").split(","))
    return render_template(
        "edit.html",
        id=rid,
        name=name,
        ingredients=ingredients or "",
        method=method or "",
        image_url=image_url or "",
        tags=tags or "",
        linked_recipe=linked_recipe or "",
        notes=notes or "",
        ingredient_tags=INGREDIENT_TAGS,
        type_tags=TYPE_TAGS,
        other_tags=OTHER_TAGS,
        occasion_tags=OCCASION_TAGS
    )




@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete_recipe_route(recipe_id):
    delete_recipe(recipe_id)
    return redirect(url_for("recipe_list"))



@app.route("/admin/tags", methods=["GET", "POST"])
def admin_tags():
    tags_dict = load_tags_json()

    if request.method == "POST":
        new_data = {}
        # Each group will come back as a textarea named like group_Ingredients
        for key, val in request.form.items():
            if key.startswith("group_"):
                group_name = key[len("group_"):]
                # Split on newlines or commas, strip whitespace
                items = [t.strip() for t in val.replace(",", "\n").splitlines() if t.strip()]
                # Remove duplicates while preserving order
                new_data[group_name] = list(dict.fromkeys(items))

        # Save the updated groups back to JSON
        save_tags_json(new_data)
        return redirect(url_for("admin_tags"))

    # GET request: show current groups
    return render_template("admin_tags.html", tags_dict=tags_dict)

@app.route("/")
def index():
    with get_conn() as conn:
        c = conn.cursor()
        default_tag = "chicken"
        # show recipes tagged 'chicken' by default
        c.execute("SELECT id, name, ingredients FROM recipes WHERE tags LIKE ?", (f'%{default_tag}%',))
        recipes = c.fetchall()
        # load all tags for the tag cloud
        c.execute("SELECT DISTINCT name FROM tags ORDER BY name")
        all_tags = [row[0] for row in c.fetchall()]
    return render_template("index.html", recipes=recipes, all_tags=all_tags, default_tag=default_tag)
@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    results = []

    with get_conn() as conn:
        c = conn.cursor()
        # Decide what to filter by
        if q:
            c.execute("""
                SELECT id, name, ingredients, tags
                FROM recipes
                WHERE name LIKE ? OR ingredients LIKE ? OR tags LIKE ?
                ORDER BY name
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        elif tag:
            c.execute("""
                SELECT id, name, ingredients, tags
                FROM recipes
                WHERE tags LIKE ?
                ORDER BY name
            """, (f"%{tag}%",))
        else:
            c.execute("SELECT id, name, ingredients, tags FROM recipes ORDER BY name")
        results = c.fetchall()

        # For the tag cloud on search pages
        c.execute("SELECT DISTINCT name FROM tags ORDER BY name")
        all_tags = [row[0] for row in c.fetchall()]

    return render_template(
        "index.html",
        recipes=results,
        all_tags=all_tags,
        default_tag=tag or q or "Results"
    )

@app.route("/planner")
def planner():
    # Just render the notebook layout; meals are loaded dynamically from localStorage
    return render_template("planner_notebook.html")


@app.route("/api/selected")
def api_selected():
    import json
    ids = request.args.get("ids", "")
    if not ids:
        return {"meals": []}
    id_list = [i for i in ids.split(",") if i.isdigit()]
    if not id_list:
        return {"meals": []}

    with get_conn() as conn:
        c = conn.cursor()
        q = f"SELECT id, name, ingredients FROM recipes WHERE id IN ({','.join(['?'] * len(id_list))})"
        c.execute(q, id_list)
        rows = c.fetchall()

    meals = []
    for rid, name, ing_text in rows:
        try:
            # Try to interpret proper JSON first
            if ing_text and ing_text.strip().startswith("["):
                ingredients = json.loads(ing_text)
                if isinstance(ingredients, str):  # handle double-encoded JSON
                    ingredients = json.loads(ingredients)
            else:
                # Treat commas and newlines as separators
                text = (ing_text or "").replace(",", "\n")
                ingredients = [i.strip() for i in text.splitlines() if i.strip()]
        except Exception:
            # Fallback cleanup if JSON or text is malformed
            text = (ing_text or "").replace(",", "\n").replace("[", "").replace("]", "").replace('"', "")
            ingredients = [i.strip() for i in text.splitlines() if i.strip()]

        # Ensure list of strings, even if JSON was nested
        if isinstance(ingredients, list):
            ingredients = [str(i).strip() for i in ingredients]
        else:
            ingredients = [str(ingredients).strip()]

        meals.append({
            "id": rid,
            "name": name,
            "url": url_for("recipe_detail", recipe_id=rid),
            "ingredients": ingredients
        })

    return {"meals": meals}




# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    init_db()  # safe to call every run
    app.run(debug=True)

