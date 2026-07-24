#!/bin/bash
# ======================================================================
# 📦 Installation du package sessions avec virtualenv + .env
# ======================================================================

set -e

echo "======================================================================"
echo "📦 Installation du package sessions"
echo "======================================================================"

USER_HOME="$HOME"
PROJECT_DIR="$USER_HOME/.sessions"
BIN_DIR="$USER_HOME/bin"

# Création des dossiers
echo "📁 Création des dossiers..."
mkdir -p "$PROJECT_DIR/src/lib"
mkdir -p "$PROJECT_DIR/src/tools"
mkdir -p "$PROJECT_DIR/bin"
mkdir -p "$PROJECT_DIR/sessions"
mkdir -p "$BIN_DIR"

# Vérification de Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi
echo "✅ Python 3 trouvé : $(python3 --version)"

# Création du virtualenv
echo "📁 Création du virtualenv dans $PROJECT_DIR/venv..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
else
    echo "✅ Virtualenv déjà existant"
fi

# Installation des dépendances
echo "📦 Installation des dépendances..."
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# Copie des fichiers source
echo "📝 Copie des fichiers source..."

# Création du .env.example
cat > "$PROJECT_DIR/.env.example" << 'EOF'
# ======================================================================
# Configuration du package sessions
# ======================================================================

# Répertoire des fichiers INI (par défaut ~/.sessions/sessions)
SESSIONS_CONFIG_DIR=~/.sessions/sessions

# Timeout de connexion SSH (secondes)
SSH_TIMEOUT=10

# Timeout d'exécution des commandes (secondes)
SSH_COMMAND_TIMEOUT=30

# Afficher les couleurs (true/false)
DISPLAY_COLORS=true

# Nombre maximal de connexions parallèles
MAX_PARALLEL_WORKERS=10

# Répertoire des backups (pour sync-env)
BACKUP_DIR=~/backups/sessions

# Niveau de log (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
EOF

# Création du .env par défaut si non existant
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "✅ .env créé par défaut"
fi

# Création du requirements.txt
cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
paramiko>=3.0.0
python-dotenv>=1.0.0
colorama>=0.4.0
EOF

# Création des wrappers bin
cat > "$PROJECT_DIR/bin/connect" << 'EOF'
#!/bin/bash
PROJECT_DIR="$HOME/.sessions"
source "$PROJECT_DIR/venv/bin/activate"
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from src.tools.connect import main
main()
" "$@"
EOF

cat > "$PROJECT_DIR/bin/exec" << 'EOF'
#!/bin/bash
PROJECT_DIR="$HOME/.sessions"
source "$PROJECT_DIR/venv/bin/activate"
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from src.tools.exec import main
main()
" "$@"
EOF

chmod +x "$PROJECT_DIR/bin/connect"
chmod +x "$PROJECT_DIR/bin/exec"

# Liens symboliques dans ~/bin
ln -sf "$PROJECT_DIR/bin/connect" "$BIN_DIR/connect"
ln -sf "$PROJECT_DIR/bin/exec" "$BIN_DIR/exec"

# Création d'un exemple de fichier INI
cat > "$PROJECT_DIR/sessions/exemple.ini" << 'EOF'
[prod]
host=192.168.1.10
user=admin
description=Environnement de production

[dev]
host=192.168.1.11
user=admin
port=2222
description=Environnement de développement

[recette]
host=192.168.1.12
user=test
description=Environnement de recette
EOF

echo ""
echo "======================================================================"
echo "✅ Installation terminée !"
echo "======================================================================"
echo ""
echo "📁 Fichiers installés dans : $PROJECT_DIR"
echo "📁 Fichiers INI : $PROJECT_DIR/sessions/"
echo "📁 Fichiers source : $PROJECT_DIR/src/"
echo "⚙️  Configuration : $PROJECT_DIR/.env (modifie-la si besoin)"
echo "🔗 Commandes disponibles : connect, exec"
echo ""
echo "📝 Exemple de fichier INI créé : $PROJECT_DIR/sessions/exemple.ini"
echo "   Copie-le et adapte-le : cp exemple.ini monappli.ini"
echo ""
echo "🚀 Utilisation :"
echo "   connect monappli           # Liste les environnements"
echo "   connect monappli help      # Affiche les détails"
echo "   connect monappli prod      # Connexion SSH"
echo ""
echo "   exec monappli all 'df -h'  # Exécute sur tous les envs"
echo "   exec monappli prod 'uptime' # Exécute sur un env"
echo "   exec monappli dev,recette 'ls' # Exécute sur plusieurs"
echo ""
echo "⚙️  Pour modifier la configuration : nano ~/.sessions/.env"
echo "======================================================================"
