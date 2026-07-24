#!/usr/bin/env python3
"""Gestion de l'affichage (couleurs, formats)"""

import colorama
from src.lib.env import env

# Initialisation de colorama (Windows compatible)
colorama.init(autoreset=True)

class Display:
    """Gère l'affichage des résultats"""
    
    GREEN = colorama.Fore.GREEN
    RED = colorama.Fore.RED
    YELLOW = colorama.Fore.YELLOW
    BLUE = colorama.Fore.BLUE
    CYAN = colorama.Fore.CYAN
    RESET = colorama.Fore.RESET
    BOLD = colorama.Style.BRIGHT
    
    def __init__(self, colors=None):
        if colors is None:
            colors = env.get_display_colors()
        self.colors = colors
    
    def _colorize(self, text, color):
        """Ajoute des couleurs si activé"""
        if self.colors:
            return f"{color}{text}{self.RESET}"
        return text
    
    def show_result(self, result, show_separator=True):
        """Affiche le résultat d'une exécution"""
        env_label = f"{result['app']}:{result['env']}"
        host_info = f"{result['user']}@{result['host']}:{result['port']}"
        
        print()
        print(self._colorize(f"🔌 {env_label} ({host_info})", self.CYAN))
        print(self._colorize("─────────────────────────────────", self.BOLD))
        
        if result['stdout']:
            print(result['stdout'].rstrip())
        
        if result['stderr']:
            print(self._colorize(result['stderr'].rstrip(), self.YELLOW))
        
        print(self._colorize("─────────────────────────────────", self.BOLD))
        
        if result['code'] == 0:
            print(self._colorize(f"✅ Succès (code {result['code']})", self.GREEN))
        else:
            print(self._colorize(f"❌ Échec (code {result['code']})", self.RED))
    
    def show_summary(self, results):
        """Affiche un résumé des résultats"""
        success = sum(1 for r in results if r['code'] == 0)
        failure = len(results) - success
        
        print()
        if failure == 0:
            print(self._colorize(f"📊 Résumé : {success} succès", self.GREEN))
        else:
            print(self._colorize(f"📊 Résumé : {success} succès, {failure} échec(s)", self.RED))
    
    def show_error(self, message):
        """Affiche une erreur"""
        print(self._colorize(f"❌ {message}", self.RED))
    
    def show_info(self, message):
        """Affiche une information"""
        print(self._colorize(f"ℹ️ {message}", self.BLUE))
