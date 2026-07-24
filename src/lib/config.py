#!/usr/bin/env python3
"""Gestion des fichiers de configuration INI"""

import os
import configparser
from src.lib.env import env

class ConfigManager:
    """Gère la lecture des fichiers INI"""
    
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = env.get_config_dir()
        self.config_dir = os.path.expanduser(config_dir)
    
    def get_apps(self):
        """Retourne la liste des applications disponibles"""
        if not os.path.exists(self.config_dir):
            return []
        return [f.replace('.ini', '') for f in os.listdir(self.config_dir) 
                if f.endswith('.ini')]
    
    def get_envs(self, app):
        """Retourne la liste des environnements d'une application"""
        config = configparser.ConfigParser()
        config.read(f"{self.config_dir}/{app}.ini")
        return config.sections()
    
    def get_connection_info(self, app, env):
        """Retourne les infos de connexion pour un environnement"""
        config = configparser.ConfigParser()
        config.read(f"{self.config_dir}/{app}.ini")
        section = config[env]
        return {
            'host': section.get('host'),
            'user': section.get('user'),
            'port': section.get('port', 22)
        }
    
    def get_description(self, app, env):
        """Retourne la description d'un environnement (optionnel)"""
        config = configparser.ConfigParser()
        config.read(f"{self.config_dir}/{app}.ini")
        section = config[env]
        return section.get('description', '')
    
    def app_exists(self, app):
        """Vérifie si une application existe"""
        return app in self.get_apps()
    
    def env_exists(self, app, env):
        """Vérifie si un environnement existe pour une application"""
        return env in self.get_envs(app)
