#!/usr/bin/env python3
"""Point d'entrée principal du package"""

import sys
from src.tools.connect import ConnectTool
from src.tools.exec import ExecTool

def main():
    if len(sys.argv) < 2:
        print("📦 Sessions - Outils SSH multi-environnements")
        print()
        print("Commandes disponibles :")
        print("  connect <app> [env|help]  → Connexion SSH")
        print("  exec <app> [env|all|...] <commande>  → Exécution de commandes")
        print()
        print("Exemples :")
        print("  connect appli1 prod")
        print("  exec appli1 all 'df -h'")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "connect":
        ConnectTool(sys.argv[2:]).run()
    elif command == "exec":
        ExecTool(sys.argv[2:]).run()
    else:
        print(f"❌ Commande inconnue : {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
