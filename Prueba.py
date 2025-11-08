

# ==============================
# CAPA LÓGICA - SIMULADOR DE ECOSISTEMAS (DINOSAURIOS)
# ==============================

import random

# ------------------------------
# Clase base: SerVivo
# ------------------------------
class SerVivo:
    """
    Clase base para todo ser vivo dentro del ecosistema.
    Contiene atributos comunes y comportamientos generales.
    """
    def __init__(self, nombre: str, vida: int, energia: int, x: int, y: int):
        self.nombre = nombre
        self.vida = vida
        self.energia = energia
        self.posicion_x = x
        self.posicion_y = y
        self.vivo = True
        