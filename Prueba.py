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

class PlantaBase:
    def __init__(self, nombre: str, x: int, y: int, vida: int = 20, energia: int = 0):
        self.nombre = nombre
        self.vida = vida
        self.energia = energia
        self.x = x
        self.y = y

    def esta_viva(self) -> bool:
        return self.vida > 0

    def ser_comida(self):
        self.vida = 0

    def envejecer(self):
        if self.vida <= 0:
            return
        if not hasattr(self, 'edad'):
            self.edad = 0
        if not hasattr(self, 'estado'):
            self.estado = 'brote'
        self.edad += 1
        # Transiciones de estado por edad
        # Tick ~40ms -> 1 min ~1500 ticks
        if self.edad >= 1800:
            self.estado = 'marchita'
        elif self.edad >= 300:
            self.estado = 'adulta'
        # Desaparecer si está muy marchita
        if self.edad >= 2400 and self.estado == 'marchita':
            self.vida = 0

    def intentar_sembrar(self, ecosistema: 'Ecosistema'):
        """Generar una nueva planta cercana si es adulta y con baja probabilidad."""
        if self.vida <= 0 o getattr(self, 'estado', 'brote') != 'adulta':
            return
        # Probabilidad baja de semilla, control de densidad (máximo 60)
        if len(ecosistema.plantas) >= 60:
            return
        if random.random() < 0.02:  # 2% por tick
            # Usar distribución dispersa global para mantener uniformidad
            ecosistema.agregar_planta_dispersada(
                nombre="Helecho",
                attempts=50,
                min_dist=55,
                around=None,
            )

class Planta(PlantaBase):
    def __init__(self, nombre: str, x: int, y: int, nutricion: int = ENERGY_PLANT_GAIN):
        super().__init__(nombre, x=x, y=y, vida=20, energia=0)
        self.nutricion = nutricion
        self.edad = 0
        # Estados: 'brote' -> 'adulta' -> 'marchita'
        self.estado = 'brote'

class Dinosaurio(Entidad):
    def __init__(self, nombre: str, tipo: str, vida: int, energia: int, x: int, y: int):
        super().__init__(nombre, vida, energia, x, y)
        self.tipo = tipo  # "herbivoro" | "carnivoro" | "omnivoro"
        self.edad = 0

    # Movimiento con límites de mapa (en pixeles)
    def mover_arriba(self):
        if self.y > 0:
            self.y = max(0, self.y - MOVE_SPEED)

    def mover_abajo(self):
        if self.y < WORLD_PX_H:
            self.y = min(WORLD_PX_H, self.y + MOVE_SPEED)

    def mover_izquierda(self):
        if self.x > 0:
            self.x = max(0, self.x - MOVE_SPEED)

    def mover_derecha(self):
        if self.x < WORLD_PX_W:
            self.x = min(WORLD_PX_W, self.x + MOVE_SPEED)

    def mover_aleatorio(self):
        direc = random.choice(["arriba", "abajo", "izquierda", "derecha", "quieto"])  # quieto no gasta
        if direc == "arriba": self.mover_arriba()
        elif direc == "abajo": self.mover_abajo()
        elif direc == "izquierda": self.mover_izquierda()
        elif direc == "derecha": self.mover_derecha()

    def envejecer(self):
        self.edad += 1
        self.energia -= ENERGY_AGE_COST
        # Decaimiento periódico de energía: -1 cada ENERGY_DECAY_TICKS (~0.5s)
        if not hasattr(self, '_e_decay'):
            self._e_decay = 0
        self._e_decay += 1
        if self._e_decay >= ENERGY_DECAY_TICKS:
            self.energia -= 1
            self._e_decay = 0
        if self.edad % 20 == 0:
            self.vida -= 1
        if self.energia <= 0 or self.vida <= 0:
            self.morir()

    def morir(self):
        self.vida = 0
        self.energia = 0

    def atacar(self, otro: 'Dinosaurio', ecosistema: 'Ecosistema'):
        if not (self.esta_vivo() y otro.esta_vivo()):
            return
        # Inmunidad del T-Rex jugador
        try:
            if isinstance(otro, TRexJugador):
                return
        except NameError:
            pass
        dano = random.randint(6, 18)
        otro.vida -= dano
        self.energia -= 2
        if not otro.esta_vivo():
            # REGLA: crear cadáver cuando la especie (clase) del atacante es distinta a la de la víctima
            try:
                if type(self).__name__ != type(otro).__name__:
                    corpses.append({'x': otro.x, 'y': MARGIN_TOP + otro.y, 'age': 0, 'max_age': 3000, 'eaten': 0.0, 'skull_timer': 180})
            except Exception:
                pass
            ecosistema.marcar_para_remover(otro)

    def comer(self, objetivo: Entidad, ecosistema: 'Ecosistema'):
        if self.tipo == "herbivoro" and isinstance(objetivo, Planta) and objetivo.vida > 0:
            objetivo.ser_comida()
            self.energia += ENERGY_PLANT_GAIN
            ecosistema.marcar_planta_para_remover(objetivo)
        elif self.tipo == "omnivoro":
            if isinstance(objetivo, Planta) and objetivo.vida > 0:
                # Omnívoros pueden comer plantas, pero NO regeneran energía con plantas
                objetivo.ser_comida()
                ecosistema.marcar_planta_para_remover(objetivo)
            elif isinstance(objetivo, Dinosaurio) and objetivo is not self:
                self.atacar(objetivo, ecosistema)
        elif self.tipo == "carnivoro" and isinstance(objetivo, Dinosaurio) and objetivo is not self:
            self.atacar(objetivo, ecosistema)

    def reproducirse(self, ecosistema: 'Ecosistema'):
        if not self.esta_vivo():
            return
        if self.energia >= 35 and random.random() < PROB_REPRODUCE:
            # Checar límites por especie y globales
            if not ecosistema.puede_reproducir(self):
                return
            self.energia -= 15
            nx = min(WORLD_PX_W, max(0, self.x + random.choice([-15, 0, 15])))
            ny = min(WORLD_PX_H, max(0, self.y + random.choice([-15, 0, 15])))
            cria = type(self)(nx, ny)
            ecosistema.agregar_animal(cria)

    def tick_ia(self, ecosistema: 'Ecosistema'):
        # Default: moverse aleatorio
        self.mover_aleatorio()

# Subclases ejemplo
class Triceratops(Dinosaurio):
    def __init__(self, x, y):
        super().__init__("Triceratops", "herbivoro", vida=110, energia=100, x=x, y=y)

class Stegosaurio(Dinosaurio):
    def __init__(self, x, y):
        super().__init__("Stegosaurio", "herbivoro", vida=105, energia=100, x=x, y=y)

class Velociraptor(Dinosaurio):
    def __init__(self, x, y):
        super().__init__("Velociraptor", "carnivoro", vida=80, energia=100, x=x, y=y)

    def tick_ia(self, ecosistema: 'Ecosistema'):
        # Perseguir herbívoros más cercanos si existen, si no, aleatorio
        objetivos = [a for a in ecosistema.animales if a.tipo in ("herbivoro",) and a.esta_vivo()]
        if objetivos:
            target = min(objetivos, key=lambda a: abs(a.x - self.x) + abs(a.y - self.y))
            if target.x < self.x: self.mover_izquierda()
            elif target.x > self.x: self.mover_derecha()
            if target.y < self.y: self.mover_arriba()
            elif target.y > self.y: self.mover_abajo()
        else:
            self.mover_aleatorio()

class Dilofosaurio(Dinosaurio):
    def __init__(self, x, y):
        super().__init__("Dilofosaurio", "carnivoro", vida=95, energia=100, x=x, y=y)

class Moshops(Dinosaurio):
    def __init__(self, x, y):
        super().__init__("Moshops", "omnivoro", vida=95, energia=100, x=x, y=y)

class TRexJugador(Dinosaurio):
    """T-Rex controlado por el jugador."""
    def __init__(self, x, y):
        super().__init__("T-Rex", "carnivoro", vida=160, energia=100, x=x, y=y)

    # No IA: se mueve por entrada del usuario
    def tick_ia(self, ecosistema: 'Ecosistema'):
        pass

    # No permite reproducción (para evitar múltiples T-Rex)
    def reproducirse(self, ecosistema: 'Ecosistema'):
        return None

    # Inmortal: no envejece ni pierde recursos por tick
    def envejecer(self):
        # Mantener valores en rangos sanos
        if self.vida <= 0:
            self.vida = 160
        if self.energia < 100:
            self.energia = 100

    # Inmortal: no gastar energía al mover
    def mover_arriba(self):
        if self.y > 0:
            self.y = max(0, self.y - MOVE_SPEED)

    def mover_abajo(self):
        if self.y < WORLD_PX_H:
            self.y = min(WORLD_PX_H, self.y + MOVE_SPEED)

    def mover_izquierda(self):
        if self.x > 0:
            self.x = max(0, self.x - MOVE_SPEED)

    def mover_derecha(self):
        if self.x < WORLD_PX_W:
            self.x = min(WORLD_PX_W, self.x + MOVE_SPEED)

    # Ignorar muerte
    def morir(self):
        self.vida = 160
        self.energia = max(self.energia, 70)

class Ecosistema:
    def __init__(self, width=WORLD_PX_W, height=WORLD_PX_H):
        self.width = width
        self.height = height
        self.animales: List[Dinosaurio] = []
        self.plantas: List[Planta] = []
        self._rem_anim: List[Dinosaurio] = []
        self._rem_pla: List[Planta] = []
        self.jugador: TRexJugador | None = None
        # Límites
        self.max_animales = 32
        self.limites_especie = {
            'Triceratops': 8,
            'Stegosaurio': 8,
            'Velociraptor': 6,
            'Dilofosaurio': 4,
            'Moshops': 6,
        }
        # Mapeo especie -> clase
        self.especie_clase = {
            'Triceratops': Triceratops,
            'Stegosaurio': Stegosaurio,
            'Velociraptor': Velociraptor,
            'Dilofosaurio': Dilofosaurio,
            'Moshops': Moshops,
        }

    def contar_especie(self, nombre: str) -> int:
        return sum(1 for a in self.animales if a.esta_vivo() and type(a).__name__ == nombre)

    def puede_reproducir(self, progenitor: Dinosaurio) -> bool:
        # Mantener único T-Rex
        if isinstance(progenitor, TRexJugador):
            return False
        # Límite global
        vivos = sum(1 for a in self.animales if a.esta_vivo())
        if vivos >= self.max_animales:
            return False
        # Límite por especie
        nombre = type(progenitor).__name__
        lim = self.limites_especie.get(nombre, 6)
        if self.contar_especie(nombre) >= lim:
            return False
        return True

    def asegurar_minimos_especie(self, minimo: int = 2):
        # Garantizar al menos 'minimo' individuos por especie (sin contar T-Rex)
        for nombre, clase in self.especie_clase.items():
            cnt = self.contar_especie(nombre)
            faltan = max(0, minimo - cnt)
            if faltan <= 0:
                continue
            # Respetar límites
            lim = self.limites_especie.get(nombre, 6)
            crear = min(faltan, max(0, lim - cnt))
            if crear <= 0:
                continue
            # Checar capacidad global restante
            vivos_tot = sum(1 for a in self.animales if a.esta_vivo())
            disp = max(0, self.max_animales - vivos_tot)
            if disp <= 0:
                break
            crear = min(crear, disp)
            # Punto de referencia: uno existente de la especie o centro del mapa
            ref = None
            for a in self.animales:
                if a.esta_vivo() and type(a).__name__ == nombre:
                    ref = (a.x, a.y)
                    break
            rx, ry = (self.width//2, self.height//2) if ref is None else ref
            for _ in range(crear):
                nx = max(0, min(self.width, int(rx + random.randint(-40, 40))))
                ny = max(0, min(self.height, int(ry + random.randint(-40, 40))))
                try:
                    self.agregar_animal(clase(nx, ny))
                except Exception:
                    pass

def agregar_animal(self, animal: Dinosaurio):
    animal.x = max(0, min(self.width, animal.x))
    animal.y = max(0, min(self.height, animal.y))
    self.animales.append(animal)
    if isinstance(animal, TRexJugador):
        self.jugador = animal

def agregar_planta(self, planta: Planta):
    planta.x = max(0, min(self.width, planta.x))
    planta.y = max(0, min(self.height, planta.y))
    self.plantas.append(planta)

def _dist_sq(self, x1, y1, x2, y2):
    dx = x1 - x2
    dy = y1 - y2
    return dx*dx + dy*dy

def agregar_planta_dispersada(self, nombre: str = "Helecho", attempts: int = 20, min_dist: int = 50,
                               around: tuple | None = None, radius: int = 150):
    """Intentar ubicar una planta manteniendo una distancia mínima a las existentes."""
    min_dist_sq = max(0, min_dist) ** 2
    for _ in range(max(1, attempts)):
        if around is None:
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
        else:
            ax, ay = around
            ang = random.random() * 6.2831853
            r = random.randint(0, max(10, radius))
            x = int(max(0, min(self.width, ax + r * (random.random()*2-1))))
            y = int(max(0, min(self.height, ay + r * (random.random()*2-1))))
        ok = True
        for p in self.plantas:
            if p.vida > 0 and self._dist_sq(x, y, p.x, p.y) < min_dist_sq:
                ok = False
                break
        if ok:
            self.agregar_planta(Planta(nombre, x, y))
            return True
    return False

def marcar_para_remover(self, a: Dinosaurio):
    if a not in self._rem_anim:
        self._rem_anim.append(a)

def marcar_planta_para_remover(self, p: Planta):
    if p not in self._rem_pla:
        self._rem_pla.append(p)

def animales_en(self, x, y) -> List[Dinosaurio]:
    return [a for a in self.animales if a.esta_vivo() and a.x == x and a.y == y]

def plantas_en(self, x, y) -> List[Planta]:
    return [p for p in self.plantas if p.vida > 0 and p.x == x and p.y == y]

def poblar_inicial(self):
    objetivo = 40
    i = 0
    while len(self.plantas) < objetivo and i < objetivo * 3:
        i += 1
        placed = self.agregar_planta_dispersada(f"Helecho_{len(self.plantas)+1}", attempts=60, min_dist=55)
        if not placed:
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            self.agregar_planta(Planta(f"Helecho_{len(self.plantas)+1}", x, y))
    self.agregar_animal(TRexJugador(self.width // 2, self.height // 2))
