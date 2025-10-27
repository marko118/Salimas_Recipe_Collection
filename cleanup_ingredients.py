import sqlite3, json, shutil, os

DB_PATH = "recipes.db"

# make an extra timestamped backup for safety
backup_path = DB_PATH.replace(".db", "_cleanup_backup.db")
shutil.copy(DB_PATH, backup_path)
print(f"✅ Backup created at {backup_path}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT id, ingredients FROM recipes")
rows = c.fetchall()

updated = 0

for rid, ing in rows:
    if not ing:
        continue
    ing_text = ing.strip()

    # detect JSON style
    if ing_text.startswith("[") and ing_text.endswith("]"):
        try:
            parsed = json.loads(ing_text)
            if isinstance(parsed, list):
                clean_text = ", ".join(str(i).strip() for i in parsed if str(i).strip())
                c.execute("UPDATE recipes SET ingredients = ? WHERE id = ?", (clean_text, rid))
                updated += 1
        except Exception:
            pass

conn.commit()
conn.close()
print(f"✨ Finished cleanup. {updated} recipes updated.")
