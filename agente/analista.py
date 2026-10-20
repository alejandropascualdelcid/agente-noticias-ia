"""Usa Claude para elegir, agrupar y resumir en español las noticias más importantes del día."""

from __future__ import annotations

import json
import logging
import os

import anthropic

from .recolector import Item

log = logging.getLogger(__name__)

MODELO = os.environ.get("MODELO_CLAUDE") or "claude-opus-5-5"

CATEGORIAS = [
    "OpenAI",
    "Anthropic",
    "Google",
    "Meta",
    "xAI",
    "IA china",
    "Otras empresas",
    "Nuevo modelo",
    "Herramientas",
    "MCP",
    "Repositorio",
    "Regulación",
    "Personas",
    "Investigación",
    "Negocio",
]

SISTEMA = """Eres el editor jefe de un canal en español de noticias de inteligencia artificial \
para Instagram y TikTok. Cada mañana recibes una lista bruta de titulares recogidos de blogs \
oficiales, medios, Google News, Reddit, Hacker News, GitHub y Hugging Face, y eliges lo que \
de verdad importa hoy.

Criterios:
- Prioriza: lanzamientos de modelos y productos, anuncios oficiales de OpenAI, Anthropic/Claude, \
Google, Meta, xAI, ElevenLabs, empresas chinas de IA (DeepSeek, Qwen, Kimi…), regulación, \
movimientos de personas clave (Sam Altman, Elon Musk, Dario Amodei…), grandes inversiones, \
herramientas y MCPs nuevos útiles, y repositorios que están explotando.
- Agrupa en UNA sola noticia los titulares que cuentan lo mismo y junta todas sus fuentes.
- Descarta: contenido promocional, tutoriales genéricos, opinión sin novedad y noticias \
que ya se enviaron en días anteriores (salvo que haya un avance importante).
- Distingue con honestidad: "confirmado" si viene de fuente oficial o de varios medios fiables; \
"rumor" si son filtraciones, especulación o una única fuente dudosa; "proximamente" si es un \
anuncio de algo que aún no ha salido.
- No inventes datos que no estén en los titulares o resúmenes. Si falta un detalle, no lo pongas.
- Escribe en español de España, claro y directo, sin tecnicismos innecesarios.
- Ordena de más a menos importante."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "noticias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Titular en español, máximo 90 caracteres"},
                    "emoji": {"type": "string", "description": "Un solo emoji representativo"},
                    "resumen": {"type": "string", "description": "2-3 frases explicando qué ha pasado"},
                    "por_que_importa": {"type": "string", "description": "1 frase: por qué le importa al público"},
                    "categoria": {"type": "string", "enum": CATEGORIAS},
                    "estado": {"type": "string", "enum": ["confirmado", "rumor", "proximamente"]},
                    "relevancia": {"type": "integer", "description": "Importancia de 1 a 10"},
                    "potencial_viral": {"type": "integer", "description": "Potencial en redes de 1 a 10"},
                    "gancho": {"type": "string", "description": "Primera frase para un Reel, que enganche en 2 segundos"},
                    "ids_fuente": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Números [n] de los titulares de la lista en los que se basa",
                    },
                },
                "required": [
                    "titulo",
                    "emoji",
                    "resumen",
                    "por_que_importa",
                    "categoria",
                    "estado",
                    "relevancia",
                    "potencial_viral",
                    "gancho",
                    "ids_fuente",
                ],
                "additionalProperties": False,
            },
        },
        "resumen_del_dia": {"type": "string", "description": "Una frase que resuma el día en IA"},
    },
    "required": ["noticias", "resumen_del_dia"],
    "additionalProperties": False,
}


def _formatear_items(items: list[Item]) -> str:
    lineas = []
    for n, it in enumerate(items):
        fecha = it.fecha.strftime("%d/%m %H:%M") if it.fecha else "s/f"
        linea = f"[{n}] ({it.fuente}, {fecha}) {it.titulo}"
        if it.resumen and it.resumen != it.titulo:
            linea += f" — {it.resumen}"
        lineas.append(linea)
    return "\n".join(lineas)


def analizar(items: list[Item], ya_enviadas: list[str], cantidad: int) -> dict:
    """Devuelve {"noticias": [...], "resumen_del_dia": str}; cada noticia incluye sus fuentes reales."""
    if not items:
        return {"noticias": [], "resumen_del_dia": "Hoy no se han encontrado noticias nuevas."}

    previas = "\n".join(f"- {t}" for t in ya_enviadas) or "(ninguna)"
    prompt = (
        f"Elige las {cantidad} noticias más importantes de hoy (menos si no hay suficientes de calidad).\n\n"
        f"Noticias ya enviadas los días anteriores (no repetir):\n{previas}\n\n"
        f"Titulares recogidos hoy:\n{_formatear_items(items)}"
    )

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODELO,
        max_tokens=32000,
        system=SISTEMA,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        respuesta = stream.get_final_message()

    log.info(
        "Claude (%s): %d tokens de entrada, %d de salida",
        respuesta.model,
        respuesta.usage.input_tokens,
        respuesta.usage.output_tokens,
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError(f"Claude rechazó la petición: {respuesta.stop_details}")
    if respuesta.stop_reason == "max_tokens":
        raise RuntimeError("La respuesta de Claude se cortó por longitud")

    texto = next(b.text for b in respuesta.content if b.type == "text")
    resultado = json.loads(texto)

    # Las URLs salen de nuestros datos, nunca del modelo, para que no haya enlaces inventados
    for noticia in resultado["noticias"]:
        fuentes = [items[i] for i in noticia.pop("ids_fuente") if 0 <= i < len(items)]
        noticia["fuentes"] = [{"nombre": f.fuente, "url": f.url, "id": f.id} for f in fuentes]
    resultado["noticias"] = [n for n in resultado["noticias"] if n["fuentes"]][:cantidad]
    return resultado
