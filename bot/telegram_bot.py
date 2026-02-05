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


def dispatch(action="start"):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
    headers = {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github+json"}
    data = {"ref": BRANCH, "inputs": {"action": action}}
    r = requests.post(url, headers=headers, json=data)
    return r.status_code, r.text


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
                code, text = dispatch("start")
                send(f"Dispatch start: {code}")
            elif msg == "/stopcodespace":
                code, text = dispatch("stop")
                send(f"Dispatch stop: {code}")
        time.sleep(1)


if __name__ == "__main__":
    main()
