"""Punto de entrada: recoge noticias, las analiza con Claude y envía el resumen a Telegram.

Uso:
    python -m agente.main            # respeta la hora de envío y no repite si ya se envió hoy
    python -m agente.main --forzar   # envía ahora mismo, sea la hora que sea
    python -m agente.main --prueba   # no envía a Telegram: imprime el resumen por pantalla
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import analista, recolector, telegram

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "fuentes.yaml"
DATOS = RAIZ / "data"
RESUMENES = DATOS / "resumenes"
VISTOS = DATOS / "vistos.json"

ZONA = ZoneInfo(os.environ.get("ZONA_HORARIA") or "Europe/Madrid")
HORA_ENVIO = int(os.environ.get("HORA_ENVIO") or 10)
CANTIDAD = int(os.environ.get("NUMERO_NOTICIAS") or 12)
DIAS_MEMORIA = 14

log = logging.getLogger("agente")


def cargar_vistos() -> dict[str, str]:
    if VISTOS.exists():
        return json.loads(VISTOS.read_text(encoding="utf-8"))
    return {}


def guardar_vistos(vistos: dict[str, str], hoy) -> None:
    limite = (hoy - timedelta(days=DIAS_MEMORIA)).isoformat()
    vistos = {k: v for k, v in vistos.items() if v >= limite}
    VISTOS.write_text(json.dumps(vistos, indent=0, sort_keys=True), encoding="utf-8")


def titulos_recientes(hoy, dias: int = 3) -> list[str]:
    titulos = []
    for d in range(1, dias + 1):
        ruta = RESUMENES / f"{(hoy - timedelta(days=d)).isoformat()}.json"
        if ruta.exists():
            titulos += [n["titulo"] for n in json.loads(ruta.read_text(encoding="utf-8"))["noticias"]]
    return titulos


def guardar_resumen(hoy, resultado: dict) -> None:
    RESUMENES.mkdir(parents=True, exist_ok=True)
    (RESUMENES / f"{hoy.isoformat()}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lineas = [f"# Resumen IA · {hoy.isoformat()}", "", resultado["resumen_del_dia"], ""]
    for i, n in enumerate(resultado["noticias"], start=1):
        fuentes = ", ".join(f"[{f['nombre']}]({f['url']})" for f in n["fuentes"])
        lineas += [
            f"## {i}. {n['emoji']} {n['titulo']}",
            f"*{n['categoria']} · {n['estado']} · relevancia {n['relevancia']}/10 · viral {n['potencial_viral']}/10*",
            "",
            n["resumen"],
            "",
            f"**Por qué importa:** {n['por_que_importa']}",
            "",
            f"**Gancho:** «{n['gancho']}»",
            "",
            f"Fuentes: {fuentes}",
            "",
        ]
    (RESUMENES / f"{hoy.isoformat()}.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forzar", action="store_true", help="enviar aunque no sea la hora o ya se haya enviado")
    parser.add_argument("--prueba", action="store_true", help="no enviar a Telegram ni guardar nada")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    ya_enviado = (RESUMENES / f"{hoy.isoformat()}.json").exists()

    if not (args.forzar or args.prueba):
        if ahora.hour < HORA_ENVIO:
            log.info("Son las %s en %s; el envío es a las %d:00. Nada que hacer.", ahora.strftime("%H:%M"), ZONA, HORA_ENVIO)
            return 0
        if ya_enviado:
            log.info("El resumen de hoy ya se envió. Nada que hacer.")
            return 0

    vistos = cargar_vistos()
    items = [it for it in recolector.recolectar(CONFIG) if it.id not in vistos]
    log.info("%d noticias nuevas para analizar", len(items))

    try:
        resultado = analista.analizar(items, titulos_recientes(hoy), CANTIDAD)
    except Exception as e:
        log.exception("Falló el análisis")
        if not args.prueba:
            telegram.enviar([f"⚠️ Hoy no he podido preparar el resumen de IA: {telegram.escapar(str(e))[:500]}"])
        return 1
    mensajes = telegram.formatear_resumen(hoy, resultado)

    if args.prueba:
        print("\n\n".join(mensajes))
        return 0

    telegram.enviar(mensajes)
    for n in resultado["noticias"]:
        for f in n["fuentes"]:
            vistos[f["id"]] = hoy.isoformat()
    guardar_vistos(vistos, hoy)
    guardar_resumen(hoy, resultado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
