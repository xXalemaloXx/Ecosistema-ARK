import random
import time
from typing import List, Tuple
import pygame as pg
import sys
import math
import os

"""
Archivo: jurassic_mvc.py
Capas en un mismo archivo:
- Lógica (modelo del ecosistema): Entidad, Animal, Plantas, Ecosistema
- Vista (Pygame): render rápido, HUD y control del jugador (T-Rex)
"""

# =============================
# ----- CAPA DE LÓGICA --------
# =============================

# Tamaño del mundo en pixeles (área jugable)
WORLD_PX_W = 800
WORLD_PX_H = 520

# Balance básico
PROB_REPRODUCE = 0.02
ENERGY_MOVE_COST = 1
ENERGY_AGE_COST = 0
ENERGY_ATTACK_GAIN = 15
ENERGY_PLANT_GAIN = 10
MOVE_SPEED = 2  # pixeles por tick (más lento)

# Umbrales de hambre para IA
HUNGER_THRESHOLD = 50  # si la energía es menor al 50%, buscará comida/cazar
REST_ENERGY_DECAY = 0.015  # gasto de energía al deambular sin hambre
EAT_DURATION_TICKS = 400  # ~16 segundos a 0.04s por tick lógico
ENERGY_DECAY_TICKS = 13  # cada ~0.52s reducir 1 de energía a todos

# Velocidades de comportamiento
SPEED_FLEE = 2.0          # huir del jugador
SPEED_CHASE = 1.7         # perseguir presa
SPEED_SEEK_PLANT = 1.3    # acercarse a plantas
SPEED_PATROL = 0.5        # patrullar (más lento)
SPEED_SEEK_CORPSE = 1.5   # ir hacia cadáver

class Entidad:
    def __init__(self, nombre: str, vida: int, energia: int, x: int, y: int):
        self.nombre = nombre
        self.vida = vida
        self.energia = energia
        self.x = x
        self.y = y

    def esta_vivo(self) -> bool:
        return self.vida > 0 and self.energia > 0

    def posicion(self) -> Tuple[int, int]:
        return (self.x, self.y)

        