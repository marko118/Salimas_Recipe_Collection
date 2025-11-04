#!/bin/bash
# ==========================================
# Smart Cleanup Script for Salima’s Recipes
# Keeps only known active files (moves everything else into archive_unused/)
# ==========================================

set -e

ARCHIVE_DIR="archive_unused"
mkdir -p "$ARCHIVE_DIR/templates"
mkdir -p "$ARCHIVE_DIR/static"
mkdir -p "$ARCHIVE_DIR/root"

echo "🧹 Scanning for unused files..."

# --- define known active templates ---
ACTIVE_TEMPLATES=(
  base.html
  index.html
  add.html
  edit.html
  admin_tags.html
  recipe_detail.html
  planner.html
)

# --- define known static files ---
ACTIVE_STATIC=(
  style.css
  planner.css
  planner.js
  planner_recipes.js
  planner_grid.js
)

# --- define known root files ---
ACTIVE_ROOT=(
  app.py
  recipes_v2.db
  tags.json
  cleanup_auto_archive.sh
)

# === Move unused templates ===
for f in templates/*; do
  fname=$(basename "$f")
  if [[ ! " ${ACTIVE_TEMPLATES[@]} " =~ " ${fname} " ]]; then
    mv "$f" "$ARCHIVE_DIR/templates/" && echo "Archived template: $fname"
  fi
done

# === Move unused static files ===
for f in static/*; do
  fname=$(basename "$f")
  if [[ ! " ${ACTIVE_STATIC[@]} " =~ " ${fname} " ]]; then
    mv "$f" "$ARCHIVE_DIR/static/" && echo "Archived static file: $fname"
  fi
done

# === Move unused root files (Python scripts, backups, misc) ===
for f in *; do
  fname=$(basename "$f")
  if [[ -f "$f" && ! " ${ACTIVE_ROOT[@]} " =~ " ${fname} " && "$fname" != "venv" && "$fname" != "$ARCHIVE_DIR" ]]; then
    mv "$f" "$ARCHIVE_DIR/root/" && echo "Archived root file: $fname"
  fi
done

echo "✅ Cleanup complete."
echo "All unused files moved to: $ARCHIVE_DIR"
echo "Inspect and back up before deleting."
