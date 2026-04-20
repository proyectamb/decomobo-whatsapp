# DECOMOBO WhatsApp Agent

Agente de IA para WhatsApp Business que responde automáticamente con conocimiento
completo de DECOMOBO: productos, precios, disponibilidad y tono de marca.

## Arquitectura

```
Cliente WhatsApp → Meta Cloud API → Railway (este código) → Claude API → Respuesta
                                         ↓
                                   Notificación a Alfonso
```

## Archivos

- `app.py` — Servidor principal (webhook + lógica)
- `agent.py` — Cerebro con Claude API y conocimiento DECOMOBO
- `conversations.py` — Historial de conversaciones por teléfono
- `requirements.txt` — Dependencias Python
- `Procfile` — Instrucción de arranque para Railway

## Variables de entorno (configurar en Railway)

| Variable | Descripción |
|----------|-------------|
| `WHATSAPP_TOKEN` | Token permanente de WhatsApp Cloud API |
| `WHATSAPP_PHONE_ID` | ID del número de teléfono en Meta |
| `VERIFY_TOKEN` | Token de verificación del webhook (default: decomobo_verify_2026) |
| `NOTIFY_PHONE` | Número de Alfonso para notificaciones (formato: 521XXXXXXXXXX) |
| `ANTHROPIC_API_KEY` | API key de Anthropic (Claude) |

## Deploy

1. Push a GitHub
2. Conectar repo en Railway
3. Configurar variables de entorno
4. Railway despliega automáticamente
