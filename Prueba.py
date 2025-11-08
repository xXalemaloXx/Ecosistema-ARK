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

    # ------------------------------
    # Métodos de movimiento
    # ------------------------------
    def mover_arriba(self):
        if self.vivo:
            self.posicion_y -= 1
            self.energia -= 2

    def mover_abajo(self):
        if self.vivo:
            self.posicion_y += 1
            self.energia -= 2

    def mover_izquierda(self):
        if self.vivo:
            self.posicion_x -= 1
            self.energia -= 2

    def mover_derecha(self):
        if self.vivo:
            self.posicion_x += 1
            self.energia -= 2


