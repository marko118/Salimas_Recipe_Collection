import sqlite3, re

db_path = "recipes_v2.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

url_pattern = re.compile(r'https?://[^\s)]+', re.IGNORECASE)

moved, kept, extracted = 0, 0, 0

cur.execute("SELECT id, name, linked_recipe, source, notes FROM recipes WHERE linked_recipe != '' OR source != ''")
rows = cur.fetchall()

def extract_url(text):
    """Return the first URL found, or None."""
    if not text:
        return None
    m = url_pattern.search(text)
    return m.group(0) if m else None

for rid, name, linked, source, notes in rows:
    new_link = ""
    new_notes = notes or ""

    # --- Linked recipe field ---
    if linked:
        url = extract_url(linked)
        if url:
            new_link = url
            new_notes = (new_notes + "\n" + linked).strip()
            extracted += 1
        else:
            new_notes = (new_notes + "\n" + linked).strip()
            moved += 1

    # --- Source field ---
    if source:
        url = extract_url(source)
        if url:
            if not new_link:
                new_link = url
            new_notes = (new_notes + "\n" + source).strip()
            extracted += 1
        else:
            new_notes = (new_notes + "\n" + source).strip()
            moved += 1

    cur.execute("""
        UPDATE recipes
        SET linked_recipe = ?, notes = ?, source = ''
        WHERE id = ?
    """, (new_link.strip(), new_notes.strip(), rid))

    if new_link:
        kept += 1

conn.commit()

print(f"✅ Cleanup complete — {extracted} URLs extracted, {moved} moved to notes, {kept} total records updated.")
print("\n🔍 Sample check:")
for row in conn.execute("""
    SELECT id, name, linked_recipe, notes
    FROM recipes
    WHERE linked_recipe != '' OR notes LIKE '%http%'
    LIMIT 5
"""):
    print(row)

conn.close()
