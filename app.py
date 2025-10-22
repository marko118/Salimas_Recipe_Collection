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

DB_PATH = "recipes.db"
app = Flask(__name__)

# Load spaCy model once
nlp = spacy.load("en_core_web_md")

# ---------------------------
# Database helpers
# ---------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

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

def update_recipe(recipe_id, name, ingredients, method, image_url, tags):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE recipes
            SET name=?, ingredients=?, method=?, image_url=?, tags=?
            WHERE id=?
        """, (name, ingredients, method, image_url, tags, recipe_id))
        conn.commit()

def get_recipe(recipe_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, ingredients, method, image_url, tags FROM recipes WHERE id = ?", (recipe_id,))
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

@app.route("/")
def home():
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


@app.route("/recipes")
def recipe_list():
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
    rid, name, ingredients, method, image_url, tags = row
    ingredients_parsed = (ingredients or "").splitlines()
    return render_template(
        "recipe_detail.html",
        id=rid,
        name=name,
        ingredients=ingredients_parsed,
        raw_ingredients=ingredients or "",
        method=method or "",
        image_url=image_url or "",
        tags=tags or ""
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

    rid, name, ingredients, method, image_url, tags = row
    existing_tags = set((tags or "").split(","))

    # ✅ Load all predefined tags from tags.json
    tags_dict = load_tags_json()
    all_known = set(t for g in tags_dict.values() for t in g)
    custom_only = ",".join(t for t in existing_tags if t and t not in all_known)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        method = request.form.get("method", "").strip()
        image_url = request.form.get("image_url", "").strip()

        # ✅ collect checked predefined tags
        checked = request.form.getlist("tags")
        # ✅ merge with whatever is typed in the Extra box
        extra = request.form.get("extra_tags", "").strip()
        if extra:
            checked.extend([t.strip() for t in extra.split(",") if t.strip()])

        tags = ",".join(checked)
        update_recipe(rid, name, ingredients, method, image_url, tags)
        return redirect(url_for("recipe_detail", recipe_id=rid))

    return render_template(
        "edit.html",
        id=rid,
        name=name,
        ingredients=ingredients or "",
        method=method or "",
        image_url=image_url or "",
        tags=tags or "",
        extra_tags=custom_only,  # ✅ only custom tags
        ingredient_tags=tags_dict.get("Ingredients", []),
        type_tags=tags_dict.get("Type", []),
        other_tags=tags_dict.get("Other", []),
        occasion_tags=tags_dict.get("Occasion", [])
    )





@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete_recipe_route(recipe_id):
    delete_recipe(recipe_id)
    return redirect(url_for("recipe_list"))


@app.route("/search", methods=["GET", "POST"])
def search():
    matches = []
    query = ""
    include_ingredients = False

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        include_ingredients = bool(request.form.get("include_ingredients"))

        if query:
            rows = get_all_recipes()
            for rid, name, ing, method, image_url, tags in rows:
                # Include NAME so title-only searches work; keep tags; optionally add ingredients
                text_to_check = " ".join([(name or ""), (tags or "")]).strip()
                if include_ingredients:
                    text_to_check += " " + (ing or "")
                if query.lower() in text_to_check.lower():
                    matches.append({
                        "id": rid,
                        "name": name,
                        "ingredients": ing or "",
                        "method": method or "",
                        "image_url": image_url or "",
                        "tags": tags or ""
                    })

    return render_template(
        "search.html",
        matches=matches,
        query=query,
        include_ingredients=include_ingredients
    )


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


# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    init_db()  # safe to call every run
    app.run(debug=True)

