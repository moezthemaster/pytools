#!/usr/bin/env python3
"""Outil de copie de fichiers/répertoires entre local et remote"""

import sys
import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4
from src.lib.base import BaseTool
from src.lib.ssh import SSHExecutor
from src.lib.env import env

class CopyTool(BaseTool):
    """Copie des fichiers/répertoires entre local et remote"""
    
    def __init__(self, args):
        super().__init__(args)
        self.recursive = False
        self.target_user = None
        self.mode = None
        self.verbose = False
        self.force = False
        self.preserve = False
        
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
            elif arg == "--mode":
                if i + 1 < len(self.args):
                    self.mode = self.args[i + 1]
                    # Valider le mode
                    try:
                        int(self.mode, 8)
                    except ValueError:
                        print(f"❌ Mode invalide : {self.mode} (ex: 644, 755)")
                        sys.exit(1)
                    i += 2
                else:
                    print("❌ L'option --mode nécessite une valeur (ex: 644)")
                    sys.exit(1)
            elif arg in ["-p", "--preserve"]:
                self.preserve = True
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
    -r, --recursive         Copie récursive (répertoires)
    -u, --user <user>       Utilisateur cible pour la copie (ex: root, devops)
    --mode <mode>           Permissions finales (ex: 600, 644, 755)
    -p, --preserve          Préserve les permissions source
    -v, --verbose           Mode verbeux (affiche la progression)
    -f, --force             Force la copie (écrase les fichiers existants)
    -h, --help              Affiche cette aide

EXEMPLES:
    # Remote → Local
    copy appli1:prod:/var/log/app.log ./logs/
    copy appli1:prod:/etc/nginx /tmp/nginx-backup -r -u root --mode 755

    # Local → Remote
    copy ./mon_script.sh appli1:prod:/tmp/ -u devops --mode 755
    copy ./conf/ appli1:prod:/etc/app/ -r -u root --mode 644

    # Remote → Remote (via local)
    copy appli1:prod:/etc/config.yml appli2:recette:/etc/config.yml -u root --mode 600
    copy appli1:prod:/var/www/ appli2:recette:/var/www/ -r -u root --mode 755
""")
    
    def run(self):
        """Exécute la copie selon le flux détecté"""
        self.parse_args()
        
        # Demander le mot de passe si on a besoin de SSH
        if self.src_type == "remote" or self.dst_type == "remote":
            self.password = self.get_password()
        
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
    
    def _execute_ssh(self, app, env, command):
        """Exécute une commande SSH et retourne le résultat"""
        user, host, port = self._get_remote_info(app, env)
        
        ssh = SSHExecutor(self.password)
        client = ssh.connect(host, user, port)
        
        if isinstance(client, dict) and 'error' in client:
            return {'code': -1, 'stdout': '', 'stderr': client['error']}
        
        result = ssh.exec_command(client, command)
        client.close()
        return result
    
    def _get_default_group(self, app, env, user):
        """Récupère le groupe par défaut d'un utilisateur"""
        cmd = f"dersudo du- root -c 'id -gn {user}'"
        result = self._execute_ssh(app, env, cmd)
        if result['code'] == 0:
            return result['stdout'].strip()
        return user
    
    def _set_remote_permissions(self, app, env, path, user, mode):
        """Définit le propriétaire et les permissions sur un fichier remote"""
        # Récupérer le groupe par défaut
        group = self._get_default_group(app, env, user)
        
        # Changer le propriétaire
        cmd = f"dersudo du- root -c 'chown {user}:{group} {path}'"
        result = self._execute_ssh(app, env, cmd)
        if result['code'] != 0:
            print(f"⚠️  Impossible de changer le propriétaire: {result['stderr']}")
        
        # Changer les permissions
        if mode:
            cmd = f"dersudo du- root -c 'chmod {mode} {path}'"
            result = self._execute_ssh(app, env, cmd)
            if result['code'] != 0:
                print(f"⚠️  Impossible de changer les permissions: {result['stderr']}")
    
    def _copy_remote_to_local(self):
        """Copie d'un remote vers le local"""
        print(f"📥 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.destination}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")
        
        # Déterminer la destination finale
        dst_is_dir = os.path.isdir(self.destination) or self.destination.endswith('/')
        if dst_is_dir:
            base_name = os.path.basename(self.src_path)
            dest_path = os.path.join(self.destination, base_name)
        else:
            dest_path = self.destination
        
        if self.target_user:
            self._copy_remote_to_local_with_sudo(dest_path)
        else:
            self._copy_remote_to_local_without_sudo(dest_path)
        
        # Appliquer les permissions locales si mode spécifié
        if self.mode and os.path.exists(dest_path):
            os.chmod(dest_path, int(self.mode, 8))
    
    def _copy_remote_to_local_without_sudo(self, dest_path):
        """Copie sans changement d'utilisateur (scp direct)"""
        user, host, port = self._get_remote_info(self.src_app, self.src_env)
        
        cmd = f"scp -P {port} {user}@{host}:{self.src_path} {dest_path}"
        if self.verbose:
            cmd = f"scp -v -P {port} {user}@{host}:{self.src_path} {dest_path}"
        
        print(f"🔧 {cmd}")
        result = subprocess.call(cmd, shell=True)
        
        if result != 0:
            print(f"❌ Erreur lors de la copie")
            sys.exit(1)
        
        print(f"✅ Copie réussie : {dest_path}")
    
    def _copy_remote_to_local_with_sudo(self, dest_path):
        """Copie avec changement d'utilisateur (via /tmp + scp)"""
        user, host, port = self._get_remote_info(self.src_app, self.src_env)
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}"
        
        try:
            if self.recursive:
                # Répertoire : utiliser tar
                print("📦 Compression du répertoire...")
                cmd = f"dersudo du- {self.target_user} -c 'tar czf {remote_temp} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}'"
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result['code'] != 0:
                    raise Exception(f"Erreur lors de la compression: {result['stderr']}")
            else:
                # Fichier : copie simple
                cmd = f"dersudo du- {self.target_user} -c 'cp {self.src_path} {remote_temp}'"
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result['code'] != 0:
                    raise Exception(f"Erreur lors de la copie vers /tmp: {result['stderr']}")
            
            # Ouvrir les droits pour lecture
            cmd = f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp}'"
            self._execute_ssh(self.src_app, self.src_env, cmd)
            
            # Télécharger avec scp
            print("📤 Téléchargement...")
            scp_cmd = f"scp -P {port} {user}@{host}:{remote_temp} {dest_path}"
            if self.verbose:
                scp_cmd = f"scp -v -P {port} {user}@{host}:{remote_temp} {dest_path}"
            result = subprocess.call(scp_cmd, shell=True)
            
            if result != 0:
                raise Exception("Erreur lors du téléchargement")
            
            # Si c'était un répertoire, extraire
            if self.recursive:
                print("📦 Extraction...")
                os.makedirs(dest_path, exist_ok=True)
                subprocess.call(f"tar xzf {dest_path} -C {os.path.dirname(dest_path)}", shell=True)
                os.remove(dest_path)
            
            print(f"✅ Copie réussie : {dest_path}")
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique
            print("🧹 Nettoyage...")
            self._execute_ssh(self.src_app, self.src_env, f"rm -f {remote_temp}")
    
    def _copy_local_to_remote(self):
        """Copie du local vers un remote"""
        print(f"📤 Copie de {self.source} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")
        
        # Vérifier si source est un répertoire
        if os.path.isdir(self.source):
            if not self.recursive:
                print(f"❌ {self.source} est un répertoire. Utilisez -r pour copier récursivement.")
                sys.exit(1)
            self._copy_local_dir_to_remote()
        else:
            if self.target_user:
                self._copy_local_file_to_remote_with_sudo()
            else:
                self._copy_local_file_to_remote_without_sudo()
    
    def _copy_local_file_to_remote_without_sudo(self):
        """Copie sans changement d'utilisateur (scp direct)"""
        user, host, port = self._get_remote_info(self.dst_app, self.dst_env)
        
        cmd = f"scp -P {port} {self.source} {user}@{host}:{self.dst_path}"
        if self.verbose:
            cmd = f"scp -v -P {port} {self.source} {user}@{host}:{self.dst_path}"
        
        print(f"🔧 {cmd}")
        result = subprocess.call(cmd, shell=True)
        
        if result != 0:
            print(f"❌ Erreur lors de la copie")
            sys.exit(1)
        
        print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
    
    def _copy_local_file_to_remote_with_sudo(self):
        """Copie avec changement d'utilisateur (via /tmp + scp)"""
        user, host, port = self._get_remote_info(self.dst_app, self.dst_env)
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}"
        
        try:
            # Upload vers /tmp
            print("📤 Upload vers /tmp...")
            scp_cmd = f"scp -P {port} {self.source} {user}@{host}:{remote_temp}"
            if self.verbose:
                scp_cmd = f"scp -v -P {port} {self.source} {user}@{host}:{remote_temp}"
            result = subprocess.call(scp_cmd, shell=True)
            
            if result != 0:
                raise Exception("Erreur lors de l'upload")
            
            # Créer le répertoire destination si nécessaire
            dst_dir = os.path.dirname(self.dst_path)
            if dst_dir:
                cmd = f"dersudo du- {self.target_user} -c 'mkdir -p {dst_dir}'"
                self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            # Copier vers la destination finale
            print("📥 Copie vers la destination...")
            cmd = f"dersudo du- {self.target_user} -c 'cp {remote_temp} {self.dst_path}'"
            result = self._execute_ssh(self.dst_app, self.dst_env, cmd)
            if result['code'] != 0:
                raise Exception(f"Erreur lors de la copie vers {self.dst_path}: {result['stderr']}")
            
            # Appliquer les permissions et le propriétaire
            self._set_remote_permissions(self.dst_app, self.dst_env, self.dst_path, self.target_user, self.mode)
            
            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique
            print("🧹 Nettoyage...")
            self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_temp}")
    
    def _copy_local_dir_to_remote(self):
        """Copie un répertoire local vers le remote"""
        user, host, port = self._get_remote_info(self.dst_app, self.dst_env)
        temp_name = f"tmp_copy_{uuid4().hex}"
        local_temp = f"/tmp/{temp_name}.tar.gz"
        remote_temp = f"/tmp/{temp_name}.tar.gz"
        
        try:
            # Créer un tar du répertoire local
            print("📦 Compression du répertoire local...")
            subprocess.call(f"tar czf {local_temp} -C {os.path.dirname(self.source)} {os.path.basename(self.source)}", shell=True)
            
            # Upload vers /tmp sur le remote
            print("📤 Upload vers /tmp...")
            scp_cmd = f"scp -P {port} {local_temp} {user}@{host}:{remote_temp}"
            if self.verbose:
                scp_cmd = f"scp -v -P {port} {local_temp} {user}@{host}:{remote_temp}"
            result = subprocess.call(scp_cmd, shell=True)
            
            if result != 0:
                raise Exception("Erreur lors de l'upload")
            
            # Créer le répertoire destination
            print("📥 Création du répertoire destination...")
            cmd = f"dersudo du- {self.target_user} -c 'mkdir -p {self.dst_path}'"
            self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            # Extraire le tar sur le remote
            print("📦 Extraction sur le remote...")
            cmd = f"dersudo du- {self.target_user} -c 'tar xzf {remote_temp} -C {self.dst_path}'"
            result = self._execute_ssh(self.dst_app, self.dst_env, cmd)
            if result['code'] != 0:
                raise Exception(f"Erreur lors de l'extraction: {result['stderr']}")
            
            # Appliquer les permissions récursivement
            if self.mode or self.target_user:
                print("🔒 Application des permissions...")
                if self.target_user:
                    group = self._get_default_group(self.dst_app, self.dst_env, self.target_user)
                    cmd = f"dersudo du- root -c 'chown -R {self.target_user}:{group} {self.dst_path}'"
                    self._execute_ssh(self.dst_app, self.dst_env, cmd)
                if self.mode:
                    cmd = f"dersudo du- root -c 'chmod -R {self.mode} {self.dst_path}'"
                    self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage
            print("🧹 Nettoyage...")
            self._execute_ssh(self
