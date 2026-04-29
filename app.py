"""
app.py - Microsoft Rewards Script v3 pour Render (Web Service gratuit)

Variables d'environnement Render (Settings > Environment) :
  ACCOUNT_1_EMAIL    = ton_email@outlook.com
  ACCOUNT_1_PASSWORD = ton_mot_de_passe
  CRON_SCHEDULE      = 0 7,16,20 * * *   (optionnel)
  RUN_ON_START       = true                (optionnel)
"""

import json
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import gradio as gr
from apscheduler.schedulers.background import BackgroundScheduler

# === Paths (v3 cherche config.json et accounts.json directement dans dist/) ===
SCRIPT_DIR = Path("/usr/src/microsoft-rewards-script")
DIST_DIR = SCRIPT_DIR / "dist"
ACCOUNTS_FILE = DIST_DIR / "accounts.json"
CONFIG_FILE = DIST_DIR / "config.json"
LOG_FILE = Path("/app/rewards_script.log")
MAX_LOG_LINES = 500
RENDER_PORT = int(os.environ.get("PORT", 10000))

# === State ===
is_running = False
run_process = None
scheduler = BackgroundScheduler()


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_log() -> str:
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return "".join(lines[-MAX_LOG_LINES:])
        return "Pas encore de logs. Le script n'a pas tourne."
    except Exception as e:
        return f"Erreur lecture log: {e}"


def generate_accounts_json() -> bool:
    accounts = []
    idx = 1

    while True:
        email = os.environ.get(f"ACCOUNT_{idx}_EMAIL", "").strip()
        password = os.environ.get(f"ACCOUNT_{idx}_PASSWORD", "").strip()
        if not email or not password:
            break
        account = {"email": email, "password": password}
        proxy_url = os.environ.get(f"ACCOUNT_{idx}_PROXY_URL", "").strip()
        if proxy_url:
            account["proxy"] = {
                "proxyAxios": True,
                "url": proxy_url,
                "port": int(os.environ.get(f"ACCOUNT_{idx}_PROXY_PORT", "0")),
                "username": os.environ.get(f"ACCOUNT_{idx}_PROXY_USER", ""),
                "password": os.environ.get(f"ACCOUNT_{idx}_PROXY_PASS", ""),
            }
        accounts.append(account)
        idx += 1

    if not accounts:
        log("ERREUR: Aucun credential trouve ! Ajoute ACCOUNT_1_EMAIL et ACCOUNT_1_PASSWORD dans les variables d'environnement Render.")
        return False

    try:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=4)
        log(f"accounts.json genere: {len(accounts)} compte(s)")
        for a in accounts:
            log(f"  -> {a['email']}")
        return True
    except Exception as e:
        log(f"ERREUR ecriture accounts.json: {e}")
        return False


def ensure_config():
    try:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        elif (SCRIPT_DIR / "src" / "config.example.json").exists():
            with open(SCRIPT_DIR / "src" / "config.example.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}

        config["headless"] = True

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        log("config.json pret (headless=true)")
    except Exception as e:
        log(f"ERREUR config.json: {e}")


def run_script():
    global is_running, run_process

    if is_running:
        log("Script deja en cours, skip...")
        return

    is_running = True
    log("=" * 50)
    log("DEBUT - Microsoft Rewards Script")
    log("=" * 50)

    if not generate_accounts_json():
        log("Abandon: impossible de generer accounts.json")
        is_running = False
        return

    ensure_config()

    try:
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        env["FORCE_HEADLESS"] = "1"

        run_process = subprocess.Popen(
            ["node", "./dist/index.js"],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        for line in run_process.stdout:
            stripped = line.strip()
            if stripped:
                log(f"[SCRIPT] {stripped}")

        run_process.wait()
        code = run_process.returncode
        status = "SUCCES" if code == 0 else f"ERREUR (code {code})"
        log("=" * 50)
        log(f"FIN - Script termine: {status}")
        log("=" * 50)

    except Exception as e:
        log(f"ERREUR execution: {e}")
    finally:
        is_running = False
        run_process = None


def run_script_threaded():
    threading.Thread(target=run_script, daemon=True).start()


def manual_run():
    if is_running:
        return "⚠️ Script deja en cours. Patientez..."
    run_script_threaded()
    return "✅ Script lance ! Les logs vont apparaitre ci-dessous."


def refresh_status():
    if is_running:
        status = "🟡 En cours d'execution..."
    else:
        status = "🟢 En attente"

    next_run = "N/A"
    if scheduler.running:
        jobs = scheduler.get_jobs()
        if jobs and jobs[0].next_run_time:
            next_run = jobs[0].next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    accounts_info = "Non configure"
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r") as f:
                accs = json.load(f)
            emails = [a.get("email", "?") for a in accs]
            accounts_info = f"{len(accs)} compte(s): {', '.join(emails)}"
        except Exception:
            accounts_info = "Erreur lecture"

    return f"{status}\nProchain run: {next_run}\nComptes: {accounts_info}"


def refresh_logs():
    return read_log()


def clear_logs():
    try:
        if LOG_FILE.exists():
            open(LOG_FILE, "w").close()
    except Exception:
        pass
    return "Logs effaces."


def parse_cron():
    schedule = os.environ.get("CRON_SCHEDULE", "0 7,16,20 * * *").strip()
    parts = schedule.split()
    if len(parts) != 5:
        parts = ["0", "7,16,20", "*", "*", "*"]
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


# === Gradio UI ===
def build_ui():
    with gr.Blocks(title="Microsoft Rewards Script") as demo:
        gr.Markdown(
            """
            # 🎁 Microsoft Rewards Script v3
            [TheNetsky/Microsoft-Rewards-Script](https://github.com/TheNetsky/Microsoft-Rewards-Script) • Heberge sur Render
            ---
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📊 Statut")
                status_box = gr.Textbox(value="Demarrage...", label="Statut", interactive=False, lines=3)
                gr.Button("🔄 Rafraichir").click(fn=refresh_status, outputs=status_box)

            with gr.Column(scale=1):
                gr.Markdown("### 🚀 Lancer manuellement")
                run_btn = gr.Button("▶️ Executer maintenant", variant="primary", size="lg")
                run_out = gr.Textbox(label="Resultat", interactive=False)
                run_btn.click(fn=manual_run, outputs=run_out)

        gr.Markdown("### 📜 Logs")
        log_box = gr.Textbox(
            value="Chargement...",
            label="Logs",
            interactive=False,
            lines=20,
            max_lines=50,
        )

        with gr.Row():
            gr.Button("🔄 Rafraichir les logs").click(fn=refresh_logs, outputs=log_box)
            gr.Button("🗑️ Vider les logs").click(fn=clear_logs, outputs=log_box)

        timer = gr.Timer(value=10)
        timer.tick(fn=refresh_logs, outputs=log_box)
        timer.tick(fn=refresh_status, outputs=status_box)

        gr.Markdown(
            """
            ---
            ### 🔑 Variables Render (Settings > Environment)

            | Variable | Description | Exemple |
            |----------|-------------|---------|
            | `ACCOUNT_1_EMAIL` | Email Microsoft | `vous@outlook.com` |
            | `ACCOUNT_1_PASSWORD` | Mot de passe | `votre_mdp` |
            | `ACCOUNT_2_EMAIL` | 2e compte (optionnel) | `autre@outlook.com` |
            | `ACCOUNT_2_PASSWORD` | Mot de passe 2e compte | `mdp2` |
            | `CRON_SCHEDULE` | Planning (defaut: 3x/jour) | `0 7,16,20 * * *` |
            | `RUN_ON_START` | Lancer au demarrage | `true` |
            """
        )

    return demo


# === Main ===
if __name__ == "__main__":
    log("=" * 60)
    log("Microsoft Rewards Script v3 - Render")
    log("=" * 60)

    has_creds = os.environ.get("ACCOUNT_1_EMAIL", "").strip() and os.environ.get("ACCOUNT_1_PASSWORD", "").strip()
    if has_creds:
        log(f"Credentials trouves: {os.environ.get('ACCOUNT_1_EMAIL')}")
    else:
        log("ATTENTION: Aucun credential ! Configure ACCOUNT_1_EMAIL + ACCOUNT_1_PASSWORD")

    generate_accounts_json()
    ensure_config()

    cron = parse_cron()
    log(f"Planning: minute={cron['minute']} heure={cron['hour']} jour={cron['day']} mois={cron['month']} jsemaine={cron['day_of_week']}")

    scheduler.add_job(
        run_script_threaded,
        "cron",
        minute=cron["minute"],
        hour=cron["hour"],
        day=cron["day"],
        month=cron["month"],
        day_of_week=cron["day_of_week"],
        id="rewards_run",
        name="Microsoft Rewards Run",
    )
    scheduler.start()
    log("Scheduler actif")

    if os.environ.get("RUN_ON_START", "true").lower() == "true":
        log("RUN_ON_START=true -> Lancement dans 30s...")
        threading.Timer(30, run_script_threaded).start()
    else:
        log("RUN_ON_START=false")

    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=RENDER_PORT,
        show_error=True,
        theme=gr.themes.Soft(),
        css=".log-box { font-family: monospace; font-size: 12px; }",
    )
