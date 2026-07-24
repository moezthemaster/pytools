#!/usr/bin/env python3
"""Gestion des variables d'environnement"""

import os
from pathlib import Path
from dotenv import load_dotenv

class EnvManager:
    """Charge et gère les variables d'environnement depuis .env"""
    
    def __init__(self, env_file=None):
        if env_file is None:
            env_file = os.path.expanduser("~/.sessions/.env")
        self.env_file = env_file
        self._load()
    
    def _load(self):
        """Charge le fichier .env"""
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)
    
    def get(self, key, default=None):
        """Récupère une variable d'environnement"""
        return os.getenv(key, default)
    
    def get_config_dir(self):
        """Retourne le répertoire des fichiers INI"""
        default = os.path.expanduser("~/.sessions/sessions")
        return self.get("SESSIONS_CONFIG_DIR", default)
    
    def get_ssh_timeout(self):
        """Timeout de connexion SSH"""
        return int(self.get("SSH_TIMEOUT", 10))
    
    def get_ssh_command_timeout(self):
        """Timeout d'exécution des commandes"""
        return int(self.get("SSH_COMMAND_TIMEOUT", 30))
    
    def get_display_colors(self):
        """Afficher les couleurs"""
        return self.get("DISPLAY_COLORS", "true").lower() == "true"
    
    def get_max_workers(self):
        """Nombre maximal de connexions parallèles"""
        return int(self.get("MAX_PARALLEL_WORKERS", 10))
    
    def get_backup_dir(self):
        """Répertoire des backups"""
        default = os.path.expanduser("~/backups/sessions")
        return self.get("BACKUP_DIR", default)
    
    def get_log_level(self):
        """Niveau de log"""
        return self.get("LOG_LEVEL", "INFO")

# Instance globale pour faciliter l'import
env = EnvManager()
