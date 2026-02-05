import os, time, requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # your chat id
GH_PAT = os.environ["GH_PAT"]
REPO = "DesarrolladorPrimary/RDP"
WORKFLOW = "codespace.yml"
BRANCH = "main"


def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )


def gh_headers():
    return {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github+json"}


def dispatch(action="start"):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
    data = {"ref": BRANCH, "inputs": {"action": action}}
    r = requests.post(url, headers=gh_headers(), json=data)
    return r.status_code, r.text


def list_codespaces():
    url = "https://api.github.com/user/codespaces"
    r = requests.get(url, headers=gh_headers(), params={"per_page": 100})
    r.raise_for_status()
    items = r.json().get("codespaces", [])
    return [c for c in items if c.get("repository", {}).get("full_name") == REPO]


def start_codespace(name):
    url = f"https://api.github.com/user/codespaces/{name}/start"
    return requests.post(url, headers=gh_headers())


def stop_codespace(name):
    url = f"https://api.github.com/user/codespaces/{name}/stop"
    return requests.post(url, headers=gh_headers())


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()


def main():
    send("Bot activo. Usa /startcodespace o /stopcodespace")
    offset = None
    while True:
        updates = get_updates(offset)
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message", {}).get("text", "")
            if msg == "/startcodespace":
                try:
                    existing = list_codespaces()
                except Exception as e:
                    code, text = dispatch("start")
                    send(f"Dispatch start (fallback): {code}")
                    continue

                if existing:
                    cs = existing[0]
                    name = cs.get("name")
                    state = cs.get("state")
                    if state == "stopped":
                        r = start_codespace(name)
                        send(f"Codespace {name} estaba detenido. Start: {r.status_code}")
                    else:
                        send(f"Codespace ya existe: {name} (estado: {state})")
                else:
                    code, text = dispatch("start")
                    send(f"Dispatch start: {code}")

            elif msg == "/stopcodespace":
                try:
                    existing = list_codespaces()
                except Exception as e:
                    send("No pude listar codespaces.")
                    continue
                if not existing:
                    send("No hay codespaces para este repo.")
                else:
                    for cs in existing:
                        name = cs.get("name")
                        r = stop_codespace(name)
                    send("Stop solicitado para codespaces del repo.")

            elif msg == "/statuscodespace":
                try:
                    existing = list_codespaces()
                except Exception as e:
                    send("No pude listar codespaces.")
                    continue
                if not existing:
                    send("No hay codespaces para este repo.")
                else:
                    lines = []
                    for cs in existing:
                        name = cs.get("name")
                        state = cs.get("state")
                        machine = cs.get("machine", {}).get("display_name")
                        lines.append(f"- {name}: {state} ({machine})")
                    send("Codespaces:\n" + "\n".join(lines))
        time.sleep(1)


if __name__ == "__main__":
    main()
