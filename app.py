from flask import Flask, render_template, request, redirect, url_for, abort
import sqlite3
from tag_list import INGREDIENT_TAGS, TYPE_TAGS, OTHER_TAGS, OCCASION_TAGS
from pathlib import Path
import re
import spacy
from flask import jsonify, request, g
import sqlite3
import json
from datetime import datetime


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

from flask import g
import sqlite3

DATABASE = "recipes_v2.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


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

        # === Ensure shopping_list table exists ===
        c.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                amount TEXT,
                checked INTEGER DEFAULT 1,
                crossed INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()   # ✅ Make sure this runs after the new table creation



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

from collections import Counter
import json
import re

from collections import Counter
import json
import re

def get_tag_cloud():
    """Return a dict of {tag: count} for all recipes, cleaned and normalized."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT tags FROM recipes")
        rows = c.fetchall()

    all_tags = []

    # Common normalizations / synonyms
    normalize_map = {
        "soups": "soup",
        "salads": "salad",
        "fish & seafood": "seafood",
        "seafood & fish": "seafood",
        "pasta dishes": "pasta",
        "curries": "curry",
        "desserts": "dessert",
        "cakes": "cake",
        "cookies": "cookie",
        "breads": "bread",
    }

    for row in rows:
        raw = row[0]
        if not raw:
            continue

        tags = []

        # --- Try JSON decode first ---
        if raw.strip().startswith("["):
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, list):
                    tags = decoded
                elif isinstance(decoded, str):
                    tags = [decoded]
            except Exception:
                cleaned = raw.strip("[]'\" ")
                tags = re.split(r"[,;]", cleaned)
        else:
            tags = re.split(r"[,;]", raw)

        # --- Normalize ---
        cleaned_tags = []
        for t in tags:
            t = re.sub(r'[^a-zA-Z0-9 &-]', '', t).strip().lower()
            if not t:
                continue
            # singularize simple plurals (quick heuristic)
            if t.endswith("s") and len(t) > 3:
                t = t[:-1]
            # apply synonym map
            if t in normalize_map:
                t = normalize_map[t]
            cleaned_tags.append(t)

        all_tags.extend(cleaned_tags)

    counts = Counter(all_tags)
    return sorted(counts.items(), key=lambda x: x[0])


# ---------------------------
# Routes
# ---------------------------

@app.route("/recipes")
def recipe_list_home():
    # === Load recipes from the database ===
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

    # === Load Quick Access tags from tags.json ===
    from pathlib import Path
    import json

    tags_path = Path("tags.json")
    quick_access = []
    all_tags = []

    if tags_path.exists():
        try:
            tags_data = json.loads(tags_path.read_text(encoding="utf-8"))
            quick_access = tags_data.get("Quick Access", [])
            # combine all tag groups for tag cloud, if you use it
            for group_tags in tags_data.values():
                if isinstance(group_tags, list):
                    all_tags.extend(group_tags)
        except Exception as e:
            print("⚠️ Error loading tags.json:", e)
    else:
        quick_access = ["Favourites", "Easy Lunch"]

    # === Render the page ===
    return render_template(
        "recipes.html",
        recipes=recipes,
        quick_access=quick_access,
        all_tags=sorted(set(all_tags))
    )






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
            return redirect(url_for("index"))


    # ✅ This part runs when we need to show the form (GET request)
    tags_dict = load_tags_json()
    return render_template(
    "add.html",
    tags_dict=tags_dict
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
        return redirect(url_for("recipe_detail", recipe_id=recipe_id, saved="1"))

    # --- When page is loaded normally (GET) ---
    tags_dict = load_tags_json()  # load all groups from tags.json dynamically

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
    tags_dict=tags_dict
)





@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete_recipe_route(recipe_id):
    delete_recipe(recipe_id)
    return redirect(url_for("index"))



@app.route("/admin/tags", methods=["GET", "POST"])
def admin_tags():
    tags_dict = load_tags_json()

    if request.method == "POST":
        new_data = {}

        # Each group is a textarea like group_Ingredients, group_Quick_Access, etc.
        for key, val in request.form.items():
            if key.startswith("group_"):
                group_name = key[len("group_"):].replace("_", " ")
                items = [t.strip() for t in val.replace(",", "\n").splitlines() if t.strip()]
                new_data[group_name] = list(dict.fromkeys(items))

        # ✅ Handle creation of an entirely new tag group
        new_group = request.form.get("new_group_name", "").strip()
        if new_group and new_group not in new_data:
            new_data[new_group] = []

        save_tags_json(new_data)
        return redirect(url_for("admin_tags"))

    # --- GET: display all existing groups ---
    return render_template("admin_tags.html", tags_dict=tags_dict)


@app.route("/")
def index():
    with get_conn() as conn:
        c = conn.cursor()
        default_tag = "chicken"
        # Show all recipes, newest first
        c.execute("SELECT id, name, ingredients FROM recipes ORDER BY id DESC")
        recipes = c.fetchall()

        # Load tag counts for the tag cloud
        tag_cloud = get_tag_cloud()

    # ✅ Load Quick Access tags from tags.json
    from pathlib import Path
    import json

    tags_path = Path("tags.json")
    quick_access = []

    if tags_path.exists():
        try:
            tags_data = json.loads(tags_path.read_text(encoding="utf-8"))
            quick_access = tags_data.get("Quick Access", [])
        except Exception as e:
            print("⚠️ Error loading tags.json:", e)

    return render_template(
        "index.html",
        recipes=recipes,
        tag_cloud=tag_cloud,
        default_tag=default_tag,
        quick_access=quick_access
    )


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
        tag_cloud = get_tag_cloud()

    return render_template(
        "index.html",
        recipes=results,
        tag_cloud=tag_cloud,
        default_tag=tag or q or "Results"
    )


@app.route("/planner")
def planner():
    return render_template("planner.html")






@app.route("/api/selected")
def api_selected():
    """Return recipe info + ingredients for given IDs (used by planner_v3)."""
    import json

    ids = request.args.get("ids", "")
    if not ids:
        return {"meals": []}

    id_list = [i for i in ids.split(",") if i.isdigit()]
    if not id_list:
        return {"meals": []}

    with get_conn() as conn:
        c = conn.cursor()
        q = f"SELECT id, name, ingredients, linked_recipe FROM recipes WHERE id IN ({','.join(['?'] * len(id_list))})"
        c.execute(q, id_list)
        rows = c.fetchall()

    meals = []
    for rid, name, ing_text, linked_recipe in rows:
        try:
            if ing_text and ing_text.strip().startswith("["):
                ingredients = json.loads(ing_text)
                if isinstance(ingredients, str):
                    ingredients = json.loads(ingredients)
            else:
                text = (ing_text or "").replace(",", "\n")
                ingredients = [i.strip() for i in text.splitlines() if i.strip()]
        except Exception:
            text = (ing_text or "").replace(",", "\n").replace("[", "").replace("]", "").replace('"', "")
            ingredients = [i.strip() for i in text.splitlines() if i.strip()]

        if isinstance(ingredients, list):
            ingredients = [str(i).strip() for i in ingredients]
        else:
            ingredients = [str(ingredients).strip()]

        # ✅ Prefer external link if available
        if linked_recipe and linked_recipe.startswith("http"):
            recipe_url = linked_recipe
        else:
            recipe_url = url_for("recipe_detail", recipe_id=rid)

        meals.append({
            "id": rid,
            "name": name,
            "url": recipe_url,
            "ingredients": ingredients
        })

    return {"meals": meals}

# === Shared Shopping List API ===

@app.route("/api/shopping_list", methods=["GET"])
def api_get_shopping_list():
    rows = query_db(
        "SELECT category, name, checked, note FROM shopping_list ORDER BY category, name;"
    )
    return jsonify([dict(r) for r in rows])

@app.route("/api/shopping_list", methods=["POST"])
def api_save_shopping_list():
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "Invalid data"}), 400

    if not data:
        return jsonify({"error": "Empty list received; nothing saved."}), 400

    db = get_db()

    # ✅ Instead of deleting everything, replace items in-place
    for item in data:
        db.execute(
    """
    INSERT INTO shopping_list (category, name, checked, note)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(category, name) DO UPDATE SET
      checked = excluded.checked,
      note = excluded.note;
    """,
    (
        item.get("category", ""),
        item.get("name", ""),
        int(item.get("checked", False)),
        item.get("note", ""),
    ),
)


    db.commit()
    return jsonify({"ok": True})



# === Shared Meal Plan API ===

@app.route("/api/meal_plan", methods=["GET"])
def api_get_meal_plan():
    rows = query_db("SELECT slot, recipe, link FROM meal_plan ORDER BY slot;")
    return jsonify([dict(r) for r in rows])

@app.route("/api/meal_plan", methods=["POST"])
def api_save_meal_plan():
    data = request.get_json(force=True)
    if not isinstance(data, list):
        return jsonify({"error": "Invalid data"}), 400

    db = get_db()
    db.execute("DELETE FROM meal_plan;")
    for slot in data:
        db.execute(
            "INSERT INTO meal_plan (slot, recipe, link, updated) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (
                slot.get("slot", ""),
                slot.get("recipe", ""),
                slot.get("link", ""),
            ),
        )
    db.commit()
    return jsonify({"ok": True})

# === DAKboard-compatible Meal Plan Feed ===
@app.route("/feed/mealplan")
def feed_mealplan():
    rows = query_db("SELECT slot, recipe FROM meal_plan ORDER BY slot;")
    if not rows:
        return "No meal plan found.", 200, {"Content-Type": "text/plain; charset=utf-8"}

    lines = []
    for r in rows:
        # slot looks like "sun_dinner" → turn into "Sun Dinner"
        parts = r["slot"].split("_", 1)
        if len(parts) == 2:
            day, meal = parts
            lines.append(f"{day.title()} {meal.title()}: {r['recipe']}")
        else:
            lines.append(f"{r['slot'].title()}: {r['recipe']}")

    text_output = "\n".join(lines)
    return text_output, 200, {"Content-Type": "text/plain; charset=utf-8"}

# ---------------------------
# Shopping List API
# ---------------------------

from flask import jsonify

@app.route("/api/shopping_list", methods=["GET"])
def api_shopping_list_get():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, name, category, amount, checked, crossed, active
            FROM shopping_list
            WHERE active = 1
            ORDER BY category, name
        """)
        rows = c.fetchall()
    items = [
        {
            "id": r[0],
            "name": r[1],
            "category": r[2] or "",
            "amount": r[3] or "",
            "checked": bool(r[4]),
            "crossed": bool(r[5]),
            "active": bool(r[6]),
        }
        for r in rows
    ]
    return jsonify(items)


@app.route("/api/shopping_list", methods=["POST"])
def api_shopping_list_post():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing name"}), 400

    category = data.get("category")
    amount = data.get("amount", "")
    checked = int(bool(data.get("checked", True)))
    crossed = int(bool(data.get("crossed", False)))
    active = 1

    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO shopping_list (name, category, amount, checked, crossed, active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, category, amount, checked, crossed, active))
        conn.commit()
        new_id = c.lastrowid

    return jsonify({"id": new_id, "name": name, "category": category})


@app.route("/api/shopping_list/<int:item_id>", methods=["PATCH"])
def api_shopping_list_patch(item_id):
    data = request.get_json(force=True)
    allowed_fields = ["name", "category", "amount", "checked", "crossed", "active"]
    sets, values = [], []

    for field in allowed_fields:
        if field in data:
            sets.append(f"{field} = ?")
            values.append(data[field])
    if not sets:
        return jsonify({"error": "No valid fields"}), 400

    values.append(item_id)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE shopping_list SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id = ?", values)
        conn.commit()

    return jsonify({"status": "updated"})


@app.route("/api/shopping_list/<int:item_id>", methods=["DELETE"])
def api_shopping_list_delete(item_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM shopping_list WHERE id = ?", (item_id,))
        conn.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/shopping_list/clear", methods=["POST"])
def api_shopping_list_clear():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE shopping_list SET active = 0, updated_at = CURRENT_TIMESTAMP")
        conn.commit()
    return jsonify({"status": "cleared"})


# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050, host="127.0.0.1")


