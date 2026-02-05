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


def get_codespace_by_name(name):
    url = f"https://api.github.com/user/codespaces/{name}"
    r = requests.get(url, headers=gh_headers())
    r.raise_for_status()
    return r.json()


def start_codespace(name):
    url = f"https://api.github.com/user/codespaces/{name}/start"
    return requests.post(url, headers=gh_headers())


def stop_codespace(name):
    url = f"https://api.github.com/user/codespaces/{name}/stop"
    return requests.post(url, headers=gh_headers())


def delete_codespace(name):
    url = f"https://api.github.com/user/codespaces/{name}"
    return requests.delete(url, headers=gh_headers())


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()


def main():
    send(
        "🤖 Bot activo.\n"
        "Comandos:\n"
        "• /startcodespace [nombre] – Inicia un codespace existente\n"
        "• /newcodespace – Crea un codespace nuevo\n"
        "• /stopcodespace – Detiene codespaces del repo\n"
        "• /statuscodespace – Estado de codespaces\n"
        "• /listcodespace – Lista codespaces\n"
        "• /restartcodespace – Reinicia codespaces\n"
        "• /deletecodespace – Elimina codespaces\n"
    )
    offset = None
    while True:
        updates = get_updates(offset)
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message", {}).get("text", "")
            if msg.startswith("/startcodespace"):
                parts = msg.split()
                target_name = parts[1] if len(parts) > 1 else None
                try:
                    existing = list_codespaces()
                except Exception as e:
                    send("No pude listar codespaces.")
                    continue

                if not existing:
                    send("No hay codespaces. Usa /newcodespace para crear uno.")
                    continue

                if target_name:
                    match = [c for c in existing if c.get("name") == target_name]
                    if not match:
                        send("No encontré ese codespace. Usa /listcodespace.")
                        continue
                    cs = match[0]
                else:
                    cs = existing[0]

                name = cs.get("name")
                state = cs.get("state")
                if state in ("stopped", "shutdown", "Shutdown"):
                    r = start_codespace(name)
                    send(f"Start solicitado para {name}: {r.status_code}")
                elif state in ("ShuttingDown", "shutting_down"):
                    send(f"{name} está apagándose. Esperando 30s...")
                    time.sleep(30)
                    try:
                        cs2 = get_codespace_by_name(name)
                        state2 = cs2.get("state")
                    except Exception:
                        state2 = None
                    if state2 in ("stopped", "shutdown", "Shutdown"):
                        r = start_codespace(name)
                        send(f"Start solicitado para {name}: {r.status_code}")
                    else:
                        send(f"Aún en estado: {state2}")
                else:
                    send(f"Codespace {name} ya está en estado: {state}")

            elif msg == "/newcodespace":
                code, text = dispatch("start")
                send(f"Crear nuevo codespace: {code}")

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

            elif msg == "/statuscodespace" or msg == "/listcodespace":
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
                        last = cs.get("last_used_at")
                        lines.append(f"- {name}: {state} ({machine}) last_used={last}")
                    send("Codespaces:\n" + "\n".join(lines))

            elif msg == "/restartcodespace":
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
                        stop_codespace(name)
                    time.sleep(5)
                    for cs in existing:
                        name = cs.get("name")
                        start_codespace(name)
                    send("Restart solicitado para codespaces del repo.")

            elif msg == "/deletecodespace":
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
                        delete_codespace(name)
                    send("Delete solicitado para codespaces del repo.")
        time.sleep(1)


if __name__ == "__main__":
    main()
