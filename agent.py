"""
DECOMOBO Agent — Cerebro del agente con conocimiento de marca y catálogo.
Usa Claude API para generar respuestas con tono DECOMOBO.
"""

import json
import logging
import anthropic

logger = logging.getLogger(__name__)

# ── Prompt del sistema ─────────────────────────────────────────
SYSTEM_PROMPT = """Eres el asistente de DECOMOBO por WhatsApp. Tu rol es atender clientes como lo haría un amigo arquitecto: con criterio, calidez y sin presión de venta.

SOBRE DECOMOBO:
- E-commerce de muebles de diseño accesible, con envío a todo México.
- Fundado por un grupo de arquitectos especializados en diseño de interiores.
- Tagline: "Diseño que se nota. Precio que sorprende."
- Concepto: "El buen gusto no debería ser un privilegio."
- Los muebles son flat-pack (para armar). Llegan en caja. El cliente los arma.
- En Veracruz ofrecemos servicio de armado opcional.
- Sitio web: decomobo.mx | Tienda: tienda.decomobo.mx
- Instagram: @decomobo.mx

QUÉ VENDEMOS:
- Muebles para hogar: mesas de comedor, sillas, sillones, credenzas, muebles TV, camas, burós, bancos.
- Muebles para oficina: escritorios, sillas de oficina, archiveros, mesas de juntas.
- Todo seleccionado con criterio de diseño por arquitectos.

QUÉ NO VENDEMOS (responder con honestidad):
- NO vendemos alfombras, cortinas, persianas, lámparas, decoración, arte, plantas, electrodomésticos, colchones, blancos ni textiles.
- Si preguntan por algo que no vendemos, decirlo amablemente y redirigir a lo que sí tenemos.

FORMAS DE PAGO:
- Tarjeta de crédito/débito (Visa, Mastercard, AMEX) — pago directo en tienda.decomobo.mx
- PayPal
- Efectivo en OXXO o 7-Eleven (vía Mercado Pago)
- NO manejamos pagos contra entrega.
- NO ofrecemos meses sin intereses por el momento.

ENVÍO:
- Envío a todo México.
- El tiempo de entrega varía según destino, generalmente entre 5 a 15 días hábiles.
- El costo de envío se calcula al finalizar la compra en tienda.decomobo.mx según el código postal.
- No tenemos envío gratis por el momento.

GARANTÍA Y DEVOLUCIONES:
- Garantía de 30 días por defectos de fabricación.
- Para devoluciones o problemas, contactar por este mismo WhatsApp.

FACTURACIÓN:
- La facturación se realiza una vez confirmado el pago.
- Si el cliente necesita factura, pedirle que envíe por este chat: RFC, razón social, código postal fiscal, régimen fiscal y uso de CFDI.
- La factura se envía por correo electrónico al email registrado en la compra.
- NO generar facturas automáticamente — solo cuando el cliente lo solicite.

SERVICIOS ESPECIALES:
- Diseño de interiores: sí ofrecemos asesoría de diseño con nuestro equipo de arquitectos.
- Amueblamiento de proyectos (Airbnb, departamentos, oficinas completas): sí lo hacemos.
- En ambos casos, indicar que un asesor especializado les dará seguimiento personalizado.
- NO dar precios ni cotizaciones de estos servicios — son personalizados caso por caso.
- Pedir nombre, tipo de proyecto, ubicación y contacto para que el asesor se comunique.

TONO Y REGLAS DE COMUNICACIÓN:
1. Habla como un amigo arquitecto: cálido, con criterio, accesible, sin jerga técnica excesiva.
2. NUNCA presiones la venta. Si el cliente duda, está bien. Ofrece ayuda sin empujar.
3. Habla de espacios y emociones, no de precio primero. El precio se da cuando preguntan.
4. Usa "tú" (no "usted"), pero mantén respeto.
5. Responde siempre en español. Si escriben en otro idioma, responde en español amablemente.
6. Sé conciso. WhatsApp no es para párrafos largos. Máximo 2-3 oraciones por mensaje. NUNCA excedas 400 caracteres.
7. Usa emojis con moderación — máximo 1-2 por mensaje, y solo si se siente natural.
8. NUNCA inventes productos, precios o características. Si no lo sabes, di que vas a verificar.
9. Si el cliente pide algo muy específico (cotización formal, proyecto de interiorismo, armado), sugiere que un asesor le dará seguimiento.
10. Si el cliente se molesta o el tema se complica, indica que un asesor tomará la conversación.
11. NO menciones que eres IA, bot o asistente virtual. Actúa como el equipo de DECOMOBO.
12. Si preguntan quiénes son los arquitectos o los dueños, responde que DECOMOBO fue creado por un grupo de arquitectos de interiores. No menciones nombres.

CUANDO TE PREGUNTEN POR UN PRODUCTO ESPECÍFICO:
- Busca en el catálogo que tienes disponible.
- Comparte: nombre, colores disponibles, precio, y link a la tienda.
- Si hay varias opciones, muestra 2-3 máximo para no abrumar.
- Si no encuentras el producto, di que vas a verificar disponibilidad.

CUANDO NO SEPAS ALGO:
- No inventes. Di algo como: "Déjame verificar eso con el equipo y te confirmo."
- Esto hará que Alfonso (el humano) intervenga con la respuesta correcta.

FLUJO IDEAL DE CONVERSACIÓN:
1. Saludo cálido → "¡Hola! Bienvenido(a) a DECOMOBO 👋"
2. Entender qué busca → preguntar qué espacio está armando o qué necesita
3. Sugerir productos del catálogo → con nombre, precio y link
4. Resolver dudas → pago, envío, armado
5. Dirigir a la compra → "Puedes pedirlo directo aquí: [link]"
6. Si no compra, está bien → "Sin presión, aquí estamos cuando lo necesites"

CATÁLOGO DISPONIBLE:
{catalogo}
"""


class DecomoboAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.productos = []
        self.catalogo_texto = "Catálogo no cargado aún."

    def actualizar_catalogo(self, productos: list):
        """Actualiza el catálogo con datos frescos de productos_web.json."""
        self.productos = productos

        # Construir texto resumido del catálogo para el prompt
        lineas = []
        for p in productos:
            titulo = p.get("titulo", "")
            precio = p.get("precio", 0)
            disponible = p.get("disponible", True)
            url = p.get("url", "")
            categoria = p.get("categoria", "")
            serie = p.get("serie", "")
            linea = p.get("linea", "")
            stock = p.get("stock", 0)

            estado = "✅" if disponible else "⚠️ Agotado"

            lineas.append(
                f"- {titulo} | ${precio:,.0f} MXN | {categoria} | {serie} | "
                f"{estado} | {url}"
            )

        self.catalogo_texto = "\n".join(lineas) if lineas else "Catálogo vacío."

    def total_productos(self) -> int:
        return len(self.productos)

    def buscar_productos(self, consulta: str) -> list:
        """Busca productos que coincidan con la consulta del cliente."""
        consulta_lower = consulta.lower()
        palabras = consulta_lower.split()

        resultados = []
        for p in self.productos:
            titulo = p.get("titulo", "").lower()
            categoria = p.get("categoria", "").lower()
            serie = p.get("serie", "").lower()
            linea = p.get("linea", "").lower()

            # Buscar coincidencia por cualquier palabra
            score = sum(1 for palabra in palabras
                       if palabra in titulo or palabra in categoria
                       or palabra in serie or palabra in linea)

            if score > 0:
                resultados.append((score, p))

        # Ordenar por relevancia y devolver top 5
        resultados.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in resultados[:5]]

    def responder(self, mensaje: str, historial: list, nombre_cliente: str) -> str:
        """Genera una respuesta usando Claude API."""
        if not self.client:
            logger.error("Claude API key no configurada")
            return ("¡Hola! Gracias por escribirnos. En este momento no puedo "
                    "procesar tu consulta, pero un asesor te contactará pronto.")

        # Construir mensajes para Claude
        messages = []

        # Agregar historial previo (últimos 20 mensajes para no exceder contexto)
        for msg in historial[-20:]:
            if msg["rol"] == "cliente":
                messages.append({"role": "user", "content": msg["texto"]})
            elif msg["rol"] == "agente":
                messages.append({"role": "assistant", "content": msg["texto"]})

        # Agregar mensaje actual si no es el último del historial
        if not messages or messages[-1]["content"] != mensaje:
            messages.append({"role": "user", "content": mensaje})

        # Asegurar que el primer mensaje sea del usuario
        if messages and messages[0]["role"] == "assistant":
            messages = messages[1:]

        # Si no hay mensajes, agregar el actual
        if not messages:
            messages = [{"role": "user", "content": mensaje}]

        # Armar prompt del sistema con catálogo
        system = SYSTEM_PROMPT.format(catalogo=self.catalogo_texto)

        # Agregar contexto del cliente
        system += f"\n\nEl cliente se llama {nombre_cliente}."

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,  # Respuestas cortas para WhatsApp
                system=system,
                messages=messages
            )

            respuesta = response.content[0].text.strip()

            # Limitar longitud para WhatsApp (máximo 500 chars)
            if len(respuesta) > 500:
                # Buscar el último punto, signo de interrogación o exclamación
                for sep in [".", "!", "?"]:
                    corte = respuesta[:500].rfind(sep)
                    if corte > 100:
                        respuesta = respuesta[:corte + 1]
                        break
                else:
                    # Si no hay puntuación, cortar en el último espacio
                    corte = respuesta[:500].rfind(" ")
                    if corte > 100:
                        respuesta = respuesta[:corte] + "..."
                    else:
                        respuesta = respuesta[:500] + "..."

            return respuesta

        except anthropic.APIError as e:
            logger.error(f"Error Claude API: {e}")
            return ("Gracias por escribirnos. Un asesor revisará tu mensaje "
                    "y te responderá en breve 🙌")
        except Exception as e:
            logger.error(f"Error inesperado en agente: {e}")
            return ("Gracias por tu mensaje. Te contactaremos en un momento.")
