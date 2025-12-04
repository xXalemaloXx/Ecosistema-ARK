import pygame as pg
import os
import math
from typing import List, Dict, Any

"""
CAPA DE VISTA (Pygame)
Contiene toda la lógica de renderizado y efectos visuales
"""

# Constantes de visualización
CELL_SIZE = 20
MARGIN_TOP = 40

class VistaEcosistema:
    def __init__(self, world_width: int, world_height: int):
        # Inicializar Pygame
        pg.init()
        self.world_w = world_width
        self.world_h = world_height
        self.window_w = world_width
        self.window_h = world_height + MARGIN_TOP
        self.screen = pg.display.set_mode((self.window_w, self.window_h))
        pg.display.set_caption("Simulación de Ecosistema")
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("consolas", 16)
        
        # Cargar sprites
        self.sprites: Dict[str, pg.Surface] = {}
        self._load_sprites()
        
        # Efectos visuales
        self.hit_effects: List[Dict[str, Any]] = []
        self.eat_effects: List[Dict[str, Any]] = []
        self.ai_attack_effects: List[Dict[str, Any]] = []
        
        # Mensajes en pantalla
        self.mensaje_temporal = None
        self.mensaje_carga_datos = None
        
    def _safe_load(self, path: str, size: tuple[int, int] | None = None) -> pg.Surface | None:
        """Cargar una imagen de forma segura con fallback."""
        try:
            img = pg.image.load(path)
            img = img.convert_alpha()
            if size is not None:
                img = pg.transform.smoothscale(img, size)
            return img
        except Exception:
            return None

    def _make_fallback(self, color: tuple[int, int, int], size: tuple[int, int]) -> pg.Surface:
        """Crear un sprite de fallback como rectángulo con color."""
        surf = pg.Surface(size, pg.SRCALPHA)
        pg.draw.rect(surf, color, surf.get_rect(), border_radius=4)
        return surf

    def _load_sprites(self):
        """Cargar sprites desde archivos o crear fallbacks."""
        base = os.path.join(os.path.dirname(__file__), 'assets')
        mapping = {
            'TRexJugador': ('trex.png', (34, 34), (230, 70, 70)),
            'Triceratops': ('triceratops.png', (30, 30), (60, 160, 60)),
            'Stegosaurio': ('stegosaurio.png', (30, 30), (60, 160, 60)),
            'Velociraptor': ('velociraptor.png', (28, 28), (200, 80, 80)),
            'Dilofosaurio': ('dilofosaurio.png', (28, 28), (200, 80, 80)),
            'Moshops': ('moshops.png', (28, 28), (200, 170, 90)),
            'Planta_brote': ('plant_brote.png', (14, 14), (90, 200, 90)),
            'Planta_adulta': ('plant_adulta.png', (18, 18), (60, 160, 60)),
            'Planta_marchita': ('plant_marchita.png', (12, 12), (150, 120, 80)),
            'Cadaver': ('cadaver.png', (26, 18), (120, 60, 40)),
        }
        for key, (fname, size, color) in mapping.items():
            path = os.path.join(base, fname)
            img = self._safe_load(path, size)
            if img is None:
                img = self._make_fallback(color, size)
            self.sprites[key] = img

    def _dist(self, ax, ay, bx, by):
        """Calcular distancia euclidiana."""
        dx = bx - ax
        dy = by - ay
        return math.hypot(dx, dy)

    def spawn_hit_effect(self, x: int, y: int, life: int = 10):
        """Crear efecto de golpe."""
        self.hit_effects.append({'x': x, 'y': y, 'life': life})

    def _render_hit_effects(self, surface):
        """Renderizar efectos de golpe."""
        remove = []
        for e in self.hit_effects:
            r = max(4, 16 - (10 - e['life']))
            pg.draw.circle(surface, (255, 0, 0), (int(e['x']), int(e['y'])), r, 2)
            pg.draw.circle(surface, (255, 255, 255), (int(e['x']), int(e['y'])), max(2, r//2), 1)
            e['life'] -= 1
            if e['life'] <= 0:
                remove.append(e)
        for e in remove:
            self.hit_effects.remove(e)

    def spawn_eat_effect(self, x: int, y: int, life: int = 12):
        """Crear efecto de comer."""
        self.eat_effects.append({'x': x, 'y': y, 'life': life})

    def _render_eat_effects(self, surface):
        """Renderizar efectos de comer."""
        remove = []
        for e in self.eat_effects:
            phase = (12 - e['life'])
            r = 6 + (phase % 6)
            pg.draw.circle(surface, (255, 165, 0), (int(e['x']), int(e['y'])), r, 2)
            e['life'] -= 1
            if e['life'] <= 0:
                remove.append(e)
        for e in remove:
            self.eat_effects.remove(e)

    def spawn_ai_attack_effect(self, x: int, y: int, life: int = 10, spokes: int = 8):
        """Crear efecto de ataque de IA."""
        self.ai_attack_effects.append({'x': x, 'y': y, 'life': life, 'spokes': spokes})

    def _render_ai_attack_effects(self, surface):
        """Renderizar efectos de ataque de IA."""
        remove = []
        for e in self.ai_attack_effects:
            phase = (10 - e['life'])
            max_r = 18
            r = 6 + int((phase / 10) * max_r)
            cx, cy = int(e['x']), int(e['y'])
            for i in range(e['spokes']):
                ang = (i / e['spokes']) * math.tau
                x2 = cx + int(r * math.cos(ang))
                y2 = cy + int(r * math.sin(ang))
                pg.draw.line(surface, (255, 0, 0), (cx, cy), (x2, y2), 2)
            e['life'] -= 1
            if e['life'] <= 0:
                remove.append(e)
        for e in remove:
            self.ai_attack_effects.remove(e)

    def _draw_skull(self, surface, x, y):
        """Dibujar calavera simple."""
        pg.draw.circle(surface, (255, 255, 255), (x, y), 8)
        pg.draw.circle(surface, (0, 0, 0), (x-3, y-2), 2)
        pg.draw.circle(surface, (0, 0, 0), (x+3, y-2), 2)
        pg.draw.rect(surface, (255, 255, 255), pg.Rect(x-5, y+3, 10, 3))

    def render_corpses(self, surface, corpses: List[Dict[str, Any]]):
        """Renderizar cadáveres."""
        for c in corpses:
            size = max(8, int(20 * (1.0 - 0.3*c['eaten'])))
            cx, cy = int(c['x']), int(c['y'])
            spr = self.sprites.get('Cadaver')
            if spr is not None:
                rect = spr.get_rect(center=(cx, cy))
                surface.blit(spr, rect)
            else:
                rect = pg.Rect(cx-size, cy-size//2, size*2, int(size))
                pg.draw.ellipse(surface, (120, 60, 40), rect)
            bar_w, bar_h = 24, 4
            bx = cx - bar_w//2
            by = cy - size - 8
            pg.draw.rect(surface, (160, 160, 160), pg.Rect(bx, by, bar_w, bar_h), border_radius=2)
            pg.draw.rect(surface, (255, 0, 0), pg.Rect(bx, by, int(bar_w * c['eaten']), bar_h), border_radius=2)
            if c['skull_timer'] > 0:
                self._draw_skull(surface, cx, cy - size - 14)

    def update_corpses(self, corpses: List[Dict[str, Any]]):
        """Actualizar estado de los cadáveres."""
        remove = []
        for c in corpses:
            c['age'] += 1
            if c['skull_timer'] > 0:
                c['skull_timer'] -= 1
            if c['eaten'] >= 1.0 or c['age'] >= c['max_age']:
                remove.append(c)
        for c in remove:
            corpses.remove(c)

    def render_plants(self, surface, plantas: List):
        """Renderizar plantas."""
        for p in plantas:
            if p.vida <= 0:
                continue
            px, py = int(p.x), MARGIN_TOP + int(p.y)
            key = 'Planta_' + p.estado
            spr = self.sprites.get(key)
            if spr is not None:
                rect = spr.get_rect(center=(px, py))
                surface.blit(spr, rect)
            else:
                if p.estado == 'brote':
                    color = (90, 200, 90); r = max(3, CELL_SIZE // 3)
                elif p.estado == 'adulta':
                    color = (60, 160, 60); r = max(5, CELL_SIZE // 2)
                else:
                    color = (150, 120, 80); r = max(2, CELL_SIZE // 4)
                pg.draw.circle(surface, color, (px, py), r)

    def render_animales(self, surface, animales: List):
        """Renderizar animales."""
        for a in animales:
            if not a.esta_vivo():
                continue
            px = int(a.x); py = MARGIN_TOP + int(a.y)
            key = type(a).__name__
            spr = self.sprites.get(key)
            if spr is not None:
                rect = spr.get_rect(center=(px, py))
                surface.blit(spr, rect)
            else:
                r = max(6, CELL_SIZE // 2)
                if hasattr(a, '__class__') and a.__class__.__name__ == 'TRexJugador':
                    pg.draw.circle(surface, (230, 70, 70), (px, py), r)
                else:
                    col = (120, 120, 200)
                    if a.tipo == 'herbivoro': col = (60, 160, 60)
                    elif a.tipo == 'carnivoro': col = (200, 80, 80)
                    elif a.tipo == 'omnivoro': col = (200, 170, 90)
                    pg.draw.circle(surface, col, (px, py), r)

    def render_hud(self, surface, eco, slot_activo, autosave_idx, autosave_intervalos):
        """Renderizar HUD (interfaz de usuario)."""
        plantas_vivas = len([p for p in eco.plantas if p.vida > 0])
        animales_vivos = len([a for a in eco.animales if a.esta_vivo()])
        intervalo_str = 'OFF' if autosave_intervalos[autosave_idx] == 0 else str(autosave_intervalos[autosave_idx])
        
        # Línea 1: Estadísticas
        hud_text1 = (
            f"Ciclo: {eco.ciclo} | Animales: {animales_vivos}/{eco.max_animales} | Plantas: {plantas_vivas} | "
            f"Slot: [{slot_activo}] | Autosave: {intervalo_str}"
        )
        # Línea 2: Controles
        hud_text2 = "[J] Guardar | [R] Cargar | [H] Auto-save | [1-3] Sel. Slot | [ESC] Salir"

        hud1 = self.font.render(hud_text1, True, (230, 230, 230))
        hud2 = self.font.render(hud_text2, True, (230, 230, 230))
        
        surface.blit(hud1, (8, 5))
        surface.blit(hud2, (8, 22))

    def render(self, ecosystem, slot_activo, autosave_idx, autosave_intervalos):
        """Renderizar todo el ecosistema."""
        # Limpiar pantalla con fondo oscuro
        self.screen.fill((25, 25, 25))
        
        # Renderizar elementos
        self.render_plants(self.screen, ecosystem.plantas)
        self.render_animales(self.screen, ecosystem.animales)
        self.render_corpses(self.screen, ecosystem.cadaveres)
        self.render_hud(self.screen, ecosystem, slot_activo, autosave_idx, autosave_intervalos)
        
        # Renderizar mensajes
        self._render_mensajes()
        
        # Renderizar efectos
        self._render_hit_effects(self.screen)
        self._render_eat_effects(self.screen)
        self._render_ai_attack_effects(self.screen)
        

    def update_effects(self):
        """Actualizar todos los efectos visuales."""
        self._render_hit_effects(self.screen)
        self._render_eat_effects(self.screen)
        self._render_ai_attack_effects(self.screen)

    def tick(self):
        """Controlar la velocidad de fotogramas."""
        self.clock.tick(120)  # 120 FPS

    def mostrar_mensaje(self, texto: str, duracion_seg: float):
        """Muestra un mensaje temporal en el centro de la pantalla."""
        self.mensaje_temporal = {
            "texto": texto,
            "expira": pg.time.get_ticks() + duracion_seg * 1000
        }
        self.mensaje_carga_datos = None

    def mostrar_mensaje_carga(self, metadatos: dict):
        """Muestra los metadatos de un archivo de guardado para confirmar la carga."""
        self.mensaje_carga_datos = metadatos
        self.mensaje_temporal = None

    def limpiar_mensajes(self):
        """Limpia cualquier mensaje en pantalla."""
        self.mensaje_temporal = None
        self.mensaje_carga_datos = None

    def _wrap_text(self, text: str, font: pg.font.Font, max_width: int) -> List[str]:
        """Divide un texto largo en varias líneas que se ajustan a un ancho máximo."""
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + word + " "
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        lines.append(current_line.strip())
        return lines

    def _render_mensajes(self):
        """Dibuja los mensajes temporales o de carga en la pantalla."""
        ahora = pg.time.get_ticks()
        
        # Mensaje temporal
        if self.mensaje_temporal:
            if ahora > self.mensaje_temporal["expira"]:
                self.mensaje_temporal = None
            else:
                texto_original = self.mensaje_temporal["texto"]
                lineas = self._wrap_text(texto_original, self.font, self.window_w - 100)
                
                # Calcular altura total para centrar el bloque de texto
                altura_total = len(lineas) * self.font.get_height()
                y_inicial = (self.window_h - altura_total) // 2

                for i, linea in enumerate(lineas):
                    # Fondo del mensaje ligeramente más claro que el fondo del juego
                    superficie_texto = self.font.render(linea, True, (255, 255, 255), (50, 50, 50, 220))
                    rect = superficie_texto.get_rect(center=(self.window_w // 2, y_inicial + i * self.font.get_height()))
                    self.screen.blit(superficie_texto, rect)

        # Mensaje de confirmación de carga
        if self.mensaje_carga_datos:
            meta = self.mensaje_carga_datos
            lineas = [
                "¿Cargar esta partida?",
                f"  Fecha: {meta.get('fecha_hora', 'N/A')}",
                f"  Ciclo: {meta.get('ciclo', 'N/A')}",
                f"  Animales: {meta.get('num_animales', 'N/A')}, Plantas: {meta.get('num_plantas', 'N/A')}",
                f"  Estado: {meta.get('estado_ecosistema', 'N/A')}",
                "",
                "Presiona [ENTER] para confirmar o [ESC] para cancelar"
            ]
            
            # Fondo semitransparente
            fondo = pg.Surface((self.window_w, self.window_h), pg.SRCALPHA)
            fondo.fill((0, 0, 0, 180))
            self.screen.blit(fondo, (0, 0))
            
            # Renderizar con ajuste de texto para cada línea
            all_wrapped_lines = []
            for linea in lineas:
                all_wrapped_lines.extend(self._wrap_text(linea, self.font, self.window_w - 100))

            altura_total = len(all_wrapped_lines) * self.font.get_height() + (len(all_wrapped_lines) - 1) * 5
            y_offset = (self.window_h - altura_total) // 2
            
            current_y = y_offset
            for linea in all_wrapped_lines:
                superficie_texto = self.font.render(linea, True, (255, 255, 255))
                rect = superficie_texto.get_rect(center=(self.window_w // 2, current_y + self.font.get_height() // 2))
                self.screen.blit(superficie_texto, rect)
                current_y += self.font.get_height() + 5 # Espacio entre líneas

    def render_menu_guardado(self, estado: str, slot_seleccionado: int, metadatos: dict):
        """Renderiza la pantalla de selección de slot para guardar o cargar."""
        self.screen.fill((25, 25, 25))

        # Título
        titulo_str = "Guardar Partida" if estado == 'PANTALLA_GUARDAR' else "Cargar Partida"
        titulo_surf = self.font.render(titulo_str, True, (255, 255, 255))
        titulo_rect = titulo_surf.get_rect(center=(self.window_w // 2, 60))
        self.screen.blit(titulo_surf, titulo_rect)

        # Slots
        slot_h = 100
        slot_w = self.window_w - 160
        start_y = 120

        for i in range(1, 4):
            slot_rect = pg.Rect((self.window_w - slot_w) // 2, start_y + (i - 1) * (slot_h + 20), slot_w, slot_h)
            
            # Resaltar slot seleccionado
            if i == slot_seleccionado:
                pg.draw.rect(self.screen, (100, 100, 100), slot_rect, border_radius=8)
                pg.draw.rect(self.screen, (255, 255, 0), slot_rect, 2, border_radius=8)
            else:
                pg.draw.rect(self.screen, (60, 60, 60), slot_rect, border_radius=8)

            # Información del slot
            meta = metadatos.get(i)
            if meta and 'error' not in meta:
                line1 = f"SLOT {i} - {meta.get('fecha_hora', 'N/A')}"
                line2 = f"Ciclo: {meta.get('ciclo', '?')} | Animales: {meta.get('num_animales', '?')} | Plantas: {meta.get('num_plantas', '?')}"
                line3 = f"Estado: {meta.get('estado_ecosistema', 'Desconocido')}"
                if meta.get('autoguardado'):
                    line1 += " (AUTOGUARDADO)"
                
                l1_surf = self.font.render(line1, True, (230, 230, 230))
                l2_surf = self.font.render(line2, True, (200, 200, 200))
                l3_surf = self.font.render(line3, True, (180, 180, 180))
                
                self.screen.blit(l1_surf, (slot_rect.x + 15, slot_rect.y + 15))
                self.screen.blit(l2_surf, (slot_rect.x + 15, slot_rect.y + 40))
                self.screen.blit(l3_surf, (slot_rect.x + 15, slot_rect.y + 65))
            else:
                texto_vacio = f"SLOT {i} - Vacío"
                vacio_surf = self.font.render(texto_vacio, True, (150, 150, 150))
                vacio_rect = vacio_surf.get_rect(center=slot_rect.center)
                self.screen.blit(vacio_surf, vacio_rect)

        # Instrucciones
        instr_str = "[↑/↓] Seleccionar | [ENTER] Confirmar | [ESC] Volver"
        instr_surf = self.font.render(instr_str, True, (200, 200, 200))
        instr_rect = instr_surf.get_rect(center=(self.window_w // 2, self.window_h - 40))
        self.screen.blit(instr_surf, instr_rect)

    def limpiar(self):
        """Limpiar recursos."""
        pg.quit()
