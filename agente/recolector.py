"""Recoge noticias de todas las fuentes configuradas en config/fuentes.yaml."""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlsplit, urlunsplit

import feedparser
import requests
import yaml

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; agente-noticias-ia/1.0)"
TIMEOUT = 20
MAX_POR_FUENTE = 15
MAX_RESUMEN = 300

PALABRAS_IA = re.compile(
    r"\b(ai|a\.i\.|ia|llm|llms|gpt|chatgpt|openai|anthropic|claude|gemini|deepmind|llama|mistral|"
    r"deepseek|qwen|grok|xai|elevenlabs|nvidia|agents?|agentic|mcp|transformer|diffusion|"
    r"machine learning|neural|inteligencia artificial|modelo|copilot|cursor|hugging ?face)\b",
    re.IGNORECASE,
)


@dataclass
class Item:
    titulo: str
    url: str
    fuente: str
    fecha: datetime | None = None
    resumen: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return hashlib.sha1(normalizar_url(self.url).encode()).hexdigest()[:12]


def normalizar_url(url: str) -> str:
    partes = urlsplit(url.strip())
    return urlunsplit((partes.scheme, partes.netloc.lower(), partes.path.rstrip("/"), partes.query, ""))


def limpiar(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:MAX_RESUMEN]


def _get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    r = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _fecha_entrada(entry) -> datetime | None:
    for clave in ("published_parsed", "updated_parsed"):
        valor = entry.get(clave)
        if valor:
            return datetime(*valor[:6], tzinfo=timezone.utc)
    return None


def _leer_feed(url: str, fuente: str, desde: datetime) -> list[Item]:
    feed = feedparser.parse(_get(url).content)
    items = []
    for entry in feed.entries:
        fecha = _fecha_entrada(entry)
        if fecha and fecha < desde:
            continue
        titulo = limpiar(entry.get("title", ""))
        enlace = entry.get("link", "")
        if not titulo or not enlace:
            continue
        # Google News pone el medio en <source>; lo usamos como nombre de fuente
        origen = entry.get("source", {}).get("title") if entry.get("source") else None
        items.append(
            Item(
                titulo=titulo,
                url=enlace,
                fuente=f"{origen} (Google News)" if origen else fuente,
                fecha=fecha,
                resumen=limpiar(entry.get("summary", "")),
            )
        )
        if len(items) >= MAX_POR_FUENTE:
            break
    return items


def rss(fuentes: list[dict], desde: datetime) -> list[Item]:
    items = []
    for f in fuentes:
        try:
            nuevos = _leer_feed(f["url"], f["nombre"], desde)
        except Exception as e:  # una fuente caída no debe parar el resto
            log.warning("RSS %s falló: %s", f["nombre"], e)
            continue
        if f.get("filtrar_ia"):
            nuevos = [it for it in nuevos if PALABRAS_IA.search(f"{it.titulo} {it.resumen}")]
        items += nuevos
    return items


def google_news(consultas: list[dict], desde: datetime) -> list[Item]:
    items = []
    for c in consultas:
        idioma = c.get("idioma", "en")
        region = "ES" if idioma == "es" else "US"
        url = (
            f"https://news.google.com/rss/search?q={quote_plus(c['consulta'] + ' when:1d')}"
            f"&hl={idioma}&gl={region}&ceid={region}:{idioma}"
        )
        try:
            items += _leer_feed(url, "Google News", desde)
        except Exception as e:
            log.warning("Google News '%s' falló: %s", c["consulta"], e)
    return items


def hacker_news(config: dict, desde: datetime) -> list[Item]:
    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{int(desde.timestamp())},points>{config.get('min_puntos', 100)}",
        "hitsPerPage": 100,
    }
    try:
        hits = _get(url, params=params).json()["hits"]
    except Exception as e:
        log.warning("Hacker News falló: %s", e)
        return []
    items = []
    for h in hits:
        titulo = h.get("title") or ""
        if not PALABRAS_IA.search(titulo):
            continue
        items.append(
            Item(
                titulo=titulo,
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                fuente="Hacker News",
                fecha=datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc),
                resumen=f"{h.get('points', 0)} puntos, {h.get('num_comments', 0)} comentarios en Hacker News",
            )
        )
    return items[:MAX_POR_FUENTE]


def github(consultas: list[dict]) -> list[Item]:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    hace_una_semana = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    items = []
    for c in consultas:
        q = f"{c['consulta']} created:>{hace_una_semana} stars:>{c.get('min_estrellas', 50)}"
        try:
            repos = _get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": 10},
                headers=headers,
            ).json()["items"]
        except Exception as e:
            log.warning("GitHub '%s' falló: %s", c["consulta"], e)
            continue
        for r in repos:
            items.append(
                Item(
                    titulo=f"Repositorio en tendencia: {r['full_name']}",
                    url=r["html_url"],
                    fuente="GitHub",
                    resumen=limpiar(
                        f"{r.get('description') or ''} — {r['stargazers_count']} estrellas en una semana"
                    ),
                )
            )
    return items


def hugging_face(limite: int) -> list[Item]:
    try:
        modelos = _get(
            "https://huggingface.co/api/models",
            params={"sort": "trendingScore", "direction": -1, "limit": limite},
        ).json()
    except Exception as e:
        log.warning("Hugging Face falló: %s", e)
        return []
    return [
        Item(
            titulo=f"Modelo en tendencia en Hugging Face: {m['id']}",
            url=f"https://huggingface.co/{m['id']}",
            fuente="Hugging Face",
            resumen=f"{m.get('likes', 0)} likes, {m.get('downloads', 0)} descargas. Tipo: {m.get('pipeline_tag') or 'n/d'}",
        )
        for m in modelos
    ]


def deduplicar(items: list[Item]) -> list[Item]:
    vistos_url, vistos_titulo, unicos = set(), set(), []
    for it in items:
        clave_titulo = re.sub(r"\W+", "", it.titulo.lower())[:80]
        if it.id in vistos_url or clave_titulo in vistos_titulo:
            continue
        vistos_url.add(it.id)
        vistos_titulo.add(clave_titulo)
        unicos.append(it)
    return unicos


def recolectar(ruta_config: Path, horas: int = 30) -> list[Item]:
    config = yaml.safe_load(ruta_config.read_text(encoding="utf-8"))
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)

    items: list[Item] = []
    items += rss(config.get("rss", []), desde)
    items += google_news(config.get("google_news", []), desde)
    items += hacker_news(config.get("hacker_news", {}), desde)
    items += github(config.get("github", []))
    items += hugging_face(config.get("hugging_face_trending", 0))

    unicos = deduplicar(items)
    log.info("Recogidas %d noticias (%d tras quitar duplicados)", len(items), len(unicos))
    return unicos
