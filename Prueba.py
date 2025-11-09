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
        if self.vida <= 0 or getattr(self, 'estado', 'brote') != 'adulta':
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
        if not (self.esta_vivo() and otro.esta_vivo()):
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

    # --- Utilidades de distribución ---
    def _dist_sq(self, x1, y1, x2, y2):
        dx = x1 - x2
        dy = y1 - y2
        return dx*dx + dy*dy

    def agregar_planta_dispersada(self, nombre: str = "Helecho", attempts: int = 20, min_dist: int = 50,
                                   around: tuple | None = None, radius: int = 150):
        """Intentar ubicar una planta manteniendo una distancia mínima a las existentes.
        - around=(x,y): si se pasa, intenta colocar alrededor de ese punto dentro de 'radius'.
        - si no, distribuye global en el mapa.
        """
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
        # Plantas de fondo (distribución dispersa) mínimo 40
        objetivo = 40
        i = 0
        while len(self.plantas) < objetivo and i < objetivo * 3:
            i += 1
            placed = self.agregar_planta_dispersada(f"Helecho_{len(self.plantas)+1}", attempts=60, min_dist=55)
            if not placed:
                # Fallback aleatorio si no encuentra hueco
                x = random.randint(0, self.width)
                y = random.randint(0, self.height)
                self.agregar_planta(Planta(f"Helecho_{len(self.plantas)+1}", x, y))
        # Solo jugador (T-Rex)
        self.agregar_animal(TRexJugador(self.width // 2, self.height // 2))

    def limpiar_muertos(self):
        for a in list(self._rem_anim):
            if a in self.animales:
                try:
                    self.animales.remove(a)
                except ValueError:
                    pass
            try:
                self._rem_anim.remove(a)
            except ValueError:
                pass
        for p in list(self._rem_pla):
            if p in self.plantas:
                try:
                    self.plantas.remove(p)
                except ValueError:
                    pass
            try:
                self._rem_pla.remove(p)
            except ValueError:
                pass
        # hard clean
        self.animales = [a for a in self.animales if a.esta_vivo()]
        self.plantas = [p for p in self.plantas if p.vida > 0]

    def interacciones_en_pos(self, x, y):
        animales = self.animales_en(x, y)
        plantas = self.plantas_en(x, y)
        # comer plantas
        if plantas and animales:
            for a in animales:
                if a.tipo in ("herbivoro", "omnivoro"):
                    obj = random.choice(plantas)
                    a.comer(obj, self)
                    if obj.vida <= 0 and obj in plantas:
                        try:
                            plantas.remove(obj)
                        except ValueError:
                            pass
        # peleas
        if len(animales) >= 2:
            atacante = random.choice(animales)
            candidatos = [b for b in animales if b is not atacante]
            if candidatos:
                victima = random.choice(candidatos)
                atacante.comer(victima, self)  # para delegar a atacar si procede

    def paso(self):
        # IA
        for a in list(self.animales):
            if not a.esta_vivo():
                self.marcar_para_remover(a)
                continue
            if not isinstance(a, TRexJugador):
                a.tick_ia(self)
            a.envejecer()
        # Ciclo de vida de plantas: envejecer y posibles semillas
        for p in list(self.plantas):
            if p.vida > 0:
                p.envejecer()
                p.intentar_sembrar(self)
        # interacciones por posición
        # Posiciones discretas ya no se usan para colisiones (movimiento libre),
        # se omiten interacciones por celda.
        posiciones = set()
        for (x, y) in posiciones:
            pass
        # reproducción
        for a in list(self.animales):
            if a.esta_vivo():
                a.reproducirse(self)
        # Asegurar mínimos por especie (p. ej. 2)
        self.asegurar_minimos_especie(minimo=2)
        # Recorte si excede el máximo global (no tocar T-Rex)
        vivos = [a for a in self.animales if a.esta_vivo() and not isinstance(a, TRexJugador)]
        excede = max(0, len([a for a in self.animales if a.esta_vivo()]) - self.max_animales)
        if excede > 0:
            # Ordenar por menor energía y mayor edad para recortar primero los más débiles
            vivos.sort(key=lambda a: (a.energia, -a.edad))
            for i in range(excede):
                if i < len(vivos):
                    self.marcar_para_remover(vivos[i])
            self.limpiar_muertos()
        # limpieza
        self.limpiar_muertos()
        # Mantener entre 40 y 60 plantas: rellenar y limitar
        min_obj = 40
        max_obj = 60
        # Top-up a mínimo
        refill_attempts = 0
        while len(self.plantas) < min_obj and refill_attempts < min_obj * 4:
            refill_attempts += 1
            placed = self.agregar_planta_dispersada("Helecho", attempts=60, min_dist=55)
            if not placed:
                # Fallback si no encuentra hueco tras varios intentos
                self.agregar_planta(Planta("Helecho", random.randint(0, self.width), random.randint(0, self.height)))
        # Si excede el máximo, remover las más viejas/marchitas primero
        if len(self.plantas) > max_obj:
            # Ordenar por prioridad de remoción: marchitas primero, luego mayor edad
            vivas = [p for p in self.plantas if p.vida > 0]
            vivas.sort(key=lambda p: (0 if p.estado == 'marchita' else 1, -p.edad))
            excedente = len(self.plantas) - max_obj
            to_remove = []
            for p in vivas:
                if excedente <= 0:
                    break
                to_remove.append(p)
                excedente -= 1
            for p in to_remove:
                self.marcar_planta_para_remover(p)
            self.limpiar_muertos()

# =============================
# ----- CAPA DE VISTA (PG) ----
# =============================

CELL_SIZE = 20
MARGIN_TOP = 40
WINDOW_W = WORLD_PX_W
WINDOW_H = MARGIN_TOP + WORLD_PX_H

# --- Sistemas de efectos y cadáveres ---
corpses = []  # {'x','y','age','max_age','eaten','skull_timer'}
hit_effects = []  # golpes del jugador
eat_effects = []  # efectos al comer
ai_attack_effects = []  # efectos de ataque IA

# --- Sprites ---
SPRITES: dict[str, pg.Surface] = {}

def _safe_load(path: str, size: tuple[int,int] | None = None) -> pg.Surface | None:
    try:
        img = pg.image.load(path)
        img = img.convert_alpha()
        if size is not None:
            img = pg.transform.smoothscale(img, size)
        return img
    except Exception:
        return None

def _make_fallback(color: tuple[int,int,int], size: tuple[int,int]) -> pg.Surface:
    surf = pg.Surface(size, pg.SRCALPHA)
    pg.draw.rect(surf, color, surf.get_rect(), border_radius=4)
    return surf

def _load_sprites():
    base = os.path.join(os.path.dirname(__file__), 'assets')
    mapping = {
        'TRexJugador': ('trex.png', (34, 34), (230,70,70)),
        'Triceratops': ('triceratops.png', (30, 30), (60,160,60)),
        'Stegosaurio': ('stegosaurio.png', (30, 30), (60,160,60)),
        'Velociraptor': ('velociraptor.png', (28, 28), (200,80,80)),
        'Dilofosaurio': ('dilofosaurio.png', (28, 28), (200,80,80)),
        'Moshops': ('moshops.png', (28, 28), (200,170,90)),
        'Planta_brote': ('plant_brote.png', (14, 14), (90,200,90)),
        'Planta_adulta': ('plant_adulta.png', (18, 18), (60,160,60)),
        'Planta_marchita': ('plant_marchita.png', (12, 12), (150,120,80)),
        'Cadaver': ('cadaver.png', (26, 18), (120,60,40)),
    }
    for key, (fname, size, color) in mapping.items():
        path = os.path.join(base, fname)
        img = _safe_load(path, size)
        if img is None:
            img = _make_fallback(color, size)
        SPRITES[key] = img

def _dist(ax, ay, bx, by):
    dx = bx - ax; dy = by - ay
    return math.hypot(dx, dy)

def _spawn_hit_effect(x, y, life=10):
    hit_effects.append({'x': x, 'y': y, 'life': life})

def _render_hit_effects(surface):
    remove = []
    for e in hit_effects:
        r = max(4, 16 - (10 - e['life']))
        pg.draw.circle(surface, (255,0,0), (int(e['x']), int(e['y'])), r, 2)
        pg.draw.circle(surface, (255,255,255), (int(e['x']), int(e['y'])), max(2, r//2), 1)
        e['life'] -= 1
        if e['life'] <= 0:
            remove.append(e)
    for e in remove:
        hit_effects.remove(e)

def _spawn_eat_effect(x, y, life=12):
    eat_effects.append({'x': x, 'y': y, 'life': life})

def _render_eat_effects(surface):
    remove = []
    for e in eat_effects:
        phase = (12 - e['life'])
        r = 6 + (phase % 6)
        pg.draw.circle(surface, (255,165,0), (int(e['x']), int(e['y'])), r, 2)
        e['life'] -= 1
        if e['life'] <= 0:
            remove.append(e)
    for e in remove:
        eat_effects.remove(e)

def _spawn_ai_attack_effect(x, y, life=10, spokes=8):
    ai_attack_effects.append({'x': x, 'y': y, 'life': life, 'spokes': spokes})

def _render_ai_attack_effects(surface):
    remove = []
    for e in ai_attack_effects:
        phase = (10 - e['life'])
        max_r = 18
        r = 6 + int((phase / 10) * max_r)
        cx, cy = int(e['x']), int(e['y'])
        for i in range(e['spokes']):
            ang = (i / e['spokes']) * math.tau
            x2 = cx + int(r * math.cos(ang))
            y2 = cy + int(r * math.sin(ang))
            pg.draw.line(surface, (255,0,0), (cx, cy), (x2, y2), 2)
        e['life'] -= 1
        if e['life'] <= 0:
            remove.append(e)
    for e in remove:
        ai_attack_effects.remove(e)

 

def _update_corpses():
    remove = []
    for c in corpses:
        c['age'] += 1
        if c['skull_timer'] > 0:
            c['skull_timer'] -= 1
        if c['eaten'] >= 1.0 or c['age'] >= c['max_age']:
            remove.append(c)
    for c in remove:
        corpses.remove(c)

def _draw_skull(surface, x, y):
    pg.draw.circle(surface, (255,255,255), (x, y), 8)
    pg.draw.circle(surface, (0,0,0), (x-3, y-2), 2)
    pg.draw.circle(surface, (0,0,0), (x+3, y-2), 2)
    pg.draw.rect(surface, (255,255,255), pg.Rect(x-5, y+3, 10, 3))

def _render_corpses(surface):
    for c in corpses:
        size = max(8, int(20 * (1.0 - 0.3*c['eaten'])))
        cx, cy = int(c['x']), int(c['y'])
        spr = SPRITES.get('Cadaver')
        if spr is not None:
            rect = spr.get_rect(center=(cx, cy))
            surface.blit(spr, rect)
        else:
            rect = pg.Rect(cx-size, cy-size//2, size*2, int(size))
            pg.draw.ellipse(surface, (120,60,40), rect)
        bar_w, bar_h = 24, 4
        bx = cx - bar_w//2
        by = cy - size - 8
        pg.draw.rect(surface, (160,160,160), pg.Rect(bx, by, bar_w, bar_h), border_radius=2)
        pg.draw.rect(surface, (255,0,0), pg.Rect(bx, by, int(bar_w * c['eaten']), bar_h), border_radius=2)
        if c['skull_timer'] > 0:
            _draw_skull(surface, cx, cy - size - 14)

def ai_eat_corpses(animal):
    if getattr(animal, 'tipo', '') not in ('carnivoro', 'omnivoro'):
        return False
    EAT_DURATION_FRAMES = EAT_DURATION_TICKS
    E_PER_TICK = 40.0 / EAT_DURATION_FRAMES
    for c in corpses:
        if c['eaten'] >= 1.0:
            continue
        if _dist(animal.x, MARGIN_TOP + animal.y, c['x'], c['y']) < 36:
            c['eaten'] += 1.0 / EAT_DURATION_FRAMES
            animal.energia += E_PER_TICK
            _spawn_eat_effect(c['x'], c['y'])
            if c['eaten'] >= 1.0:
                c['eaten'] = 1.0
                c['age'] = c['max_age']
            return True
    return False

def _attempt_attack(attacker: 'Dinosaurio', victim: 'Dinosaurio', eco: 'Ecosistema'):
    if not hasattr(attacker, '_atk_cd'):
        attacker._atk_cd = 0
    if attacker._atk_cd > 0:
        attacker._atk_cd -= 1
        return
    if _dist(attacker.x, attacker.y, victim.x, victim.y) < 26:
        attacker.atacar(victim, eco)
        attacker._atk_cd = 30
        if not isinstance(attacker, TRexJugador) and getattr(attacker, 'tipo', '') == 'carnivoro':
            _spawn_ai_attack_effect(victim.x, MARGIN_TOP + int(victim.y) - 40)

def actualizar_ia(eco: 'Ecosistema', jugador: 'TRexJugador'):
    # Agrupar por especie: centroides para moverse en grupo
    especie_pos = {}
    especie_count = {}
    for a in eco.animales:
        if not a.esta_vivo() or isinstance(a, TRexJugador):
            continue
        key = type(a).__name__
        especie_pos[key] = (
            especie_pos.get(key, (0.0, 0.0))[0] + a.x,
            especie_pos.get(key, (0.0, 0.0))[1] + a.y,
        )
        especie_count[key] = especie_count.get(key, 0) + 1
    centroides = {}
    for k, (sx, sy) in especie_pos.items():
        c = especie_count[k]
        if c > 0:
            centroides[k] = (sx / c, sy / c)

    # Herbívoros: huyen del T-Rex y comen plantas. Todos: ligera atracción al centro del grupo.
    for a in list(eco.animales):
        if a is jugador or not a.esta_vivo():
            continue
        t = getattr(a, 'tipo', '')
        # muerte natural por energía
        if a.energia <= 0:
            a.morir()
            continue
        # Movimiento de agrupamiento (suave)
        key = type(a).__name__
        if key in centroides:
            cx, cy = centroides[key]
            dxg, dyg = cx - a.x, cy - a.y
            dg = math.hypot(dxg, dyg) or 1
            if dg > 25:  # si está lejos del grupo, acércate un poco
                a.x = max(0, min(WORLD_PX_W, a.x + 0.6 * dxg/dg))
                a.y = max(0, min(WORLD_PX_H, a.y + 0.6 * dyg/dg))

        if t == 'herbivoro':
            # Huir del T-Rex si está cerca
            if _dist(a.x, a.y, jugador.x, jugador.y) < 120:
                dx = a.x - jugador.x; dy = a.y - jugador.y
                d = math.hypot(dx, dy) or 1
                a.x = max(0, min(WORLD_PX_W, a.x + SPEED_FLEE * dx/d))
                a.y = max(0, min(WORLD_PX_H, a.y + SPEED_FLEE * dy/d))
                a.energia -= 0.0
            else:
                if a.energia < HUNGER_THRESHOLD:
                    # Buscar planta más cercana (con hambre)
                    vivos = [p for p in eco.plantas if p.vida > 0]
                    if vivos:
                        obj = min(vivos, key=lambda p: _dist(a.x, a.y, p.x, p.y))
                        dx = obj.x - a.x; dy = obj.y - a.y
                        d = math.hypot(dx, dy) or 1
                        a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_PLANT * dx/d))
                        a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_PLANT * dy/d))
                        a.energia -= 0.0
                        if _dist(a.x, a.y, obj.x, obj.y) < 16 and obj.vida > 0:
                            a.comer(obj, eco)
                    else:
                        # vagar si no hay comida
                        a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                        a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                        a.energia -= 0.0
                else:
                    # Saciado: deambular conservando energía
                    a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                    a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                    a.energia -= 0.0
        elif t == 'carnivoro':
            # Prioridad absoluta: si hay cadáver (cerca o no), ve hacia él y cómelo si está al alcance
            # 1) Comer si ya está cerca
            if ai_eat_corpses(a):
                continue
            # 2) Si existe cualquier cadáver no consumido, moverse hacia el más cercano
            target_corpse = None; best_d = 1e9
            for c in corpses:
                if c['eaten'] >= 1.0:
                    continue
                d = _dist(a.x, MARGIN_TOP + a.y, c['x'], c['y'])
                if d < best_d:
                    best_d = d; target_corpse = c
            if target_corpse is not None:
                dx = target_corpse['x'] - a.x
                dy = target_corpse['y'] - (MARGIN_TOP + a.y)
                d = math.hypot(dx, dy) or 1
                a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_CORPSE * dx/d))
                a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_CORPSE * dy/d))
                # intentar comer en el próximo ciclo si se acerca lo suficiente
                ai_eat_corpses(a)
                continue
            if a.energia <= HUNGER_THRESHOLD:
                # Con hambre: priorizar cadáver cercano, luego cazar
                presas = [h for h in eco.animales if getattr(h, 'tipo','') in ('herbivoro','omnivoro') and h.esta_vivo()]
                if presas:
                    obj = min(presas, key=lambda h: _dist(a.x, a.y, h.x, h.y))
                    dx = obj.x - a.x; dy = obj.y - a.y
                    d = math.hypot(dx, dy) or 1
                    a.x = max(0, min(WORLD_PX_W, a.x + SPEED_CHASE * dx/d))
                    a.y = max(0, min(WORLD_PX_H, a.y + SPEED_CHASE * dy/d))
                    a.energia -= 0.0
                    if _dist(a.x, a.y, obj.x, obj.y) < 22:
                        _attempt_attack(a, obj, eco)
            else:
                # Saciado: patrullar/deambular suave y comer si pasa por encima de un cadáver
                a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.energia -= 0.0
                # Si patrullando encuentra cadáver, comer
                ai_eat_corpses(a)
        else:  # omnivoro
            # Prioridad absoluta: cadáver primero (cerca o no)
            if ai_eat_corpses(a):
                continue
            target_corpse = None; best_d = 1e9
            for c in corpses:
                if c['eaten'] >= 1.0:
                    continue
                d = _dist(a.x, MARGIN_TOP + a.y, c['x'], c['y'])
                if d < best_d:
                    best_d = d; target_corpse = c
            if target_corpse is not None:
                dx = target_corpse['x'] - a.x
                dy = target_corpse['y'] - (MARGIN_TOP + a.y)
                d = math.hypot(dx, dy) or 1
                a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_CORPSE * dx/d))
                a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_CORPSE * dy/d))
                ai_eat_corpses(a)
                continue
            if a.energia < HUNGER_THRESHOLD:
                # Con hambre: buscar plantas
                vivos = [p for p in eco.plantas if p.vida > 0]
                if vivos:
                    obj = min(vivos, key=lambda p: _dist(a.x, a.y, p.x, p.y))
                    dx = obj.x - a.x; dy = obj.y - a.y
                    d = math.hypot(dx, dy) or 1
                    a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_PLANT * dx/d))
                    a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_PLANT * dy/d))
                    a.energia -= 0.0
                    if _dist(a.x, a.y, obj.x, obj.y) < 16 and obj.vida > 0:
                        a.comer(obj, eco)
            else:
                # Saciado: patrullar
                a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.energia -= 0.0


def resolver_colisiones(eco: 'Ecosistema'):
    """Evita solapes empujando pares de dinosaurios separados por un radio mínimo."""
    vivos = [a for a in eco.animales if a.esta_vivo()]
    if len(vivos) < 2:
        return
    min_d = 24.0  # diámetro mínimo ~ 2*radio de colisión (12px)
    for i in range(len(vivos)):
        a = vivos[i]
        for j in range(i+1, len(vivos)):
            b = vivos[j]
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.hypot(dx, dy)
            if dist < 1e-6:
                # separar direcciones aleatorias pequeñas para evitar división por cero
                ang = random.random() * math.tau
                dx = math.cos(ang)
                dy = math.sin(ang)
                dist = 1.0
            if dist < min_d:
                overlap = (min_d - dist) * 0.5
                nx = dx / dist
                ny = dy / dist
                # Empujar ambos en direcciones opuestas
                a.x = max(0, min(WORLD_PX_W, a.x - nx * overlap))
                a.y = max(0, min(WORLD_PX_H, a.y - ny * overlap))
                b.x = max(0, min(WORLD_PX_W, b.x + nx * overlap))
                b.y = max(0, min(WORLD_PX_H, b.y + ny * overlap))

def run_game():
    pg.init()
    screen = pg.display.set_mode((WINDOW_W, WINDOW_H))
    pg.display.set_caption("Jurassic MVC - T-Rex Jugador (Pygame)")
    clock = pg.time.Clock()
    font = pg.font.SysFont("consolas", 16)
    _load_sprites()

    eco = Ecosistema()
    eco.poblar_inicial()
    # Spawns adicionales con separación inicial entre herbívoros y carnívoros
    # Definir zonas: herbívoros a la izquierda, carnívoros a la derecha, buffer central
    SEP_BUFFER = 80
    LEFT_X_MIN, LEFT_X_MAX = 50, max(50, WORLD_PX_W // 2 - SEP_BUFFER)
    RIGHT_X_MIN, RIGHT_X_MAX = min(WORLD_PX_W - 50, WORLD_PX_W // 2 + SEP_BUFFER), WORLD_PX_W - 50
    Y_MIN, Y_MAX = 80, WORLD_PX_H - 50

    # Herbívoros en manadas (lado izquierdo)
    for _ in range(4):
        eco.agregar_animal(Triceratops(
            random.randint(LEFT_X_MIN, LEFT_X_MAX),
            random.randint(Y_MIN, Y_MAX)
        ))
    for _ in range(3):
        eco.agregar_animal(Stegosaurio(
            random.randint(LEFT_X_MIN, LEFT_X_MAX),
            random.randint(Y_MIN, Y_MAX)
        ))

    # Carnívoros (lado derecho)
    for _ in range(2):
        eco.agregar_animal(Velociraptor(
            random.randint(RIGHT_X_MIN, RIGHT_X_MAX),
            random.randint(Y_MIN, Y_MAX)
        ))
    eco.agregar_animal(Dilofosaurio(
        random.randint(RIGHT_X_MIN, RIGHT_X_MAX),
        random.randint(Y_MIN, Y_MAX)
    ))

    # Omnívoros: cerca del centro pero fuera del buffer exacto
    MID_LEFT = max(50, WORLD_PX_W // 2 - SEP_BUFFER - 40)
    MID_RIGHT = min(WORLD_PX_W - 50, WORLD_PX_W // 2 + SEP_BUFFER + 40)
    omni_x = random.choice([
        random.randint(LEFT_X_MIN, min(LEFT_X_MAX, MID_LEFT)),
        random.randint(max(MID_RIGHT, RIGHT_X_MIN), RIGHT_X_MAX)
    ])
    eco.agregar_animal(Moshops(omni_x, random.randint(Y_MIN, Y_MAX)))

    SIM_DT = 0.04  # 40 ms por paso lógico
    sim_accum = 0.0
    running = True
    player_atk_cd = 0
    while running:
        dt = clock.tick(120) / 1000.0  # limitar a ~120 FPS
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                running = False

        # Entrada (WASD + flechas, movimiento diagonal normalizado)
        keys = pg.key.get_pressed()
        trex = eco.jugador
        if trex and trex.esta_vivo():
            dx = dy = 0
            if keys[pg.K_a] or keys[pg.K_LEFT]:
                dx -= 1
            if keys[pg.K_d] or keys[pg.K_RIGHT]:
                dx += 1
            if keys[pg.K_w] or keys[pg.K_UP]:
                dy -= 1
            if keys[pg.K_s] or keys[pg.K_DOWN]:
                dy += 1
            if dx != 0 or dy != 0:
                if dx != 0 and dy != 0:
                    step = int(MOVE_SPEED / 1.41421356) or 1
                else:
                    step = MOVE_SPEED
                trex.x = max(0, min(WORLD_PX_W, trex.x + dx * step))
                trex.y = max(0, min(WORLD_PX_H, trex.y + dy * step))
                

            # Comer cadáver cercano automáticamente (duración 10s)
            for c in corpses:
                if c['eaten'] >= 1.0:
                    continue
                if _dist(trex.x, MARGIN_TOP + trex.y, c['x'], c['y']) < 36:
                    c['eaten'] += 1.0 / float(EAT_DURATION_TICKS)
                    trex.energia = min(160, trex.energia + (40.0/float(EAT_DURATION_TICKS)))
                    _spawn_eat_effect(c['x'], c['y'])
                    if c['eaten'] >= 1.0:
                        c['eaten'] = 1.0
                        c['age'] = c['max_age']
                    break

            # Ataque del jugador con SPACE (cooldown)
            if player_atk_cd > 0:
                player_atk_cd -= 1
            if keys[pg.K_SPACE] and player_atk_cd == 0:
                # Buscar objetivo más cercano alcanzable
                target = None; dmin = 1e9
                for a in eco.animales:
                    if a is trex or not a.esta_vivo():
                        continue
                    d = _dist(trex.x, trex.y, a.x, a.y)
                    if d < dmin:
                        dmin = d; target = a
                if target and dmin < 24:
                    trex.atacar(target, eco)
                    _spawn_hit_effect(int(target.x), MARGIN_TOP + int(target.y))
                    # La creación de cadáver se maneja en Dinosaurio.atacar según la regla de especie distinta
                    player_atk_cd = 15

        # Simulación lógica a paso fijo
        sim_accum += dt
        while sim_accum >= SIM_DT:
            eco.paso()
            # IA adicional de movimiento/comportamiento
            actualizar_ia(eco, trex)
            # Resolver colisiones para evitar solapes
            resolver_colisiones(eco)
            sim_accum -= SIM_DT

        # Actualizar ciclo de vida de cadáveres (desaparecen al consumirse o por edad)
        _update_corpses()

        # Dibujo
        screen.fill((235, 245, 235))

        # Plantas
        for p in eco.plantas:
            if p.vida <= 0:
                continue
            px, py = int(p.x), MARGIN_TOP + int(p.y)
            key = 'Planta_'+p.estado
            spr = SPRITES.get(key)
            if spr is not None:
                rect = spr.get_rect(center=(px, py))
                screen.blit(spr, rect)
            else:
                if p.estado == 'brote':
                    color = (90, 200, 90); r = max(3, CELL_SIZE // 3)
                elif p.estado == 'adulta':
                    color = (60, 160, 60); r = max(5, CELL_SIZE // 2)
                else:
                    color = (150, 120, 80); r = max(2, CELL_SIZE // 4)
                pg.draw.circle(screen, color, (px, py), r)

        # T-Rex y otros
        for a in eco.animales:
            if not a.esta_vivo():
                continue
            px = int(a.x); py = MARGIN_TOP + int(a.y)
            key = type(a).__name__
            spr = SPRITES.get(key)
            if spr is not None:
                rect = spr.get_rect(center=(px, py))
                screen.blit(spr, rect)
            else:
                r = max(6, CELL_SIZE // 2)
                if isinstance(a, TRexJugador):
                    pg.draw.circle(screen, (230, 70, 70), (px, py), r)
                else:
                    col = (120, 120, 200)
                    if a.tipo == 'herbivoro': col = (60, 160, 60)
                    elif a.tipo == 'carnivoro': col = (200, 80, 80)
                    elif a.tipo == 'omnivoro': col = (200, 170, 90)
                    pg.draw.circle(screen, col, (px, py), r)

        # HUD
        plantas = len([p for p in eco.plantas if p.vida > 0])
        hud_text = f"Plantas:{plantas}  [WASD] mover  [SPACE] atacar  (ESC salir)"
        hud = font.render(hud_text, True, (20, 20, 20))
        screen.blit(hud, (8, 8))

        # Efectos y cadáveres
        _render_corpses(screen)
        _render_eat_effects(screen)
        _render_hit_effects(screen)
        _render_ai_attack_effects(screen)

        pg.display.flip()

    pg.quit()


def main():
    random.seed()
    run_game()

if __name__ == "__main__":
    main()