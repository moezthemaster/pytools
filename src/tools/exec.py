#!/usr/bin/env python3
"""Outil d'exécution de commandes sur plusieurs environnements"""

import sys
from src.lib.base import BaseTool
from src.lib.session import SessionManager

class ExecTool(BaseTool):
    """Exécute une commande sur un ou plusieurs environnements"""
    
    def parse_args(self):
        """Parse les arguments avec support de -u/--user"""
        
        # Si pas assez d'arguments
        if len(self.args) < 2:
            print("Usage: exec <app> [<env>|all|env1,env2] <commande> [options]")
            print("       exec <app>                    → Liste les environnements")
            print("       exec <app> help               → Affiche les détails")
            print("")
            print("Options:")
            print("  -u, --user <user>   Exécute la commande en tant qu'utilisateur")
            print("")
            print("Exemples:")
            print("  exec appli1 prod 'df -h'")
            print("  exec appli1 prod 'cat /etc/passwd' -u root")
            print("  exec appli1 all 'ls -la' -u devops")
            sys.exit(1)
        
        # Récupérer l'app (toujours en position 0)
        self.app = self.args[0]
        
        # Vérifier que l'app existe
        if not self.config.app_exists(self.app):
            print(f"❌ Application '{self.app}' inconnue")
            self.list_apps()
            sys.exit(1)
        
        # Si seulement l'app est fournie
        if len(self.args) == 1:
            self.list_envs(self.app)
            sys.exit(0)
        
        # Si help
        if self.args[1] in ["help", "-h"] and len(self.args) == 2:
            self.show_help(self.app)
            sys.exit(0)
        
        # Extraire l'environnement (position 1)
        self.env_spec = self.args[1]
        
        # Chercher l'option -u ou --user dans les arguments
        self.target_user = None
        self.command_parts = []
        
        i = 2
        while i < len(self.args):
            arg = self.args[i]
            if arg in ["-u", "--user"]:
                if i + 1 < len(self.args):
                    self.target_user = self.args[i + 1]
                    i += 2  # Saute l'option et sa valeur
                else:
                    print("❌ L'option -u nécessite un nom d'utilisateur")
                    sys.exit(1)
            else:
                self.command_parts.append(arg)
                i += 1
        
        self.command = " ".join(self.command_parts) if self.command_parts else ""
        
        if not self.command:
            print("❌ Commande manquante")
            print("Usage: exec <app> <env> <commande> [-u user]")
            sys.exit(1)
        
        # Résoudre la spécification des environnements
        if self.env_spec == "all":
            self.envs = self.config.get_envs(self.app)
        elif "," in self.env_spec:
            self.envs = [e.strip() for e in self.env_spec.split(",")]
        else:
            self.envs = [self.env_spec]
        
        # Vérifier que les environnements existent
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
        
        # Ajouter le changement d'utilisateur si demandé
        final_command = self.command
        if self.target_user:
            final_command = f"dersudo du- {self.target_user} -c \"{self.command}\""
            self.logger.info(f"👤 Exécution en tant que : {self.target_user}")
        
        manager = SessionManager(
            app=self.app,
            envs=self.envs,
            command=final_command,
            password=password,
            target_user=self.target_user  # Pour l'affichage
        )
        manager.run_parallel()

def main():
    """Point d'entrée pour l'outil exec"""
    tool = ExecTool(sys.argv[1:])
    tool.run()

if __name__ == "__main__":
    main()
