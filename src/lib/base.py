#!/usr/bin/env python3
"""Classe de base pour tous les outils"""

import sys
import getpass
import logging
from src.lib.config import ConfigManager
from src.lib.display import Display
from src.lib.env import env

class BaseTool:
    """Classe de base minimaliste pour tous les outils"""
    
    def __init__(self, args):
        self.args = args
        self.config = ConfigManager()
        self.display = Display()
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure le logging"""
        level = getattr(logging, env.get_log_level())
        logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def get_password(self):
        """Demande le mot de passe SSH de manière sécurisée"""
        return getpass.getpass("🔑 Mot de passe SSH : ")
    
    def list_apps(self):
        """Affiche les applications disponibles"""
        apps = self.config.get_apps()
        if not apps:
            print("📦 Aucune application trouvée dans", self.config.config_dir)
            return
        print("📦 Applications disponibles :")
        for app in sorted(apps):
            print(f"  {app}")
    
    def list_envs(self, app):
        """Affiche les environnements d'une application"""
        envs = self.config.get_envs(app)
        if not envs:
            print(f"🌍 Aucun environnement trouvé pour '{app}'")
            return
        print(f"🌍 Environnements disponibles pour '{app}' :")
        for env in envs:
            print(f"  {env}")
    
    def show_help(self, app):
        """Affiche les détails d'une application"""
        envs = self.config.get_envs(app)
        if not envs:
            print(f"📖 Aucun environnement trouvé pour '{app}'")
            return
        print(f"📖 Détails pour '{app}' :")
        for env in envs:
            info = self.config.get_connection_info(app, env)
            port = info.get('port', 22)
            desc = self.config.get_description(app, env)
            if desc:
                print(f"  {env} → {info['user']}@{info['host']}:{port} ({desc})")
            else:
                print(f"  {env} → {info['user']}@{info['host']}:{port}")
    
    def run(self):
        """À surcharger dans les classes filles"""
        raise NotImplementedError("La méthode run() doit être implémentée")
