"""Ayuda a averiguar tu TELEGRAM_CHAT_ID.

1. Escribe cualquier mensaje a tu bot en Telegram.
2. Ejecuta:  TELEGRAM_BOT_TOKEN=xxxx python -m agente.obtener_chat_id
"""

import os
import sys

import requests


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Falta la variable TELEGRAM_BOT_TOKEN")
        return 1
    datos = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    chats = {
        u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name") or u["message"]["chat"].get("title")
        for u in datos.get("result", [])
        if "message" in u
    }
    if not chats:
        print("No hay mensajes. Escribe algo a tu bot en Telegram y vuelve a ejecutar esto.")
        return 1
    for chat_id, nombre in chats.items():
        print(f"{nombre}: TELEGRAM_CHAT_ID = {chat_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
