"""
DECOMOBO Conversations — Almacén de historial de conversaciones.
Guarda el historial por número de teléfono en memoria.
"""

import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Conversaciones se limpian después de 24 horas sin actividad
TIMEOUT_HORAS = 24


class ConversationStore:
    def __init__(self):
        self.conversaciones = {}  # telefono -> {mensajes, nombre, manual, ultima_actividad}

    def _inicializar(self, telefono: str, nombre: str = ""):
        """Crea una conversación nueva si no existe."""
        if telefono not in self.conversaciones:
            self.conversaciones[telefono] = {
                "mensajes": [],
                "nombre": nombre,
                "manual": False,
                "ultima_actividad": time.time()
            }

    def agregar_mensaje(self, telefono: str, rol: str, texto: str, nombre: str = ""):
        """
        Agrega un mensaje al historial.
        rol: 'cliente' o 'agente'
        """
        self._inicializar(telefono, nombre)

        conv = self.conversaciones[telefono]

        if nombre:
            conv["nombre"] = nombre

        conv["mensajes"].append({
            "rol": rol,
            "texto": texto,
            "timestamp": time.time()
        })

        conv["ultima_actividad"] = time.time()

        # Limpiar conversaciones viejas periódicamente
        self._limpiar_viejas()

    def obtener_historial(self, telefono: str) -> list:
        """Devuelve el historial de mensajes de una conversación."""
        if telefono not in self.conversaciones:
            return []
        return self.conversaciones[telefono]["mensajes"]

    def es_modo_manual(self, telefono: str) -> bool:
        """Verifica si Alfonso tomó el control de esta conversación."""
        if telefono not in self.conversaciones:
            return False
        return self.conversaciones[telefono]["manual"]

    def activar_manual(self, telefono: str):
        """Alfonso toma el control — el agente deja de responder."""
        self._inicializar(telefono)
        self.conversaciones[telefono]["manual"] = True
        logger.info(f"Modo manual activado para {telefono}")

    def desactivar_manual(self, telefono: str):
        """Alfonso devuelve el control al agente."""
        if telefono in self.conversaciones:
            self.conversaciones[telefono]["manual"] = False
            logger.info(f"Modo manual desactivado para {telefono}")

    def resumen(self) -> list:
        """Devuelve un resumen de todas las conversaciones activas."""
        resumen = []
        for telefono, conv in self.conversaciones.items():
            ultimo_msg = conv["mensajes"][-1] if conv["mensajes"] else None
            resumen.append({
                "telefono": telefono,
                "nombre": conv["nombre"],
                "manual": conv["manual"],
                "total_mensajes": len(conv["mensajes"]),
                "ultimo_mensaje": ultimo_msg["texto"][:80] if ultimo_msg else "",
                "ultimo_rol": ultimo_msg["rol"] if ultimo_msg else "",
                "hace_minutos": round((time.time() - conv["ultima_actividad"]) / 60, 1)
            })

        # Ordenar por más reciente primero
        resumen.sort(key=lambda x: x["hace_minutos"])
        return resumen

    def total_activas(self) -> int:
        """Cuenta conversaciones activas (últimas 24h)."""
        ahora = time.time()
        limite = ahora - (TIMEOUT_HORAS * 3600)
        return sum(1 for c in self.conversaciones.values()
                   if c["ultima_actividad"] > limite)

    def _limpiar_viejas(self):
        """Elimina conversaciones sin actividad en 24+ horas."""
        ahora = time.time()
        limite = ahora - (TIMEOUT_HORAS * 3600)
        viejas = [t for t, c in self.conversaciones.items()
                  if c["ultima_actividad"] < limite]
        for t in viejas:
            del self.conversaciones[t]
            logger.info(f"Conversación limpiada: {t}")
