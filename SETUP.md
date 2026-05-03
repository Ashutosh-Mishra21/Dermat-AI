# DermaSense AI — Local Setup Guide (VS Code)

Complete step-by-step guide to download this project from GitHub and run it on your own computer using VS Code.

---

## Prerequisites (install these once)

Download and install:

1. **Git** → https://git-scm.com/downloads
2. **Python 3.10+** → https://www.python.org/downloads/ (✅ check "Add Python to PATH" during install)
3. **Node.js LTS (v18 or v20)** → https://nodejs.org/ (only needed if you want the React preview; the pure static site works without it)
4. **MongoDB Community** → https://www.mongodb.com/try/download/community (install as a service so it starts automatically)
5. **VS Code** → https://code.visualstudio.com/
6. **Yarn** (after Node.js is installed, open a terminal and run): `npm install -g yarn`

> **VS Code extensions (recommended):** Python, Pylance, ESLint, Live Server, GitLens

---

## Step 1 — Download the project from GitHub

Open a terminal (PowerShell on Windows / Terminal on Mac/Linux):

```bash
cd Desktop
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
code .
```

The last command opens the project in VS Code.

---

## Step 2 — Set up the Python backend (with virtual environment)

Open the **Terminal** inside VS Code: `Ctrl+` ` (backtick) or menu **Terminal → New Terminal**.

```bash
cd backend
```

### Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should now see `(venv)` at the start of your terminal line. ✅

### Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This takes 1–2 minutes.

### Configure your API keys

Open `backend/.env` in VS Code and paste your keys:

```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="dermasense_db"
CORS_ORIGINS="*"

SILICONFLOW_API_KEY="sk-xxxxx..."
OPENROUTER_API_KEY="sk-or-xxxxx..."
OPENWEB_NINJA_API_KEY="xxxxx..."
```

> Leave a key as `""` if you don't have it — the app will fall back gracefully.

### Start the backend

Make sure the `(venv)` is still active, then run:

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

You should see:
```
Uvicorn running on http://0.0.0.0:8001
Application startup complete.
```

Leave this terminal **open and running**. Open a **second terminal** for the next step.

---

## Step 3 — Run the frontend (static site — simplest option)

The frontend is plain HTML/CSS/JS in `frontend/public/dermasense/`. You have two ways to run it:

### Option A — VS Code Live Server (easiest, recommended)

1. Install the **Live Server** extension in VS Code (already recommended above).
2. In VS Code's file explorer, right-click `frontend/public/dermasense/index.html`
3. Click **"Open with Live Server"**
4. Your browser opens `http://127.0.0.1:5500/frontend/public/dermasense/index.html`

### Option B — Python's built-in server

In a new terminal:
```bash
cd frontend/public/dermasense
python -m http.server 3000
```
Then open http://localhost:3000 in your browser.

### Important: Point the frontend at your backend

Open `frontend/public/dermasense/script.js` and find line ~7:

```js
const API_BASE = (() => {
  try {
    if (window.location.protocol === "file:") return "http://localhost:8001";
    return window.location.origin;
  } catch (_) { return ""; }
})();
```

Change it to:

```js
const API_BASE = "http://localhost:8001";
```

Save the file and refresh your browser. The quiz now talks to your local backend. ✅

---

## Step 4 — (Optional) Run the full React + static setup

If you want the same dev experience as the original preview:

```bash
cd frontend
yarn install
yarn start
```

This starts the React shell on http://localhost:3000 and auto-redirects to the DermaSense site. Keep the backend running in parallel (Step 2).

---

## Step 5 — Verify everything works

1. Backend health check: open http://localhost:8001/api/config in your browser — you should see `{"siliconflow":true,"openrouter":true,"amazon":true}` (depending on which keys you filled).
2. Open the DermaSense site, take the skin quiz, submit — you should see real AI recommendations.
3. Open the Products page — you should see live Amazon.in results with rupee prices.

---

## Daily workflow (after initial setup)

Every time you come back to code:

```bash
# Terminal 1 — backend
cd backend
# Windows:
venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — frontend (Live Server handles this automatically, or):
cd frontend/public/dermasense
python -m http.server 3000
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `pip` or `python` not recognized | Reinstall Python with "Add to PATH" checked, then restart VS Code |
| `ModuleNotFoundError: fastapi` | You forgot to activate venv. Run the `Activate.ps1` / `source venv/bin/activate` command again |
| `MongoServerError: connect ECONNREFUSED` | MongoDB service isn't running. On Windows: open Services → Start "MongoDB Server". On Mac: `brew services start mongodb-community` |
| Quiz submits but says "Default recommendations" | API keys are blank or invalid. Re-check `backend/.env` and **restart the backend** after editing |
| CORS errors in browser console | Make sure `CORS_ORIGINS="*"` is set in `.env` and backend is restarted |
| Port 8001 already in use | Run `uvicorn server:app --port 8002` and update `API_BASE` accordingly |
| Amazon products all show `—` | Your OpenWeb Ninja key is invalid, out of credits, or not subscribed to the "Real-Time Amazon Data" plan on RapidAPI |

---

## Project structure

```
<your-repo>/
├── backend/
│   ├── server.py              # FastAPI routes
│   ├── skin_analysis.py       # AI integration (SiliconFlow + OpenRouter)
│   ├── amazon_service.py      # OpenWeb Ninja Amazon.in integration
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # Your API keys (DO NOT commit!)
│   └── venv/                  # Virtual environment (auto-created, gitignored)
└── frontend/
    └── public/
        └── dermasense/
            ├── index.html     # Structure
            ├── styles.css     # Design
            └── script.js      # Behavior + API calls
```

---

## Pushing changes back to GitHub

```bash
git add .
git commit -m "description of what you changed"
git push
```

**Before your first push**, make sure `.gitignore` contains:
```
backend/venv/
backend/.env
node_modules/
__pycache__/
*.pyc
```
so you don't accidentally upload your API keys or the huge venv folder.

---

Happy coding! ✦
