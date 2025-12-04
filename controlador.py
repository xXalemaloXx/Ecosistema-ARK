import random
import math
import sys
import pygame as pg
from modelo import (
    Ecosistema, TRexJugador, Triceratops, Stegosaurio, 
    Velociraptor, Dilofosaurio, Moshops,
    WORLD_PX_W, WORLD_PX_H, MOVE_SPEED, 
    SPEED_FLEE, SPEED_CHASE, SPEED_SEEK_PLANT, SPEED_PATROL, 
    SPEED_SEEK_CORPSE, HUNGER_THRESHOLD, EAT_DURATION_TICKS
)
from vista import VistaEcosistema, MARGIN_TOP
from persistencia import Persistencia

"""
CAPA DE CONTROLADOR
Contiene la lógica de control, IA y el bucle principal del juego
"""

class ControladorJuego:
    def __init__(self):
        self.persistencia = Persistencia()
        self.slot_activo = 1
        self.autosave_intervalos = [0, 300, 600, 1200]  # 0 es OFF
        self.autosave_idx = 0
        self.carga_pendiente = None
        self.ecosistema = Ecosistema()
        self.vista = VistaEcosistema(WORLD_PX_W, WORLD_PX_H)
        self.corriendo = True
        self.player_atk_cd = 0

        # Estados del juego: 'JUGANDO', 'PANTALLA_GUARDAR', 'PANTALLA_CARGAR'
        self.estado_juego = 'JUGANDO'
        self.slot_seleccionado = self.slot_activo
        self.metadatos_slots = {}
        
        # Inicializar el ecosistema
        self.ecosistema.poblar_inicial()
        self._poblar_animales_adicionales()
        
        # Mensaje inicial
        self.vista.mostrar_mensaje(f"Slot {self.slot_activo} seleccionado", 2)

    def _poblar_animales_adicionales(self):
        """Añadir animales adicionales con separación inicial."""
        # Definir zonas: herbívoros a la izquierda, carnívoros a la derecha, buffer central
        SEP_BUFFER = 80
        LEFT_X_MIN, LEFT_X_MAX = 50, max(50, WORLD_PX_W // 2 - SEP_BUFFER)
        RIGHT_X_MIN, RIGHT_X_MAX = min(WORLD_PX_W - 50, WORLD_PX_W // 2 + SEP_BUFFER), WORLD_PX_W - 50
        Y_MIN, Y_MAX = 80, WORLD_PX_H - 50

        # Herbívoros en manadas (lado izquierdo)
        for _ in range(4):
            self.ecosistema.agregar_animal(Triceratops(
                random.randint(LEFT_X_MIN, LEFT_X_MAX),
                random.randint(Y_MIN, Y_MAX)
            ))
        for _ in range(3):
            self.ecosistema.agregar_animal(Stegosaurio(
                random.randint(LEFT_X_MIN, LEFT_X_MAX),
                random.randint(Y_MIN, Y_MAX)
            ))

        # Carnívoros (lado derecho)
        for _ in range(2):
            self.ecosistema.agregar_animal(Velociraptor(
                random.randint(RIGHT_X_MIN, RIGHT_X_MAX),
                random.randint(Y_MIN, Y_MAX)
            ))
        self.ecosistema.agregar_animal(Dilofosaurio(
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
        self.ecosistema.agregar_animal(Moshops(omni_x, random.randint(Y_MIN, Y_MAX)))

    def _dist_sq(self, ax, ay, bx, by):
        """Calcular la distancia euclidiana al cuadrado. Más rápido para comparaciones."""
        dx = bx - ax
        dy = by - ay
        return dx*dx + dy*dy

    def _manejar_entrada_jugador(self):
        """Manejar la entrada del jugador."""
        keys = pg.key.get_pressed()
        trex = self.ecosistema.jugador
        
        if trex and trex.esta_vivo():
            # Movimiento (WASD + flechas)
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

            # Comer cadáver cercano automáticamente
            for c in self.ecosistema.cadaveres:
                if c['eaten'] >= 1.0:
                    continue
                if self._dist_sq(trex.x, MARGIN_TOP + trex.y, c['x'], c['y']) < 36*36:
                    c['eaten'] += 1.0 / float(EAT_DURATION_TICKS)
                    trex.energia = min(160, trex.energia + (40.0/float(EAT_DURATION_TICKS)))
                    self.vista.spawn_eat_effect(c['x'], c['y'])
                    if c['eaten'] >= 1.0:
                        c['eaten'] = 1.0
                        c['age'] = c['max_age']
                    break

            # Ataque del jugador con SPACE
            if self.player_atk_cd > 0:
                self.player_atk_cd -= 1
            if keys[pg.K_SPACE] and self.player_atk_cd == 0:
                target = None
                dmin = 1e9
                for a in self.ecosistema.animales:
                    if a is trex or not a.esta_vivo():
                        continue
                    d_sq = self._dist_sq(trex.x, trex.y, a.x, a.y)
                    if d_sq < dmin:
                        dmin = d_sq
                        target = a
                if target and dmin < 24*24:
                    trex.atacar(target, self.ecosistema)
                    self.vista.spawn_hit_effect(int(target.x), MARGIN_TOP + int(target.y))
                    self.player_atk_cd = 15

    def _actualizar_ia(self):
        """Actualizar la IA de los animales."""
        jugador = self.ecosistema.jugador
        
        # Agrupar por especie: centroides para moverse en grupo
        especie_pos = {}
        especie_count = {}
        for a in self.ecosistema.animales:
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

        # Comportamiento por tipo
        for a in list(self.ecosistema.animales):
            if a is jugador or not a.esta_vivo():
                continue
            t = getattr(a, 'tipo', '')
            
            # Muerte natural por energía
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
                self._ia_herbivoro(a, jugador)
            elif t == 'carnivoro':
                self._ia_carnivoro(a, jugador)
            elif t == 'omnivoro':
                self._ia_omnivoro(a, jugador)

    def _ia_herbivoro(self, a, jugador):
        """IA para herbívoros."""
        # Huir del T-Rex si está cerca
        if self._dist_sq(a.x, a.y, jugador.x, jugador.y) < 120*120:
            dx = a.x - jugador.x
            dy = a.y - jugador.y
            d = math.hypot(dx, dy) or 1
            a.x = max(0, min(WORLD_PX_W, a.x + SPEED_FLEE * dx/d))
            a.y = max(0, min(WORLD_PX_H, a.y + SPEED_FLEE * dy/d))
            a.energia -= 0.0
        else:
            if a.energia < HUNGER_THRESHOLD:
                # Buscar planta más cercana
                vivos = [p for p in self.ecosistema.plantas if p.vida > 0]
                if vivos:
                    obj = min(vivos, key=lambda p: self._dist_sq(a.x, a.y, p.x, p.y))
                    dx = obj.x - a.x
                    dy = obj.y - a.y
                    d = math.hypot(dx, dy) or 1
                    a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_PLANT * dx/d))
                    a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_PLANT * dy/d))
                    a.energia -= 0.0
                    if self._dist_sq(a.x, a.y, obj.x, obj.y) < 16*16 and obj.vida > 0:
                        a.comer(obj, self.ecosistema)
                else:
                    # Vagar si no hay comida
                    a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                    a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                    a.energia -= 0.0
            else:
                # Saciado: deambular conservando energía
                a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
                a.energia -= 0.0

    def _ia_carnivoro(self, a, jugador):
        """IA para carnívoros."""
        # Prioridad absoluta: cadáver
        if self._ai_comer_cadaver(a):
            return
        
        # Buscar cadáver más cercano
        target_corpse = None
        best_d = 1e9
        for c in self.ecosistema.cadaveres:
            if c['eaten'] >= 1.0:
                continue
            d_sq = self._dist_sq(a.x, MARGIN_TOP + a.y, c['x'], c['y'])
            if d_sq < best_d:
                best_d = d_sq
                target_corpse = c
        
        if target_corpse is not None:
            dx = target_corpse['x'] - a.x
            dy = target_corpse['y'] - (MARGIN_TOP + a.y)
            d = math.hypot(dx, dy) or 1
            a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_CORPSE * dx/d))
            a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_CORPSE * dy/d))
            self._ai_comer_cadaver(a)
            return
        
        if a.energia <= HUNGER_THRESHOLD:
            # Con hambre: cazar
            presas = [h for h in self.ecosistema.animales if getattr(h, 'tipo', '') in ('herbivoro', 'omnivoro') and h.esta_vivo()]
            if presas:
                obj = min(presas, key=lambda h: self._dist_sq(a.x, a.y, h.x, h.y))
                dx = obj.x - a.x
                dy = obj.y - a.y
                d = math.hypot(dx, dy) or 1
                a.x = max(0, min(WORLD_PX_W, a.x + SPEED_CHASE * dx/d))
                a.y = max(0, min(WORLD_PX_H, a.y + SPEED_CHASE * dy/d))
                a.energia -= 0.0
                if self._dist_sq(a.x, a.y, obj.x, obj.y) < 22*22:
                    self._intentar_ataque(a, obj)
        else:
            # Saciado: patrullar
            a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
            a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
            a.energia -= 0.0
            # Si patrullando encuentra cadáver, comer
            self._ai_comer_cadaver(a)

    def _ia_omnivoro(self, a, jugador):
        """IA para omnívoros."""
        # Prioridad absoluta: cadáver
        if self._ai_comer_cadaver(a):
            return
        
        # Buscar cadáver más cercano
        target_corpse = None
        best_d = 1e9
        for c in self.ecosistema.cadaveres:
            if c['eaten'] >= 1.0:
                continue
            d_sq = self._dist_sq(a.x, MARGIN_TOP + a.y, c['x'], c['y'])
            if d_sq < best_d:
                best_d = d_sq
                target_corpse = c
        
        if target_corpse is not None:
            dx = target_corpse['x'] - a.x
            dy = target_corpse['y'] - (MARGIN_TOP + a.y)
            d = math.hypot(dx, dy) or 1
            a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_CORPSE * dx/d))
            a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_CORPSE * dy/d))
            self._ai_comer_cadaver(a)
            return
        
        if a.energia < HUNGER_THRESHOLD:
            # Con hambre: buscar plantas
            vivos = [p for p in self.ecosistema.plantas if p.vida > 0]
            if vivos:
                obj = min(vivos, key=lambda p: self._dist_sq(a.x, a.y, p.x, p.y))
                dx = obj.x - a.x
                dy = obj.y - a.y
                d = math.hypot(dx, dy) or 1
                a.x = max(0, min(WORLD_PX_W, a.x + SPEED_SEEK_PLANT * dx/d))
                a.y = max(0, min(WORLD_PX_H, a.y + SPEED_SEEK_PLANT * dy/d))
                a.energia -= 0.0
                if self._dist_sq(a.x, a.y, obj.x, obj.y) < 16*16 and obj.vida > 0:
                    a.comer(obj, self.ecosistema)
        else:
            # Saciado: patrullar
            a.x = max(0, min(WORLD_PX_W, a.x + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
            a.y = max(0, min(WORLD_PX_H, a.y + random.uniform(-SPEED_PATROL, SPEED_PATROL)))
            a.energia -= 0.0

    def _ai_comer_cadaver(self, animal):
        """Manejar la IA para comer cadáveres."""
        if getattr(animal, 'tipo', '') not in ('carnivoro', 'omnivoro'):
            return False
        
        EAT_DURATION_FRAMES = EAT_DURATION_TICKS
        E_PER_TICK = 40.0 / EAT_DURATION_FRAMES
        
        for c in self.ecosistema.cadaveres:
            if c['eaten'] >= 1.0:
                continue
            if self._dist_sq(animal.x, MARGIN_TOP + animal.y, c['x'], c['y']) < 36*36:
                c['eaten'] += 1.0 / EAT_DURATION_FRAMES
                animal.energia += E_PER_TICK
                self.vista.spawn_eat_effect(c['x'], c['y'])
                if c['eaten'] >= 1.0:
                    c['eaten'] = 1.0
                    c['age'] = c['max_age']
                return True
        return False

    def _intentar_ataque(self, attacker, victim):
        """Intentar realizar un ataque."""
        if not hasattr(attacker, '_atk_cd'):
            attacker._atk_cd = 0
        if attacker._atk_cd > 0:
            attacker._atk_cd -= 1
            return
        dist_sq = self._dist_sq(attacker.x, attacker.y, victim.x, victim.y)
        if dist_sq < 26*26:
            attacker.atacar(victim, self.ecosistema)
            attacker._atk_cd = 30
            if not isinstance(attacker, TRexJugador) and getattr(attacker, 'tipo', '') == 'carnivoro':
                self.vista.spawn_ai_attack_effect(victim.x, MARGIN_TOP + int(victim.y) - 40)

    def _resolver_colisiones(self):
        """Evitar solapes empujando dinosaurios separados."""
        vivos = [a for a in self.ecosistema.animales if a.esta_vivo()]
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

    def _manejar_eventos(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.corriendo = False
            elif event.type == pg.KEYDOWN:
                # --- Eventos globales ---
                if event.key == pg.K_ESCAPE:
                    if self.estado_juego in ['PANTALLA_GUARDAR', 'PANTALLA_CARGAR']:
                        self.estado_juego = 'JUGANDO'
                        self.vista.limpiar_mensajes()
                    else:
                        self.corriendo = False

                # --- Eventos en estado JUGANDO ---
                if self.estado_juego == 'JUGANDO':
                    self._manejar_eventos_jugando(event)
                
                # --- Eventos en PANTALLAS de Guardar/Cargar ---
                elif self.estado_juego in ['PANTALLA_GUARDAR', 'PANTALLA_CARGAR']:
                    self._manejar_eventos_menu(event)

    def _manejar_eventos_jugando(self, event):
        # Selección de slot activo (ahora solo cambia el target del autosave)
        if event.key in [pg.K_1, pg.K_2, pg.K_3]:
            self.slot_activo = event.key - pg.K_0
            self.vista.mostrar_mensaje(f"Autoguardado en Slot {self.slot_activo}", 2)
        # Abrir pantalla de guardado
        elif event.key == pg.K_j:
            self.estado_juego = 'PANTALLA_GUARDAR'
            self.slot_seleccionado = self.slot_activo
            self._cargar_metadatos_todos_slots()
        # Abrir pantalla de carga
        elif event.key == pg.K_r:
            self.estado_juego = 'PANTALLA_CARGAR'
            self.slot_seleccionado = self.slot_activo
            self._cargar_metadatos_todos_slots()
        # Ciclo de autoguardado
        elif event.key == pg.K_h:
            self.autosave_idx = (self.autosave_idx + 1) % len(self.autosave_intervalos)
            intervalo = self.autosave_intervalos[self.autosave_idx]
            msg = f"Autoguardado: {'OFF' if intervalo == 0 else f'Cada {intervalo} ciclos'}"
            self.vista.mostrar_mensaje(msg, 2)

    def _manejar_eventos_menu(self, event):
        if event.key in [pg.K_UP, pg.K_w]:
            self.slot_seleccionado = max(1, self.slot_seleccionado - 1)
        elif event.key in [pg.K_DOWN, pg.K_s]:
            self.slot_seleccionado = min(3, self.slot_seleccionado + 1)
        elif event.key in [pg.K_1, pg.K_2, pg.K_3]:
            self.slot_seleccionado = event.key - pg.K_0
        elif event.key == pg.K_RETURN:
            if self.estado_juego == 'PANTALLA_GUARDAR':
                slot_str = f"slot{self.slot_seleccionado}"
                success, msg = self.persistencia.guardar_slot(slot_str, self.ecosistema, self.autosave_intervalos[self.autosave_idx])
                self.vista.mostrar_mensaje(msg, 3)
                self.estado_juego = 'JUGANDO'
            elif self.estado_juego == 'PANTALLA_CARGAR':
                slot_str = f"slot{self.slot_seleccionado}"
                eco_cargado, msg = self.persistencia.cargar_slot(slot_str)
                if eco_cargado:
                    self.ecosistema = eco_cargado
                    self.vista.mostrar_mensaje(msg, 3)
                else:
                    self.vista.mostrar_mensaje(f"{msg}. No se pudo cargar.", 4)
                self.estado_juego = 'JUGANDO'

    def _cargar_metadatos_todos_slots(self):
        self.metadatos_slots = {}
        for i in range(1, 4):
            slot_str = f"slot{i}"
            meta, err = self.persistencia.cargar_metadatos(slot_str)
            if meta:
                self.metadatos_slots[i] = meta
            else:
                self.metadatos_slots[i] = {'error': err}

    def ejecutar(self):
        """Bucle principal del juego."""
        SIM_DT = 0.04  # 40 ms por paso lógico
        sim_accum = 0.0
        
        while self.corriendo:
            dt = self.vista.clock.tick(120) / 1000.0  # limitar a ~120 FPS
            
            self._manejar_eventos()

            # --- Lógica y renderizado condicional por estado ---
            if self.estado_juego == 'JUGANDO':
                self._manejar_entrada_jugador()
                
                sim_accum += dt
                while sim_accum >= SIM_DT:
                    self.ecosistema.paso()
                    self._actualizar_ia()
                    self._resolver_colisiones()
                    sim_accum -= SIM_DT
                    
                    # Autoguardado
                    intervalo = self.autosave_intervalos[self.autosave_idx]
                    if intervalo > 0 and self.ecosistema.ciclo > 0 and self.ecosistema.ciclo % intervalo == 0:
                        slot_a_guardar = f"slot{self.slot_activo}"
                        self.persistencia.guardar_slot(slot_a_guardar, self.ecosistema, intervalo, autoguardado=True)
                        self.vista.mostrar_mensaje(f"Autoguardado en Slot {self.slot_activo}", 1.5)
                
                self.vista.update_corpses(self.ecosistema.cadaveres)
                self.vista.render(self.ecosistema, self.slot_activo, self.autosave_idx, self.autosave_intervalos)
            
            elif self.estado_juego in ['PANTALLA_GUARDAR', 'PANTALLA_CARGAR']:
                self.vista.render_menu_guardado(self.estado_juego, self.slot_seleccionado, self.metadatos_slots)
            
            # El flip final de la pantalla lo hace cada método de renderizado
            pg.display.flip()
        
        # Limpiar
        self.vista.limpiar()

def main():
    """Función principal."""
    random.seed()
    juego = ControladorJuego()
    juego.ejecutar()

if __name__ == "__main__":
    main()
