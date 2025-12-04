import pickle
import json
import os
import shutil
from datetime import datetime
from modelo import Ecosistema, SIM_VERSION

"""
CAPA DE PERSISTENCIA
Contiene la lógica para guardar y cargar el estado del ecosistema.
"""

SAVE_DIR = "saves"

class Persistencia:
    def __init__(self):
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

    def _get_paths(self, slot: str):
        """Obtiene las rutas para los archivos de datos y metadatos de un slot."""
        data_path = os.path.join(SAVE_DIR, f"{slot}.dat")
        meta_path = os.path.join(SAVE_DIR, f"{slot}.json")
        return data_path, meta_path

    def _crear_backup(self, path: str):
        """Crea un backup de un archivo si existe."""
        if os.path.exists(path):
            try:
                shutil.copy(path, f"{path}.bak")
                return True
            except Exception as e:
                print(f"Error al crear backup para {path}: {e}")
                return False
        return True

    def _generar_metadatos(self, eco: Ecosistema, autoguardado: bool, intervalo_autosave: int) -> dict:
        """Genera un diccionario con los metadatos del estado actual del juego."""
        num_animales = len([a for a in eco.animales if a.esta_vivo()])
        num_plantas = len([p for p in eco.plantas if p.vida > 0])
        
        estado = "Equilibrado"
        if num_plantas < 20:
            estado = "Baja vegetación"
        if num_animales > eco.max_animales * 0.8:
            estado = "Alta densidad"

        return {
            "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ciclo": eco.ciclo,
            "num_animales": num_animales,
            "num_plantas": num_plantas,
            "estado_ecosistema": estado,
            "version_simulador": SIM_VERSION,
            "autoguardado": autoguardado,
            "intervalo_autosave": intervalo_autosave
        }

    def guardar_slot(self, slot: str, eco: Ecosistema, intervalo_autosave: int, autoguardado: bool = False):
        """Guarda el estado completo del juego (ecosistema y cadáveres) en un slot."""
        data_path, meta_path = self._get_paths(slot)

        # Crear backups antes de sobrescribir
        self._crear_backup(data_path)
        self._crear_backup(meta_path)

        # Guardar estado completo del juego
        estado = {
            "ecosistema": eco,
            "version_simulador": SIM_VERSION
        }
        try:
            with open(data_path, 'wb') as f:
                pickle.dump(estado, f)
        except Exception as e:
            print(f"Error al guardar el estado del juego en {data_path}: {e}")
            return False, "Error al guardar datos"

        # Guardar metadatos
        try:
            metadatos = self._generar_metadatos(eco, autoguardado, intervalo_autosave)
            with open(meta_path, 'w') as f:
                json.dump(metadatos, f, indent=4)
        except Exception as e:
            print(f"Error al guardar los metadatos en {meta_path}: {e}")
            return False, "Error al guardar metadatos"
        
        return True, f"Juego guardado en slot '{slot}'"

    def cargar_metadatos(self, slot: str):
        """Carga solo los metadatos de un slot para mostrarlos."""
        _, meta_path = self._get_paths(slot)
        if not os.path.exists(meta_path):
            return None, "Slot vacío"
        try:
            with open(meta_path, 'r') as f:
                metadatos = json.load(f)
            return metadatos, None
        except Exception as e:
            return None, f"Error al leer metadatos: {e}"

    def cargar_slot(self, slot: str) -> tuple[Ecosistema | None, str]:
        """Carga el estado completo del juego desde un slot y valida la versión."""
        data_path, meta_path = self._get_paths(slot)
        
        if not os.path.exists(data_path) or not os.path.exists(meta_path):
            return None, "El slot de guardado está vacío o corrupto."

        # Validar versión
        metadatos, error = self.cargar_metadatos(slot)
        if error:
            return None, error
        
        if metadatos.get("version_simulador") != SIM_VERSION:
            return None, f'Versión incompatible (Juego: {SIM_VERSION}, Guardado: {metadatos.get("version_simulador", "??")})'

        # Cargar estado completo del juego
        try:
            with open(data_path, 'rb') as f:
                estado_cargado = pickle.load(f)

            # Compatibilidad con guardados antiguos que solo contenían el objeto Ecosistema
            if isinstance(estado_cargado, Ecosistema):
                # Si es un guardado antiguo, no se puede verificar la versión aquí.
                # La verificación de metadatos ya proporciona una barrera.
                return estado_cargado, "Juego cargado (formato antiguo)."

            # Para nuevos guardados (diccionarios)
            if isinstance(estado_cargado, dict):
                if estado_cargado.get("version_simulador") != SIM_VERSION:
                    return None, f'Versión incompatible (Juego: {SIM_VERSION}, Guardado: {estado_cargado.get("version_simulador", "??")})'
                return estado_cargado.get("ecosistema"), "Juego cargado exitosamente."
            
            # Si el formato no es reconocido
            return None, "Formato de archivo de guardado no reconocido."

        except Exception as e:
            return None, f"Error al cargar el estado del juego: {e}"
