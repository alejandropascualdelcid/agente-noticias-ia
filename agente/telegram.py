"""Envía el resumen diario a Telegram."""

from __future__ import annotations

import html
import logging
import os

import requests

log = logging.getLogger(__name__)

LIMITE_MENSAJE = 4000  # Telegram admite 4096 caracteres por mensaje

ETIQUETA_ESTADO = {
    "confirmado": "✅ Confirmado",
    "rumor": "⚠️ Rumor",
    "proximamente": "🔜 Próximamente",
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def escapar(texto: str) -> str:
    return html.escape(texto or "", quote=False)


def formatear_noticia(n: int, noticia: dict) -> str:
    enlaces = " · ".join(
        f'<a href="{html.escape(f["url"])}">{escapar(f["nombre"])}</a>' for f in noticia["fuentes"][:3]
    )
    fuego = " 🔥" if noticia["potencial_viral"] >= 8 else ""
    return (
        f"<b>{n}. {escapar(noticia['emoji'])} {escapar(noticia['titulo'])}</b>{fuego}\n"
        f"<i>{escapar(noticia['categoria'])} · {ETIQUETA_ESTADO.get(noticia['estado'], noticia['estado'])}</i>\n"
        f"{escapar(noticia['resumen'])}\n"
        f"💡 {escapar(noticia['por_que_importa'])}\n"
        f"🎣 <i>Gancho:</i> «{escapar(noticia['gancho'])}»\n"
        f"🔗 {enlaces}"
    )


def formatear_resumen(fecha, resultado: dict) -> list[str]:
    """Devuelve el resumen dividido en mensajes que caben en Telegram."""
    cabecera = (
        f"🤖 <b>Resumen IA · {fecha.day} de {MESES[fecha.month - 1]}</b>\n"
        f"{escapar(resultado['resumen_del_dia'])}"
    )
    bloques = [formatear_noticia(i, n) for i, n in enumerate(resultado["noticias"], start=1)]
    if not bloques:
        return [cabecera]

    mensajes, actual = [], cabecera
    for bloque in bloques:
        if len(actual) + len(bloque) + 2 > LIMITE_MENSAJE:
            mensajes.append(actual)
            actual = bloque
        else:
            actual += "\n\n" + bloque
    mensajes.append(actual)
    return mensajes


def enviar(mensajes: list[str]) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    for texto in mensajes:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"Telegram respondió {r.status_code}: {r.text}")
    log.info("Enviados %d mensajes a Telegram", len(mensajes))
