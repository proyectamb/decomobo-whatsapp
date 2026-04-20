"""
DECOMOBO WhatsApp Agent — Servidor principal
Recibe mensajes de WhatsApp Cloud API, procesa con Claude, y responde.
"""

import os
import json
import logging
import threading
import time
import requests
from flask import Flask, request, jsonify
from agent import DecomoboAgent
from conversations import ConversationStore

# ── Configuración ──────────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Variables de entorno (se configuran en Railway)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")           # Token de acceso permanente
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")     # ID del número de teléfono
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "decomobo_verify_2026")
NOTIFY_PHONE = os.environ.get("NOTIFY_PHONE")               # Tu número personal para notificaciones
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ── Componentes ────────────────────────────────────────────────
conversations = ConversationStore()
agent = DecomoboAgent(api_key=ANTHROPIC_API_KEY)

# ── Cargar catálogo desde Hostinger ────────────────────────────
CATALOG_URL = "https://decomobo.mx/productos_web.json"
CATALOG_REFRESH_SECONDS = 3600  # Cada hora

def cargar_catalogo():
    """Descarga productos_web.json desde decomobo.mx y actualiza el agente."""
    try:
        resp = requests.get(CATALOG_URL, timeout=15)
        resp.raise_for_status()
        productos = resp.json()
        agent.actualizar_catalogo(productos)
        logger.info(f"Catálogo cargado: {len(productos)} productos")
    except Exception as e:
        logger.error(f"Error cargando catálogo: {e}")

def refrescar_catalogo_periodico():
    """Hilo que refresca el catálogo cada hora."""
    while True:
        time.sleep(CATALOG_REFRESH_SECONDS)
        cargar_catalogo()

# Cargar al arrancar
cargar_catalogo()

# Iniciar hilo de refresco
hilo_catalogo = threading.Thread(target=refrescar_catalogo_periodico, daemon=True)
hilo_catalogo.start()


# ── Webhook: Verificación (GET) ────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    """
    Meta envía un GET para verificar que el webhook es tuyo.
    Compara el token que tú definiste con el que Meta envía.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verificado correctamente")
        return challenge, 200
    else:
        logger.warning(f"Verificación fallida: token={token}")
        return "Forbidden", 403


# ── Webhook: Mensajes entrantes (POST) ─────────────────────────
@app.route("/webhook", methods=["POST"])
def recibir_mensaje():
    """
    Meta envía un POST cada vez que llega un mensaje a WhatsApp.
    Procesa el mensaje, genera respuesta con Claude, y la envía.
    """
    data = request.get_json()

    # Validar que es un mensaje de WhatsApp
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Ignorar notificaciones de status (enviado, leído, etc.)
        if "messages" not in value:
            return jsonify({"status": "ok"}), 200

        message = value["messages"][0]
        contact = value["contacts"][0]
    except (KeyError, IndexError):
        return jsonify({"status": "ok"}), 200

    # Extraer datos del mensaje
    telefono = message["from"]              # Número del cliente (con código país)
    nombre = contact["profile"]["name"]     # Nombre del contacto
    mensaje_id = message["id"]

    # Solo procesamos mensajes de texto por ahora
    if message["type"] == "text":
        texto_cliente = message["text"]["body"]
    elif message["type"] == "image":
        texto_cliente = "[El cliente envió una imagen]"
    elif message["type"] == "audio":
        texto_cliente = "[El cliente envió un audio]"
    elif message["type"] == "document":
        texto_cliente = "[El cliente envió un documento]"
    else:
        texto_cliente = f"[El cliente envió un mensaje tipo: {message['type']}]"

    logger.info(f"Mensaje de {nombre} ({telefono}): {texto_cliente[:100]}")

    # Marcar como leído
    marcar_como_leido(mensaje_id)

    # Verificar si la conversación está en modo manual (Alfonso tomó el control)
    if conversations.es_modo_manual(telefono):
        logger.info(f"Modo manual activo para {telefono} — agente NO responde")
        return jsonify({"status": "ok"}), 200

    # Agregar mensaje del cliente al historial
    conversations.agregar_mensaje(telefono, "cliente", texto_cliente, nombre=nombre)

    # Generar respuesta con Claude
    historial = conversations.obtener_historial(telefono)
    respuesta = agent.responder(texto_cliente, historial, nombre)

    if respuesta:
        # Agregar respuesta al historial
        conversations.agregar_mensaje(telefono, "agente", respuesta)

        # Enviar por WhatsApp
        enviar_mensaje(telefono, respuesta)
        logger.info(f"Respuesta enviada a {telefono}: {respuesta[:100]}")

    # Notificar a Alfonso (en hilo separado para no bloquear)
    threading.Thread(
        target=notificar_alfonso,
        args=(nombre, telefono, texto_cliente, respuesta),
        daemon=True
    ).start()

    return jsonify({"status": "ok"}), 200


# ── Control manual ─────────────────────────────────────────────
@app.route("/manual/<telefono>", methods=["POST"])
def activar_modo_manual(telefono):
    """Alfonso activa modo manual para una conversación específica."""
    conversations.activar_manual(telefono)
    return jsonify({"status": "manual activado", "telefono": telefono})

@app.route("/manual/<telefono>", methods=["DELETE"])
def desactivar_modo_manual(telefono):
    """Alfonso devuelve el control al agente."""
    conversations.desactivar_manual(telefono)
    return jsonify({"status": "agente reactivado", "telefono": telefono})

@app.route("/conversaciones", methods=["GET"])
def ver_conversaciones():
    """Ver todas las conversaciones activas."""
    return jsonify(conversations.resumen())


# ── Funciones de WhatsApp Cloud API ────────────────────────────
def enviar_mensaje(telefono, texto):
    """Envía un mensaje de texto por WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": texto}
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error enviando mensaje a {telefono}: {e}")


def marcar_como_leido(mensaje_id):
    """Marca un mensaje como leído (las palomitas azules)."""
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": mensaje_id
    }

    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass  # No es crítico si falla


def notificar_alfonso(nombre, telefono, mensaje_cliente, respuesta_agente):
    """Envía notificación a Alfonso cuando llega un mensaje nuevo."""
    if not NOTIFY_PHONE:
        return

    texto = (
        f"🔔 *Nuevo mensaje DECOMOBO*\n\n"
        f"👤 {nombre}\n"
        f"📱 {telefono}\n\n"
        f"💬 _{mensaje_cliente}_\n\n"
        f"🤖 Respuesta del agente:\n{respuesta_agente}\n\n"
        f"Para tomar control, respóndele directo desde WhatsApp Business."
    )

    enviar_mensaje(NOTIFY_PHONE, texto)


# ── Health check ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "productos": agent.total_productos(),
        "conversaciones_activas": conversations.total_activas()
    })


# ── Arrancar ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
