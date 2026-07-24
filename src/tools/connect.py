#!/usr/bin/env python3
"""Outil de connexion SSH interactive"""

import sys
import subprocess
from src.lib.base import BaseTool

class ConnectTool(BaseTool):
    """Se connecte en SSH à un environnement"""
    
    def parse_args(self):
        """Parse les arguments spécifiques à connect"""
        if len(self.args) == 0:
            self.list_apps()
            sys.exit(0)
        
        self.app = self.args[0]
        
        if not self.config.app_exists(self.app):
            print(f"❌ Application '{self.app}' inconnue")
            self.list_apps()
            sys.exit(1)
        
        if len(self.args) == 1:
            self.list_envs(self.app)
            sys.exit(0)
        
        if self.args[1] in ["help", "-h"]:
            self.show_help(self.app)
            sys.exit(0)
        
        self.env = self.args[1]
        
        if not self.config.env_exists(self.app, self.env):
            print(f"❌ Environnement '{self.env}' inconnu pour '{self.app}'")
            self.list_envs(self.app)
            sys.exit(1)
    
    def run(self):
        """Établit la connexion SSH"""
        self.parse_args()
        
        info = self.config.get_connection_info(self.app, self.env)
        port = info.get('port', 22)
        
        print(f"🔌 Connexion à {self.app} ({self.env}) : {info['user']}@{info['host']}:{port}")
        
        # Connexion SSH classique (on laisse ssh gérer l'auth)
        cmd = f"ssh {info['user']}@{info['host']} -p {port}"
        subprocess.call(cmd, shell=True)

def main():
    """Point d'entrée pour l'outil connect"""
    tool = ConnectTool(sys.argv[1:])
    tool.run()

if __name__ == "__main__":
    main()
