# Telegram Codespace Bot

This bot triggers a GitHub Actions workflow to start a Codespace.

## Env vars
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- GH_PAT
- ALLOWED_CHAT_ID (opcional, limita quién puede usar el bot)
- AUTO_STOP_MINUTES (opcional, auto-apagar por inactividad)
- CHECK_INTERVAL (opcional, segundos entre chequeos)

## Run
```bash
python3 bot/telegram_bot.py
```

## Systemd (24/7)
```bash
sudo cp bot/systemd/telegram-bot.service /etc/systemd/system/telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot
sudo systemctl status telegram-bot
```
