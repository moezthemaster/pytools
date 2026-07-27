#!/usr/bin/env python3
"""Gestion des sessions multi-environnements"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from src.lib.config import ConfigManager
from src.lib.ssh import SSHExecutor
from src.lib.display import Display
from src.lib.env import env

class SessionManager:
    """Gère l'exécution sur plusieurs environnements"""
    
    def __init__(self, app, envs, command, password, target_user=None):
        self.app = app
        self.envs = envs
        self.command = command
        self.password = password
        self.target_user = target_user
        self.config = ConfigManager()
        self.executor = SSHExecutor(password)
        self.results = []
        self.display = Display(colors=env.get_display_colors())
        self.max_workers = env.get_max_workers()
    
    def run_sequential(self):
        """Exécute séquentiellement (une machine après l'autre)"""
        for env in self.envs:
            info = self.config.get_connection_info(self.app, env)
            result = self.executor.run_on_env(self.app, env, self.command, info, self.target_user)
            self.results.append(result)
            self.display.show_result(result, show_separator=True)
        self.display.show_summary(self.results)
    
    def run_parallel(self):
        """Exécute en parallèle (toutes les machines en même temps)"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for env in self.envs:
                info = self.config.get_connection_info(self.app, env)
                future = pool.submit(
                    self.executor.run_on_env,
                    self.app,
                    env,
                    self.command,
                    info,
                    self.target_user
                )
                futures[future] = env
            
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                self.display.show_result(result, show_separator=True)
        
        self.display.show_summary(self.results)
    
    def get_results(self):
        """Retourne les résultats"""
        return self.results
