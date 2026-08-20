#!/usr/bin/env python3
"""Outil de copie de fichiers/répertoires entre local et remote"""

import sys
import os
import tempfile
import subprocess
import shutil
from pathlib import Path
from uuid import uuid4
from src.lib.base import BaseTool
from src.lib.ssh import SSHExecutor
from src.lib.session import SessionManager
from src.lib.env import env

class CopyTool(BaseTool):
    """Copie des fichiers/répertoires entre local et remote"""
    
    def __init__(self, args):
        super().__init__(args)
        self.recursive = False
        self.target_user = None
        self.preserve_perms = False
        self.verbose = False
        self.force = False
        
    def parse_args(self):
        """Parse les arguments de la commande copy"""
        
        if len(self.args) < 2:
            self.print_usage()
            sys.exit(1)
        
        # Extraire les options
        i = 0
        args_clean = []
        while i < len(self.args):
            arg = self.args[i]
            
            if arg in ["-r", "--recursive"]:
                self.recursive = True
                i += 1
            elif arg in ["-u", "--user"]:
                if i + 1 < len(self.args):
                    self.target_user = self.args[i + 1]
                    i += 2
                else:
                    print("❌ L'option -u nécessite un nom d'utilisateur")
                    sys.exit(1)
            elif arg in ["-p", "--preserve"]:
                self.preserve_perms = True
                i += 1
            elif arg in ["-v", "--verbose"]:
                self.verbose = True
                i += 1
            elif arg in ["-f", "--force"]:
                self.force = True
                i += 1
            elif arg in ["-h", "--help"]:
                self.print_usage()
                sys.exit(0)
            else:
                args_clean.append(arg)
                i += 1
        
        if len(args_clean) < 2:
            print("❌ Source et destination requises")
            self.print_usage()
            sys.exit(1)
        
        self.source = args_clean[0]
        self.destination = args_clean[1]
        
        # Détecter le type de source/destination
        self.src_type = self._detect_type(self.source)
        self.dst_type = self._detect_type(self.destination)
        
        # Déterminer le flux
        self.flow = self._determine_flow()
        
        # Si c'est un remote, extraire les infos
        if self.src_type == "remote":
            self.src_app, self.src_env, self.src_path = self._parse_remote(self.source)
            if not self.config.app_exists(self.src_app):
                print(f"❌ Application '{self.src_app}' inconnue")
                self.list_apps()
                sys.exit(1)
            if not self.config.env_exists(self.src_app, self.src_env):
                print(f"❌ Environnement '{self.src_env}' inconnu pour '{self.src_app}'")
                self.list_envs(self.src_app)
                sys.exit(1)
        
        if self.dst_type == "remote":
            self.dst_app, self.dst_env, self.dst_path = self._parse_remote(self.destination)
            if not self.config.app_exists(self.dst_app):
                print(f"❌ Application '{self.dst_app}' inconnue")
                self.list_apps()
                sys.exit(1)
            if not self.config.env_exists(self.dst_app, self.dst_env):
                print(f"❌ Environnement '{self.dst_env}' inconnu pour '{self.dst_app}'")
                self.list_envs(self.dst_app)
                sys.exit(1)
        
        # Vérifier que les chemins locaux existent
        if self.src_type == "local" and not os.path.exists(self.source):
            print(f"❌ Source locale inexistante : {self.source}")
            sys.exit(1)
        
        if self.dst_type == "local":
            # Vérifier que le répertoire destination existe
            dst_dir = os.path.dirname(self.destination) if os.path.dirname(self.destination) else "."
            if dst_dir and not os.path.exists(dst_dir):
                print(f"❌ Répertoire destination inexistant : {dst_dir}")
                sys.exit(1)
    
    def _detect_type(self, path):
        """Détecte si un chemin est local ou remote"""
        # Format remote : appli:env:/path
        if ":" in path and path.count(":") >= 2:
            return "remote"
        return "local"
    
    def _parse_remote(self, remote_path):
        """Parse un chemin remote au format appli:env:/path"""
        parts = remote_path.split(":", 2)
        if len(parts) != 3:
            print(f"❌ Format remote invalide : {remote_path}")
            print("   Format attendu : appli:env:/path")
            sys.exit(1)
        return parts[0], parts[1], parts[2]
    
    def _determine_flow(self):
        """Détermine le type de flux"""
        if self.src_type == "remote" and self.dst_type == "local":
            return "REMOTE_TO_LOCAL"
        elif self.src_type == "local" and self.dst_type == "remote":
            return "LOCAL_TO_REMOTE"
        elif self.src_type == "remote" and self.dst_type == "remote":
            return "REMOTE_TO_REMOTE"
        else:
            print(f"❌ Flux non supporté : {self.src_type} → {self.dst_type}")
            print("   Supporté : remote→local, local→remote, remote→remote")
            sys.exit(1)
    
    def print_usage(self):
        """Affiche l'aide"""
        print("""
📋 copy - Copie de fichiers/répertoires entre local et remote

USAGE:
    copy <source> <destination> [options]

FORMATS:
    Local   : /path/to/file  ou  ./relative/path
    Remote  : appli:env:/path/to/file

OPTIONS:
    -r, --recursive     Copie récursive (répertoires)
    -u, --user <user>   Utilisateur cible pour la copie (ex: root, devops)
    -p, --preserve      Préserve les permissions
    -v, --verbose       Mode verbeux
    -f, --force         Force la copie (écrase les fichiers existants)
    -h, --help          Affiche cette aide

EXEMPLES:
    # Remote → Local
    copy appli1:prod:/var/log/app.log ./logs/
    copy appli1:prod:/etc/nginx /tmp/nginx-backup -r -u root

    # Local → Remote
    copy ./mon_script.sh appli1:prod:/tmp/
    copy ./conf/ appli1:prod:/etc/app/ -r -u root

    # Remote → Remote (via local)
    copy appli1:prod:/etc/config.yml appli2:recette:/etc/config.yml -u root
    copy appli1:prod:/var/www/ appli2:recette:/var/www/ -r -u root
""")
    
    def run(self):
        """Exécute la copie selon le flux détecté"""
        self.parse_args()
        
        if self.flow == "REMOTE_TO_LOCAL":
            self._copy_remote_to_local()
        elif self.flow == "LOCAL_TO_REMOTE":
            self._copy_local_to_remote()
        elif self.flow == "REMOTE_TO_REMOTE":
            self._copy_remote_to_remote()
        else:
            print(f"❌ Flux non supporté : {self.flow}")
            sys.exit(1)
    
    def _get_remote_info(self, app, env):
        """Récupère les infos de connexion pour un remote"""
        info = self.config.get_connection_info(app, env)
        return info['user'], info['host'], info['port']
    
    def _execute_ssh(self, app, env, command, input_data=None):
        """Exécute une commande SSH et retourne le résultat"""
        user, host, port = self._get_remote_info(app, env)
        
        # Connexion SSH
        ssh = SSHExecutor(self.get_password())
        client = ssh.connect(host, user, port)
        
        if isinstance(client, dict) and 'error' in client:
            print(f"❌ Erreur de connexion à {app}:{env} : {client['error']}")
            return None
        
        # Si commande avec input, utiliser stdin
        if input_data:
            stdin, stdout, stderr = client.exec_command(command)
            stdin.write(input_data)
            stdin.flush()
            stdin.channel.shutdown_write()
        else:
            stdin, stdout, stderr = client.exec_command(command)
        
        result = {
            'stdout': stdout.read().decode(),
            'stderr': stderr.read().decode(),
            'code': stdout.channel.recv_exit_status()
        }
        
        client.close()
        return result
    
    def _copy_remote_to_local(self):
        """Copie d'un remote vers le local"""
        print(f"📥 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.destination}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        
        # Vérifier si destination est un répertoire
        dst_is_dir = os.path.isdir(self.destination) or self.destination.endswith('/')
        if dst_is_dir:
            # Déterminer le nom du fichier/répertoire
            base_name = os.path.basename(self.src_path)
            dest_path = os.path.join(self.destination, base_name)
        else:
            dest_path = self.destination
        
        # Si c'est un répertoire et qu'on n'a pas -r
        if self.recursive:
            self._copy_remote_dir_to_local(dest_path)
        else:
            self._copy_remote_file_to_local(dest_path)
    
    def _copy_remote_file_to_local(self, dest_path):
        """Copie un fichier remote vers le local"""
        # Construire la commande de lecture
        if self.target_user:
            cmd = f"dersudo du- {self.target_user} -c \"cat {self.src_path}\""
        else:
            cmd = f"cat {self.src_path}"
        
        # Exécuter la commande et récupérer le contenu
        result = self._execute_ssh(self.src_app, self.src_env, cmd)
        
        if result is None:
            sys.exit(1)
        
        if result['code'] != 0:
            print(f"❌ Erreur lors de la lecture de {self.src_path}")
            print(result['stderr'])
            sys.exit(1)
        
        # Écrire le fichier localement
        try:
            with open(dest_path, 'w') as f:
                f.write(result['stdout'])
            print(f"✅ Copie réussie : {dest_path}")
        except Exception as e:
            print(f"❌ Erreur lors de l'écriture locale : {e}")
            sys.exit(1)
    
    def _copy_remote_dir_to_local(self, dest_path):
        """Copie un répertoire remote vers le local"""
        # Utiliser tar pour compresser le répertoire
        if self.target_user:
            cmd = f"dersudo du- {self.target_user} -c \"tar czf - -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}\""
        else:
            cmd = f"tar czf - -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
        
        result = self._execute_ssh(self.src_app, self.src_env, cmd)
        
        if result is None:
            sys.exit(1)
        
        if result['code'] != 0:
            print(f"❌ Erreur lors de la lecture du répertoire {self.src_path}")
            print(result['stderr'])
            sys.exit(1)
        
        # Sauvegarder le tar
        tar_file = f"/tmp/copy_{uuid4().hex}.tar.gz"
        try:
            with open(tar_file, 'w') as f:
                f.write(result['stdout'])
            
            # Extraire le tar
            os.makedirs(dest_path, exist_ok=True)
            subprocess.call(f"tar xzf {tar_file} -C {dest_path}", shell=True)
            
            print(f"✅ Copie réussie : {dest_path}")
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction : {e}")
            sys.exit(1)
        finally:
            # Nettoyer
            if os.path.exists(tar_file):
                os.remove(tar_file)
    
    def _copy_local_to_remote(self):
        """Copie du local vers un remote"""
        print(f"📤 Copie de {self.source} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        
        # Vérifier si source est un répertoire
        if os.path.isdir(self.source):
            if not self.recursive:
                print(f"❌ {self.source} est un répertoire. Utilisez -r pour copier récursivement.")
                sys.exit(1)
            self._copy_local_dir_to_remote()
        else:
            self._copy_local_file_to_remote()
    
    def _copy_local_file_to_remote(self):
        """Copie un fichier local vers le remote"""
        # Lire le fichier local
        try:
            with open(self.source, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Erreur lors de la lecture de {self.source} : {e}")
            sys.exit(1)
        
        # Construire la commande d'écriture
        if self.target_user:
            cmd = f"dersudo du- {self.target_user} -c \"cat > {self.dst_path}\""
        else:
            cmd = f"cat > {self.dst_path}"
        
        # Exécuter la commande avec input
        result = self._execute_ssh(self.dst_app, self.dst_env, cmd, content)
        
        if result is None:
            sys.exit(1)
        
        if result['code'] != 0:
            print(f"❌ Erreur lors de l'écriture de {self.dst_path}")
            print(result['stderr'])
            sys.exit(1)
        
        print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
    
    def _copy_local_dir_to_remote(self):
        """Copie un répertoire local vers le remote"""
        # Créer un tar du répertoire local
        tar_file = f"/tmp/copy_{uuid4().hex}.tar.gz"
        try:
            subprocess.call(f"tar czf {tar_file} -C {os.path.dirname(self.source)} {os.path.basename(self.source)}", shell=True)
            
            # Lire le tar
            with open(tar_file, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Erreur lors de la création du tar : {e}")
            sys.exit(1)
        finally:
            if os.path.exists(tar_file):
                os.remove(tar_file)
        
        # Créer le répertoire destination
        if self.target_user:
            mkdir_cmd = f"dersudo du- {self.target_user} -c \"mkdir -p {self.dst_path}\""
        else:
            mkdir_cmd = f"mkdir -p {self.dst_path}"
        
        result = self._execute_ssh(self.dst_app, self.dst_env, mkdir_cmd)
        if result is None or result['code'] != 0:
            print(f"❌ Erreur lors de la création du répertoire destination")
            sys.exit(1)
        
        # Extraire le tar sur le remote
        if self.target_user:
            cmd = f"dersudo du- {self.target_user} -c \"tar xzf - -C {self.dst_path}\""
        else:
            cmd = f"tar xzf - -C {self.dst_path}"
        
        result = self._execute_ssh(self.dst_app, self.dst_env, cmd, content)
        
        if result is None:
            sys.exit(1)
        
        if result['code'] != 0:
            print(f"❌ Erreur lors de l'extraction sur {self.dst_path}")
            print(result['stderr'])
            sys.exit(1)
        
        print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
    
    def _copy_remote_to_remote(self):
        """Copie entre deux remotes via le local"""
        print(f"📤 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        
        # Créer un fichier temporaire local
        temp_file = f"/tmp/copy_{uuid4().hex}"
        
        try:
            # Étape 1 : Remote1 → Local
            print("📥 Téléchargement depuis la source...")
            
            if self.recursive:
                # Pour répertoire, utiliser tar
                if self.target_user:
                    cmd = f"dersudo du- {self.target_user} -c \"tar czf - -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}\""
                else:
                    cmd = f"tar czf - -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
                
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result is None or result['code'] != 0:
                    print(f"❌ Erreur lors de la lecture de {self.src_path}")
                    sys.exit(1)
                
                with open(temp_file + '.tar.gz', 'w') as f:
                    f.write(result['stdout'])
            else:
                # Pour fichier, utiliser cat
                if self.target_user:
                    cmd = f"dersudo du- {self.target_user} -c \"cat {self.src_path}\""
                else:
                    cmd = f"cat {self.src_path}"
                
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result is None or result['code'] != 0:
                    print(f"❌ Erreur lors de la lecture de {self.src_path}")
                    sys.exit(1)
                
                with open(temp_file, 'w') as f:
                    f.write(result['stdout'])
            
            # Étape 2 : Local → Remote2
            print("📤 Envoi vers la destination...")
            
            if self.recursive:
                # Extraire le tar sur le remote
                if self.target_user:
                    mkdir_cmd = f"dersudo du- {self.target_user} -c \"mkdir -p {self.dst_path}\""
                else:
                    mkdir_cmd = f"mkdir -p {self.dst_path}"
                
                result = self._execute_ssh(self.dst_app, self.dst_env, mkdir_cmd)
                if result is None or result['code'] != 0:
                    print(f"❌ Erreur lors de la création du répertoire destination")
                    sys.exit(1)
                
                with open(temp_file + '.tar.gz', 'r') as f:
                    content = f.read()
                
                if self.target_user:
                    cmd = f"dersudo du- {self.target_user} -c \"tar xzf - -C {self.dst_path}\""
                else:
                    cmd = f"tar xzf - -C {self.dst_path}"
                
                result = self._execute_ssh(self.dst_app, self.dst_env, cmd, content)
            else:
                # Envoyer le fichier
                with open(temp_file, 'r') as f:
                    content = f.read()
                
                if self.target_user:
                    cmd = f"dersudo du- {self.target_user} -c \"cat > {self.dst_path}\""
                else:
                    cmd = f"cat > {self.dst_path}"
                
                result = self._execute_ssh(self.dst_app, self.dst_env, cmd, content)
            
            if result is None or result['code'] != 0:
                print(f"❌ Erreur lors de l'envoi vers {self.dst_path}")
                if result:
                    print(result['stderr'])
                sys.exit(1)
            
            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
            
        except Exception as e:
            print(f"❌ Erreur lors de la copie : {e}")
            sys.exit(1)
        finally:
            # Nettoyage des fichiers temporaires
            for f in [temp_file, temp_file + '.tar.gz']:
                if os.path.exists(f):
                    os.remove(f)

def main():
    """Point d'entrée pour l'outil copy"""
    tool = CopyTool(sys.argv[1:])
    tool.run()

if __name__ == "__main__":
    main()
