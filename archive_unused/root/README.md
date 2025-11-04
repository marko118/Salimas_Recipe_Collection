# 🍲 Salima’s Recipe Collection (V2) ish still not stable as of 281025


A family-friendly recipe and meal-planning web app built with **Flask**, hosted on a Raspberry Pi, and now integrated with:
- OCR meal plan importer
- Smart tag search and categorization
- Editable recipes with notes, image links, and source URLs

---

## 🧰 Features
- View, search, and filter recipes by tags (ingredients, type, occasion, etc.)
- Select meals for the week and view total count
- Edit or delete recipes via the admin pages
- OCR integration to import handwritten meal plans
- Hosted on Raspberry Pi with Cloudflare tunnel access

---

## 🚀 Running Locally

### 1. Clone the repo
```bash
git clone https://github.com/marko118/Salimas_Recipe_Collection.git
cd Salimas_Recipe_Collection
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port=5050
Salimas_Recipe_Collection/
│
├── app.py                  # Main Flask app
├── recipes_v2.db           # SQLite database
├── static/
│   └── style.css           # Shared styling
├── templates/
│   ├── base.html           # Header/footer layout
│   ├── index.html          # Home page
│   ├── recipe_detail.html  # Individual recipe page
│   ├── edit.html           # Recipe editor
│   └── search.html         # Search results
└── README.md               # This file
Future Development Ideas

Integrate DakBoard meal plan display

Add category filters (e.g., breakfast/lunch/dinner)

OCR import automation from scanned notebooks

Export selected meals to shopping list

Backup to Google Drive or GitHub Actions

Built with ❤️ by Mark and Salima


---

## 🗂️ **2. Requirements file (dependencies list)**
Create a text file called `requirements.txt` in your project root:
```bash
Flask
spacy
pip freeze > requirements.txt
🧩 3. Version tagging / changelog

When you hit big milestones (like the new integrated version), you can tag it:

git tag -a v2.0 -m "Integrated meal planner and recipe site"
git push origin v2.0


Then “future you” can always roll back or compare versions.

🧱 4. Notes for Raspberry Pi deployment

Keep a separate file called DEPLOY_PI.md or similar with setup steps:

how to activate venv

how to start Flask on boot

Cloudflare tunnel info

backup paths


# 🧱 Deployment Guide — Salima’s Recipe Collection (Raspberry Pi)

This document explains how to run the **Flask meal planner + recipe site** on your Raspberry Pi (with Cloudflare tunnel).

---

## 📍 System Overview

**Hostname:** `recipepi`  
**OS:** Raspberry Pi OS (SSD boot)  
**App path:** `/home/admin/Salimas_Recipe_Collection-main`  
**Web access:** via Cloudflare Tunnel  
**Local URL:** http://127.0.0.1:5050  
**Public URL:** (Cloudflare tunnel link)

---

## 🪴 1. Initial Setup (first time only)

### Install dependencies
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
cd ~
git clone https://github.com/marko118/Salimas_Recipe_Collection.git
cd Salimas_Recipe_Collection
🧰 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate


To deactivate later:

deactivate

📦 3. Install requirements
pip install -r requirements.txt


If requirements.txt doesn’t exist yet, install manually:

pip install flask spacy
python3 -m spacy download en_core_web_md
🚀 4. Run the app manually (for testing)
flask run --port=5050 --host=0.0.0.0


Then visit:

Local: http://<pi_ip>:5050

Remote: your Cloudflare tunnel URL

🔁 5. Run Flask automatically on boot
Create a systemd service file:
sudo nano /etc/systemd/system/recipeapp.service


Paste this:

[Unit]
Description=Flask Recipe Web App
After=network.target

[Service]
User=admin
WorkingDirectory=/home/admin/Salimas_Recipe_Collection-main
Environment="PATH=/home/admin/Salimas_Recipe_Collection-main/venv/bin"
ExecStart=/home/admin/Salimas_Recipe_Collection-main/venv/bin/flask run --port=5050 --host=0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target


Save (Ctrl+O, Ctrl+X), then enable and start:
sudo systemctl daemon-reload
sudo systemctl enable recipeapp
sudo systemctl start recipeapp
Check status:

bash
Copy code
sudo systemctl status recipeapp
Logs:

bash
Copy code
journalctl -u recipeapp -n 20
☁️ 6. Cloudflare Tunnel
If you haven’t already:

bash
Copy code
cloudflared service install
To point your tunnel to this app:

bash
Copy code
sudo nano /etc/cloudflared/config.yml
Example:

yaml
Copy code
tunnel: recipepi
credentials-file: /etc/cloudflared/<tunnel_id>.json

ingress:
  - hostname: recipes.example.com
    service: http://localhost:5050
  - service: http_status:404
Restart tunnel:

bash
Copy code
sudo systemctl restart cloudflared
🧠 7. Updating from GitHub
To pull latest changes:

bash
Copy code
cd ~/Salimas_Recipe_Collection-main
git pull
sudo systemctl restart recipeapp
If you edited live and want to back up first:

bash
Copy code
git add .
git commit -m "Backup local changes before pull"
git pull --rebase
💾 8. Backups (recommended)
Regularly copy your database:

bash
Copy code
cp ~/Salimas_Recipe_Collection-main/recipes_v2.db ~/backups/recipes_$(date +%F).db
You can automate that weekly with cron.

✅ Quick Status Check Commands
Purpose	Command
Check service status	sudo systemctl status recipeapp
Restart service	sudo systemctl restart recipeapp
View last 20 log lines	journalctl -u recipeapp -n 20
View local web app	http://127.0.0.1:5050
Cloudflare logs	sudo journalctl -u cloudflared -n 20

🧩 9. Optional Extras
Daily GitHub sync:
Add a cron entry to auto-push changes:

bash
Copy code
0 3 * * * cd ~/Salimas_Recipe_Collection-main && git add . && git commit -m "Auto backup $(date +\%F)" && git push
OCR imports:
To use the “meal plan extractor” tools later, install:

bash
Copy code
pip install pillow pytesseract
sudo apt install tesseract-ocr
🧾 Notes
Your database file recipes_v2.db holds all user-added recipes, notes, and URLs.

Everything else (templates, style, Python logic) is synced from GitHub.

The Pi’s SSD stores the full working copy; GitHub acts as remote backup and version history.

Author: Mark Richards
Last updated: October 2025

yaml
Copy code

---

Would you like me to add a short **“remote development setup”** section at the bottom — i.e., how to clone it on your work computer and push changes back to the Pi when you’re home?

---

## 💻 10. Remote Development Setup (Working Away From Home)

You can safely work on this project from any other computer (e.g., laptop or work Mac)
without breaking the Pi’s live copy.  
Here’s how to set that up and sync both directions.

---

### 🧩 Clone the GitHub copy

On your other computer:
```bash
git clone https://github.com/marko118/Salimas_Recipe_Collection.git
cd Salimas_Recipe_Collection

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port=5050
🧭 Making changes

Edit any files in templates/, static/, or app.py

Test locally if needed

Commit and push when ready:
git add .
git commit -m "Updated recipe layout / styling"
git push origin main
🔁 Syncing updates back to the Pi

When you’re home or connected to the Pi (via SSH):

cd ~/Salimas_Recipe_Collection-main
git pull
sudo systemctl restart recipeapp

🧱 Safety tip

Never edit files directly on the Pi and on your laptop at the same time
— always push from one, then pull from the other.

If you forget and Git complains about conflicts:

git stash
git pull
git stash pop

🧰 Optional: Sync database changes

Your recipes_v2.db file is local to each system.
If you edit recipes or add notes on the Pi, the database there is the “truth.”

To back it up to GitHub manually:

cd ~/Salimas_Recipe_Collection-main
git add recipes_v2.db
git commit -m "Backup updated database"
git push


To bring that same data onto your laptop:

git pull

✨ Recommended workflow
When	What you do
On your Mac	Code, edit HTML/CSS/Python, test locally, push to GitHub
On your Pi	git pull && sudo systemctl restart recipeapp
On either	Backup recipes_v2.db occasionally to GitHub or /backups



