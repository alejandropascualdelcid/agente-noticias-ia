# 🤖 Agente de Noticias IA

Cada mañana revisa decenas de fuentes sobre inteligencia artificial y te manda por **Telegram** las noticias más importantes del día, resumidas en español y listas para convertirlas en contenido para Instagram y TikTok.

## Qué hace

1. **Recoge** noticias de las últimas 30 horas de:
   - Blogs oficiales: OpenAI, Google DeepMind, Google AI, Hugging Face
   - Medios: TechCrunch, The Verge, VentureBeat, MIT Tech Review, Ars Technica, Wired, Xataka…
   - Google News: Anthropic/Claude, ElevenLabs, empresas chinas (DeepSeek, Qwen, Kimi…), regulación, Musk/xAI, Sam Altman, MCPs…
   - Comunidades: Reddit (r/LocalLLaMA, r/singularity, r/OpenAI, r/ClaudeAI) y Hacker News
   - GitHub (repos nuevos que están explotando, MCPs) y modelos en tendencia en Hugging Face
2. **Analiza** todo con Claude: quita duplicados, agrupa lo que cuenta lo mismo, descarta el ruido y elige el top 12.
3. **Envía** a Telegram cada noticia con:
   - titular y resumen en español
   - 💡 por qué importa
   - ✅ confirmado / ⚠️ rumor / 🔜 próximamente
   - 🔥 si tiene mucho potencial viral
   - 🎣 un gancho listo para empezar un Reel
   - enlaces a las fuentes originales
4. **Guarda** cada resumen en `data/resumenes/` (en `.json` y `.md`) para no repetir noticias y para la fase de creación de contenido.

Todas las fuentes se pueden editar en [`config/fuentes.yaml`](config/fuentes.yaml).

## Puesta en marcha (unos 15 minutos)

### 1. Crea tu bot de Telegram
1. En Telegram, abre **@BotFather** y envía `/newbot`.
2. Elige un nombre y un usuario (tiene que acabar en `bot`).
3. BotFather te da un **token** del tipo `123456789:ABC...`. Guárdalo: es tu `TELEGRAM_BOT_TOKEN`.
4. Abre el chat con tu bot nuevo y envíale cualquier mensaje (por ejemplo «hola»).

### 2. Averigua tu chat ID
Abre en el navegador esta dirección, poniendo tu token:

```
https://api.telegram.org/bot<TU_TOKEN>/getUpdates
```

Busca `"chat":{"id": 123456789` en lo que aparece. Ese número es tu `TELEGRAM_CHAT_ID`.
(Si lo prefieres, también puedes ejecutar `TELEGRAM_BOT_TOKEN=... python -m agente.obtener_chat_id`.)

### 3. Consigue una clave de la API de Claude
1. Entra en <https://console.anthropic.com> y crea una cuenta.
2. En **Billing**, añade saldo (con 5 $ tienes para empezar de sobra) y pon un **límite de gasto mensual** para dormir tranquilo.
3. En **API Keys**, crea una clave. Es tu `ANTHROPIC_API_KEY`.

### 4. Guarda las claves en GitHub
En este repositorio: **Settings → Secrets and variables → Actions → New repository secret**, y crea estos tres:

| Nombre | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | la clave de Claude |
| `TELEGRAM_BOT_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | tu chat ID |

### 5. Pruébalo
**Actions → Resumen diario de IA → Run workflow**. En un par de minutos te llega el resumen a Telegram.
A partir de ahí se envía solo todos los días a las 10:00 (hora de Madrid).

## Ajustes opcionales

En **Settings → Secrets and variables → Actions → Variables** puedes crear:

| Variable | Para qué | Por defecto |
|---|---|---|
| `HORA_ENVIO` | Hora de envío (hora de Madrid, entre 9 y 12) | `10` |
| `NUMERO_NOTICIAS` | Cuántas noticias incluir | `12` |
| `MODELO_CLAUDE` | Modelo de Claude que se usa | `claude-opus-5-5` |

## Costes aproximados

| Servicio | Coste |
|---|---|
| GitHub Actions | Gratis (unos 5 minutos al día) |
| Telegram | Gratis |
| API de Claude con `claude-opus-5-5` | ~0,20 $ al día ≈ **5–7 $ al mes** |
| API de Claude con `claude-haiku-5-5` | ≈ **menos de 1 $ al mes** (la selección es algo menos fina) |

Así quedan unos 13–15 € libres para la voz de ElevenLabs (plan Starter, 5 $/mes) en la fase de vídeo. Los costes de Claude son estimaciones: tras unos días, revisa el gasto real en la consola de Anthropic.

## Probar en tu ordenador (opcional)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python -m agente.main --prueba    # muestra el resumen por pantalla sin enviarlo
```

## Próximas fases

- **Fase 2:** botón «Crear contenido» en cada noticia del Telegram: ganchos, guion de Reel de 30–60 s, carrusel de 5–7 diapositivas, pie de publicación y hashtags.
- **Fase 3:** vídeo vertical automático con voz IA y subtítulos animados.
- **Fase 4:** identidad de marca (nombre, colores, plantillas) y métricas.
