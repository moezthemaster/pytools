#!/usr/bin/env python3
"""Outil d'exécution de commandes sur plusieurs environnements"""

import sys
from src.lib.base import BaseTool
from src.lib.session import SessionManager

class ExecTool(BaseTool):
    """Exécute une commande sur un ou plusieurs environnements"""
    
    def parse_args(self):
        """Parse les arguments spécifiques à exec"""
        if len(self.args) < 2:
            print("Usage: exec <app> [<env>|all|env1,env2] <commande>")
            print("       exec <app>                    → Liste les environnements")
            print("       exec <app> help               → Affiche les détails")
            sys.exit(1)
        
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
        
        self.env_spec = self.args[1]
        self.command = " ".join(self.args[2:]) if len(self.args) > 2 else ""
        
        if not self.command:
            print("❌ Commande manquante")
            print("Usage: exec <app> <env> <commande>")
            sys.exit(1)
        
        if self.env_spec == "all":
            self.envs = self.config.get_envs(self.app)
        elif "," in self.env_spec:
            self.envs = [e.strip() for e in self.env_spec.split(",")]
        else:
            self.envs = [self.env_spec]
        
        available_envs = self.config.get_envs(self.app)
        invalid_envs = [e for e in self.envs if e not in available_envs]
        if invalid_envs:
            print(f"❌ Environnement(s) inconnu(s) : {', '.join(invalid_envs)}")
            self.list_envs(self.app)
            sys.exit(1)
    
    def run(self):
        """Exécute la commande sur tous les environnements"""
        self.parse_args()
        password = self.get_password()
        
        manager = SessionManager(
            app=self.app,
            envs=self.envs,
            command=self.command,
            password=password
        )
        manager.run_parallel()

def main():
    """Point d'entrée pour l'outil exec"""
    tool = ExecTool(sys.argv[1:])
    tool.run()

if __name__ == "__main__":
    main()
