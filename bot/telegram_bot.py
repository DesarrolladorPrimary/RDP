import os, time, requests, threading, datetime

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # your chat id
GH_PAT = os.environ["GH_PAT"]
REPO = "DesarrolladorPrimary/RDP"
WORKFLOW = "codespace.yml"
BRANCH = "main"
ALLOWED_CHAT_ID = os.environ.get("ALLOWED_CHAT_ID", CHAT_ID)
AUTO_STOP_MINUTES = int(os.environ.get("AUTO_STOP_MINUTES", "0"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
PENDING = {}


def send(msg, chat_id=None):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id or CHAT_ID, "text": msg}
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


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    send(
        "✨ *Codespace Control* ✨\n"
        "Estoy activo y listo.\n\n"
        "📌 *Comandos principales*\n"
        "• /startcodespace [nombre] → Inicia un codespace\n"
        "• /newcodespace → Crea un codespace nuevo\n"
        "• /stopcodespace → Detiene codespaces\n\n"
        "📊 *Estado*\n"
        "• /statuscodespace → Estado detallado\n"
        "• /listcodespace → Lista rápida\n\n"
        "🛠️ *Mantenimiento*\n"
        "• /restartcodespace → Reinicia (con confirmación)\n"
        "• /deletecodespace → Elimina (con confirmación)\n\n"
        "ℹ️ /help\n"
    )

    def wait_for_running(nm, timeout=180, interval=15):
        waited = 0
        while waited < timeout:
            try:
                csx = get_codespace_by_name(nm)
                st = csx.get("state")
            except Exception:
                st = None
            if st in ("Available", "running"):
                return True, st
            time.sleep(interval)
            waited += interval
        return False, st

    def wait_for_stopped(nm, timeout=180, interval=15):
        waited = 0
        while waited < timeout:
            try:
                csx = get_codespace_by_name(nm)
                st = csx.get("state")
            except Exception:
                st = None
            if st in ("Shutdown", "shutdown", "stopped"):
                return True, st
            time.sleep(interval)
            waited += interval
        return False, st

    def confirm(chat_id, action, payload):
        code = str(int(time.time()))[-4:]
        PENDING[chat_id] = (action, payload, time.time(), code)
        send(f"Confirma con: /confirm {code}", chat_id)

    offset = None
    while True:
        updates = get_updates(offset)
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message", {}).get("text", "")
            chat_id = u.get("message", {}).get("chat", {}).get("id")

            if ALLOWED_CHAT_ID and str(chat_id) != str(ALLOWED_CHAT_ID):
                continue

            if msg.startswith("/confirm"):
                parts = msg.split()
                code = parts[1] if len(parts) > 1 else None
                if not code or chat_id not in PENDING:
                    send("No hay acción pendiente.", chat_id)
                    continue
                action, payload, ts, expect = PENDING.get(chat_id)
                if code != expect:
                    send("Código inválido.", chat_id)
                    continue
                PENDING.pop(chat_id, None)
                if action == "delete":
                    existing = payload
                    for cs in existing:
                        name = cs.get("name")
                        delete_codespace(name)
                    send("Delete solicitado para codespaces del repo.", chat_id)
                elif action == "restart":
                    existing = payload
                    for cs in existing:
                        stop_codespace(cs.get("name"))
                    time.sleep(5)
                    for cs in existing:
                        start_codespace(cs.get("name"))
                    send("Restart solicitado para codespaces del repo.", chat_id)
                continue

            if msg in ("/help", "/start"):
                send("Usa /listcodespace para ver tus codespaces.", chat_id)
                continue

            if msg.startswith("/startcodespace"):
                parts = msg.split()
                target_name = parts[1] if len(parts) > 1 else None
                try:
                    existing = list_codespaces()
                except Exception:
                    send("No pude listar codespaces.", chat_id)
                    continue

                if not existing:
                    send("No hay codespaces. Usa /newcodespace para crear uno.", chat_id)
                    continue

                if target_name:
                    match = [c for c in existing if c.get("name") == target_name]
                    if not match:
                        send("No encontré ese codespace. Usa /listcodespace.", chat_id)
                        continue
                    cs = match[0]
                else:
                    cs = existing[0]

                name = cs.get("name")
                state = cs.get("state")

                if state in ("stopped", "shutdown", "Shutdown"):
                    r = start_codespace(name)
                    send(f"Start solicitado para {name}: {r.status_code}. Esperando... ", chat_id)
                    ok, st = wait_for_running(name)
                    if ok:
                        send(f"✅ {name} ya está listo ({st}).", chat_id)
                    else:
                        send(f"⏳ {name} aún no está listo (estado: {st}).", chat_id)
                elif state in ("ShuttingDown", "shutting_down"):
                    send(f"{name} está apagándose. Esperando 30s...", chat_id)
                    time.sleep(30)
                    try:
                        cs2 = get_codespace_by_name(name)
                        state2 = cs2.get("state")
                    except Exception:
                        state2 = None
                    if state2 in ("stopped", "shutdown", "Shutdown"):
                        r = start_codespace(name)
                        send(f"Start solicitado para {name}: {r.status_code}. Esperando...", chat_id)
                        ok, st = wait_for_running(name)
                        if ok:
                            send(f"✅ {name} ya está listo ({st}).", chat_id)
                        else:
                            send(f"⏳ {name} aún no está listo (estado: {st}).", chat_id)
                    else:
                        send(f"Aún en estado: {state2}", chat_id)
                else:
                    send(f"Codespace {name} ya está en estado: {state}", chat_id)

            elif msg == "/newcodespace":
                code, text = dispatch("start")
                send(f"Crear nuevo codespace: {code}", chat_id)

            elif msg == "/stopcodespace":
                try:
                    existing = list_codespaces()
                except Exception:
                    send("No pude listar codespaces.", chat_id)
                    continue
                if not existing:
                    send("No hay codespaces para este repo.", chat_id)
                else:
                    for cs in existing:
                        stop_codespace(cs.get("name"))
                    send("Stop solicitado. Esperando apagado...", chat_id)
                    for cs in existing:
                        name = cs.get("name")
                        ok, st = wait_for_stopped(name)
                        if ok:
                            send(f"✅ {name} apagado ({st}).", chat_id)
                        else:
                            send(f"⏳ {name} aún no se apaga (estado: {st}).", chat_id)

            elif msg == "/statuscodespace" or msg == "/listcodespace":
                try:
                    existing = list_codespaces()
                except Exception:
                    send("No pude listar codespaces.", chat_id)
                    continue
                if not existing:
                    send("No hay codespaces para este repo.", chat_id)
                else:
                    lines = []
                    for cs in existing:
                        name = cs.get("name")
                        state = cs.get("state")
                        machine = cs.get("machine", {}).get("display_name")
                        last = cs.get("last_used_at")
                        lines.append(f"- {name}: {state} ({machine}) last_used={last}")
                    send("Codespaces:\n" + "\n".join(lines), chat_id)

            elif msg == "/restartcodespace":
                try:
                    existing = list_codespaces()
                except Exception:
                    send("No pude listar codespaces.", chat_id)
                    continue
                if not existing:
                    send("No hay codespaces para este repo.", chat_id)
                else:
                    confirm(chat_id, "restart", existing)

            elif msg == "/deletecodespace":
                try:
                    existing = list_codespaces()
                except Exception:
                    send("No pude listar codespaces.", chat_id)
                    continue
                if not existing:
                    send("No hay codespaces para este repo.", chat_id)
                else:
                    confirm(chat_id, "delete", existing)
        time.sleep(1)


def autostop_loop():
    if AUTO_STOP_MINUTES <= 0:
        return
    while True:
        try:
            existing = list_codespaces()
            now = datetime.datetime.now(datetime.timezone.utc)
            for cs in existing:
                state = cs.get("state")
                last_used = parse_ts(cs.get("last_used_at"))
                if state in ("Available", "running") and last_used:
                    idle_min = (now - last_used).total_seconds() / 60
                    if idle_min >= AUTO_STOP_MINUTES:
                        stop_codespace(cs.get("name"))
                        send(f"🛑 Auto-stop: {cs.get('name')} por inactividad ({int(idle_min)} min).")
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    t = threading.Thread(target=autostop_loop, daemon=True)
    t.start()
    main()
