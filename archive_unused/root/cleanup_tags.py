import sqlite3, shutil

DB_PATH = "recipes.db"

# Backup for safety
backup_path = DB_PATH.replace(".db", "_tag_backup.db")
shutil.copy(DB_PATH, backup_path)
print(f"✅ Backup created at {backup_path}")

# --- Normalization rules ---
# Key = plural or variant, Value = canonical form
NORMALIZE = {
    "salads": "salad",
    "pastas": "pasta",
    "soups": "soup",
    "curries": "curry",
    "stews": "stew",
    "wraps": "wrap",
    "pies": "pie",
    "sandwiches": "sandwich",
    "pizzas": "pizza",
    "cookies": "cookie",
    "cakes": "cake",
    "smoothies": "smoothie",
}

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT id, tags FROM recipes")
rows = c.fetchall()

updated = 0

for rid, tag_text in rows:
    if not tag_text:
        continue

    tags = [t.strip().lower() for t in tag_text.split(",") if t.strip()]
    cleaned = []
    for t in tags:
        t = NORMALIZE.get(t, t)  # normalize plural to singular
        if t not in cleaned:
            cleaned.append(t)

    new_tag_str = ",".join(cleaned)
    if new_tag_str != tag_text:
        c.execute("UPDATE recipes SET tags = ? WHERE id = ?", (new_tag_str, rid))
        updated += 1

conn.commit()
conn.close()

print(f"✨ Finished tag cleanup. {updated} recipes updated.")
