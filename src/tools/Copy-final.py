#!/usr/bin/env python3
"""Outil de copie de fichiers/répertoires entre local et remote (100% paramiko)"""

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
    """Copie des fichiers/répertoires entre local et remote avec paramiko"""
    
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
            dst_dir = os.path.dirname(self.destination) if os.path.dirname(self.destination) else "."
            if dst_dir and not os.path.exists(dst_dir):
                print(f"❌ Répertoire destination inexistant : {dst_dir}")
                sys.exit(1)
    
    def _detect_type(self, path):
        """Détecte si un chemin est local ou remote"""
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
    
    def _get_ssh_client(self, app, env):
        """Obtient un client SSH pour un remote"""
        user, host, port = self._get_remote_info(app, env)
        ssh = SSHExecutor(self.password)
        client = ssh.connect(host, user, port)
        if isinstance(client, dict) and 'error' in client:
            raise Exception(f"Erreur de connexion à {app}:{env}: {client['error']}")
        return client
    
    def _execute_ssh(self, app, env, command):
        """Exécute une commande SSH et retourne le résultat"""
        client = self._get_ssh_client(app, env)
        ssh = SSHExecutor(self.password)
        result = ssh.exec_command(client, command)
        client.close()
        return result
    
    def _sftp_transfer(self, client, src_path, dst_path, direction="download"):
        """Transfère un fichier via SFTP avec progression"""
        sftp = client.open_sftp()
        
        try:
            # Récupérer la taille du fichier pour la progression
            if direction == "download":
                file_size = sftp.stat(src_path).st_size
            else:
                file_size = os.path.getsize(src_path)
            
            transferred = 0
            
            def progress_callback(transferred_bytes, total_bytes):
                nonlocal transferred
                transferred = transferred_bytes
                if self.verbose and total_bytes > 0:
                    percent = (transferred_bytes / total_bytes) * 100
                    bar_length = 40
                    filled = int(bar_length * transferred_bytes / total_bytes)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    print(f'\r📊 {percent:.1f}% [{bar}] {transferred_bytes}/{total_bytes} octets', end='', flush=True)
            
            if direction == "download":
                sftp.get(src_path, dst_path, callback=progress_callback)
            else:
                sftp.put(src_path, dst_path, callback=progress_callback)
            
            if self.verbose:
                print()  # Nouvelle ligne après la progression
                
        finally:
            sftp.close()
    
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
    
    # ============================================================
    # REMOTE TO LOCAL
    # ============================================================
    
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
        """Copie sans changement d'utilisateur (SFTP direct)"""
        # Vérifier si c'est un répertoire
        test_cmd = f"if [ -d {self.src_path} ]; then echo 'directory'; else echo 'file'; fi"
        result = self._execute_ssh(self.src_app, self.src_env, test_cmd)
        is_directory = result['stdout'].strip() == 'directory'
        
        if is_directory and not self.recursive:
            print(f"❌ {self.src_path} est un répertoire. Utilisez -r pour copier récursivement.")
            sys.exit(1)
        
        client = self._get_ssh_client(self.src_app, self.src_env)
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}.tar.gz"
        local_tar = f"/tmp/{temp_name}.tar.gz"
        
        try:
            if is_directory:
                # Pour les répertoires, utiliser tar
                print("📦 Compression du répertoire source...")
                cmd = f"tar czf {remote_temp} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
                self._execute_ssh(self.src_app, self.src_env, cmd)
                
                # Télécharger le tar
                print("📥 Téléchargement du tar...")
                self._sftp_transfer(client, remote_temp, local_tar, direction="download")
                
                # Extraire localement
                print("📦 Extraction locale...")
                parent_dir = os.path.dirname(dest_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                    subprocess.call(f"tar xzf {local_tar} -C {parent_dir}", shell=True)
                else:
                    os.makedirs('/', exist_ok=True)
                    subprocess.call(f"tar xzf {local_tar} -C /", shell=True)
            else:
                # Fichier : SFTP direct
                self._sftp_transfer(client, self.src_path, dest_path, direction="download")
            
            print(f"✅ Copie réussie : {dest_path}")
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            if is_directory:
                # Nettoyer le tar remote
                self._execute_ssh(self.src_app, self.src_env, f"rm -f {remote_temp}")
                # Nettoyer le tar local
                if os.path.exists(local_tar):
                    os.remove(local_tar)
            client.close()
    
    def _copy_remote_to_local_with_sudo(self, dest_path):
        """Copie avec changement d'utilisateur (via /tmp + SFTP)"""
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}"
        local_tar = f"/tmp/{temp_name}.tar.gz"
        
        # Vérifier si c'est un répertoire
        test_cmd = f"if [ -d {self.src_path} ]; then echo 'directory'; else echo 'file'; fi"
        result = self._execute_ssh(self.src_app, self.src_env, test_cmd)
        is_directory = result['stdout'].strip() == 'directory'
        
        if is_directory and not self.recursive:
            print(f"❌ {self.src_path} est un répertoire. Utilisez -r pour copier récursivement.")
            sys.exit(1)
        
        try:
            if is_directory:
                # Répertoire : utiliser tar
                print("📦 Compression du répertoire source...")
                cmd = f"dersudo du- {self.target_user} -c 'tar czf {remote_temp} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}'"
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result['code'] != 0:
                    raise Exception(f"Erreur lors de la compression: {result['stderr']}")
                
                # Ouvrir les droits
                cmd = f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp}'"
                self._execute_ssh(self.src_app, self.src_env, cmd)
                
                # Télécharger le tar
                print("📥 Téléchargement du tar...")
                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    self._sftp_transfer(client, remote_temp, local_tar, direction="download")
                finally:
                    client.close()
                
                # Extraire localement
                print("📦 Extraction locale...")
                parent_dir = os.path.dirname(dest_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                    subprocess.call(f"tar xzf {local_tar} -C {parent_dir}", shell=True)
                else:
                    os.makedirs('/', exist_ok=True)
                    subprocess.call(f"tar xzf {local_tar} -C /", shell=True)
            else:
                # Fichier : copie simple
                print("📤 Copie vers /tmp sur le remote...")
                cmd = f"dersudo du- {self.target_user} -c 'cp {self.src_path} {remote_temp}'"
                result = self._execute_ssh(self.src_app, self.src_env, cmd)
                if result['code'] != 0:
                    raise Exception(f"Erreur lors de la copie vers /tmp: {result['stderr']}")
                
                # Ouvrir les droits
                cmd = f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp}'"
                self._execute_ssh(self.src_app, self.src_env, cmd)
                
                # Télécharger avec SFTP
                print("📥 Téléchargement...")
                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    self._sftp_transfer(client, remote_temp, dest_path, direction="download")
                finally:
                    client.close()
            
            print(f"✅ Copie réussie : {dest_path}")
            
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            # Nettoyer le fichier temporaire remote
            self._execute_ssh(self.src_app, self.src_env, f"rm -f {remote_temp}")
            # Nettoyer le tar local si présent
            if is_directory and os.path.exists(local_tar):
                os.remove(local_tar)
    
    # ============================================================
    # LOCAL TO REMOTE
    # ============================================================
    
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
        """Copie sans changement d'utilisateur (SFTP direct)"""
        client = self._get_ssh_client(self.dst_app, self.dst_env)
        
        try:
            # Créer le répertoire destination si nécessaire
            dst_dir = os.path.dirname(self.dst_path)
            if dst_dir:
                cmd = f"mkdir -p {dst_dir}"
                self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            print("📤 Upload...")
            self._sftp_transfer(client, self.source, self.dst_path, direction="upload")
            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
        finally:
            client.close()
    
    def _copy_local_file_to_remote_with_sudo(self):
        """Copie avec changement d'utilisateur (via /tmp + SFTP)"""
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}"
        
        try:
            # Upload vers /tmp
            print("📤 Upload vers /tmp...")
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                self._sftp_transfer(client, self.source, remote_temp, direction="upload")
            finally:
                client.close()
            
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
            print(f"\n❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_temp}")
    
    def _copy_local_dir_to_remote(self):
        """Copie un répertoire local vers le remote"""
        temp_name = f"tmp_copy_{uuid4().hex}"
        local_tar = f"/tmp/{temp_name}.tar.gz"
        remote_tar = f"/tmp/{temp_name}.tar.gz"
        
        try:
            # Créer un tar du répertoire local
            print("📦 Compression du répertoire local...")
            source_parent = os.path.dirname(self.source)
            source_basename = os.path.basename(self.source)
            
            if source_parent:
                subprocess.call(f"tar czf {local_tar} -C {source_parent} {source_basename}", shell=True)
            else:
                subprocess.call(f"tar czf {local_tar} -C / {source_basename}", shell=True)
            
            # Upload vers /tmp sur le remote
            print("📤 Upload vers /tmp...")
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                self._sftp_transfer(client, local_tar, remote_tar, direction="upload")
            finally:
                client.close()
            
            # Créer le répertoire destination
            print("📥 Création du répertoire destination...")
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'mkdir -p {self.dst_path}'"
            else:
                cmd = f"mkdir -p {self.dst_path}"
            self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            # Extraire le tar sur le remote
            print("📦 Extraction sur le remote...")
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'tar xzf {remote_tar} -C {self.dst_path}'"
            else:
                cmd = f"tar xzf {remote_tar} -C {self.dst_path}"
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
            print(f"\n❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_tar}")
            if os.path.exists(local_tar):
                os.remove(local_tar)
    
    # ============================================================
    # REMOTE TO REMOTE
    # ============================================================
    
    def _copy_remote_to_remote(self):
        """Copie entre deux remotes via le local"""
        print(f"📤 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")
        
        # Vérifier si la source est un répertoire
        test_cmd = f"if [ -d {self.src_path} ]; then echo 'directory'; else echo 'file'; fi"
        result = self._execute_ssh(self.src_app, self.src_env, test_cmd)
        is_directory = result['stdout'].strip() == 'directory'
        
        if is_directory and not self.recursive:
            print(f"❌ {self.src_path} est un répertoire. Utilisez -r pour copier récursivement.")
            sys.exit(1)
        
        # Créer un fichier/répertoire temporaire local
        temp_name = f"tmp_copy_{uuid4().hex}"
        local_temp = f"/tmp/{temp_name}"
        local_tar = f"/tmp/{temp_name}.tar.gz"
        remote_temp_src = None
        remote_temp_dst = None
        
        try:
            # ============================================================
            # ÉTAPE 1 : Remote1 → Local
            # ============================================================
            print("📥 Étape 1/2: Téléchargement depuis la source...")
            
            if self.target_user:
                # Avec sudo : copier vers /tmp sur le remote source
                remote_temp_src = f"/tmp/{temp_name}"
                
                if is_directory:
                    # Répertoire : compresser en tar
                    print("📦 Compression du répertoire source...")
                    cmd = f"dersudo du- {self.target_user} -c 'tar czf {remote_temp_src} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}'"
                    result = self._execute_ssh(self.src_app, self.src_env, cmd)
                    if result['code'] != 0:
                        raise Exception(f"Erreur lors de la compression: {result['stderr']}")
                    
                    # Ouvrir les droits
                    cmd = f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp_src}'"
                    self._execute_ssh(self.src_app, self.src_env, cmd)
                    
                    # Télécharger le tar
                    print("📥 Téléchargement du tar...")
                    client = self._get_ssh_client(self.src_app, self.src_env)
                    try:
                        self._sftp_transfer(client, remote_temp_src, local_tar, direction="download")
                    finally:
                        client.close()
                    
                    # Extraire le tar localement
                    print("📦 Extraction locale...")
                    os.makedirs(os.path.dirname(local_temp), exist_ok=True)
                    subprocess.call(f"tar xzf {local_tar} -C {os.path.dirname(local_temp)}", shell=True)
                    
                else:
                    # Fichier : copie simple
                    print("📤 Copie vers /tmp sur le remote...")
                    cmd = f"dersudo du- {self.target_user} -c 'cp {self.src_path} {remote_temp_src}'"
                    result = self._execute_ssh(self.src_app, self.src_env, cmd)
                    if result['code'] != 0:
                        raise Exception(f"Erreur lors de la copie vers /tmp: {result['stderr']}")
                    
                    # Ouvrir les droits
                    cmd = f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp_src}'"
                    self._execute_ssh(self.src_app, self.src_env, cmd)
                    
                    # Télécharger
                    print("📥 Téléchargement...")
                    client = self._get_ssh_client(self.src_app, self.src_env)
                    try:
                        self._sftp_transfer(client, remote_temp_src, local_temp, direction="download")
                    finally:
                        client.close()
                
            else:
                # Sans sudo : SFTP direct
                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    if is_directory:
                        # Pour un répertoire, on utilise tar sans sudo
                        remote_temp_src = f"/tmp/{temp_name}.tar.gz"
                        cmd = f"tar czf {remote_temp_src} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
                        self._execute_ssh(self.src_app, self.src_env, cmd)
                        
                        # Télécharger le tar
                        print("📥 Téléchargement du tar...")
                        self._sftp_transfer(client, remote_temp_src, local_tar, direction="download")
                        
                        # Extraire localement
                        print("📦 Extraction locale...")
                        os.makedirs(os.path.dirname(local_temp), exist_ok=True)
                        subprocess.call(f"tar xzf {local_tar} -C {os.path.dirname(local_temp)}", shell=True)
                    else:
                        # Fichier : SFTP direct
                        print("📥 Téléchargement...")
                        self._sftp_transfer(client, self.src_path, local_temp, direction="download")
                finally:
                    client.close()
            
            # Nettoyer le remote_temp_src (si utilisé)
            if remote_temp_src:
                self._execute_ssh(self.src_app, self.src_env, f"rm -f {remote_temp_src}")
                remote_temp_src = None
            
            # Nettoyer le tar local si présent
            if os.path.exists(local_tar):
                os.remove(local_tar)
            
            print(f"✅ Téléchargement terminé : {local_temp}")
            
            # ============================================================
            # ÉTAPE 2 : Local → Remote2
            # ============================================================
            print("📤 Étape 2/2: Envoi vers la destination...")
            
            # Déterminer si le fichier local est un répertoire
            is_local_dir = os.path.isdir(local_temp)
            
            if is_local_dir and not self.recursive:
                print(f"❌ {local_temp} est un répertoire. Utilisez -r pour copier récursivement.")
                sys.exit(1)
            
            if is_local_dir:
                # Copier un répertoire local vers remote
                self._copy_local_dir_to_remote_with_temp(local_temp)
            else:
                # Copier un fichier local vers remote
                if self.target_user:
                    self._copy_local_file_to_remote_with_sudo_temp(local_temp)
                else:
                    self._copy_local_file_to_remote_without_sudo_temp(local_temp)
            
            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")
            
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            
            # Nettoyer le fichier temporaire remote source s'il existe encore
            if remote_temp_src:
                self._execute_ssh(self.src_app, self.src_env, f"rm -f {remote_temp_src}")
            
            # Nettoyer le fichier temporaire remote destination s'il existe encore
            if remote_temp_dst:
                self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_temp_dst}")
            
            # Nettoyer les fichiers temporaires locaux
            if os.path.exists(local_temp):
                if os.path.isdir(local_temp):
                    shutil.rmtree(local_temp)
                else:
                    os.remove(local_temp)
            if os.path.exists(local_tar):
                os.remove(local_tar)
    
    # ============================================================
    # FONCTIONS AUXILIAIRES POUR REMOTE-TO-REMOTE
    # ============================================================
    
    def _copy_local_file_to_remote_without_sudo_temp(self, local_path):
        """Copie un fichier local vers remote sans sudo (pour remote-to-remote)"""
        client = self._get_ssh_client(self.dst_app, self.dst_env)
        
        try:
            # Créer le répertoire destination si nécessaire
            dst_dir = os.path.dirname(self.dst_path)
            if dst_dir:
                cmd = f"mkdir -p {dst_dir}"
                self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            print("📤 Upload...")
            self._sftp_transfer(client, local_path, self.dst_path, direction="upload")
        finally:
            client.close()
    
    def _copy_local_file_to_remote_with_sudo_temp(self, local_path):
        """Copie un fichier local vers remote avec sudo (pour remote-to-remote)"""
        temp_name = f"tmp_copy_{uuid4().hex}"
        remote_temp = f"/tmp/{temp_name}"
        
        try:
            # Upload vers /tmp
            print("📤 Upload vers /tmp...")
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                self._sftp_transfer(client, local_path, remote_temp, direction="upload")
            finally:
                client.close()
            
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
            
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_temp}")
    
    def _copy_local_dir_to_remote_with_temp(self, local_path):
        """Copie un répertoire local vers remote (pour remote-to-remote)"""
        temp_name = f"tmp_copy_{uuid4().hex}"
        local_tar = f"/tmp/{temp_name}.tar.gz"
        remote_tar = f"/tmp/{temp_name}.tar.gz"
        
        try:
            # Créer un tar du répertoire local
            print("📦 Compression du répertoire local...")
            subprocess.call(f"tar czf {local_tar} -C {os.path.dirname(local_path)} {os.path.basename(local_path)}", shell=True)
            
            # Upload vers /tmp sur le remote
            print("📤 Upload vers /tmp...")
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                self._sftp_transfer(client, local_tar, remote_tar, direction="upload")
            finally:
                client.close()
            
            # Créer le répertoire destination
            print("📥 Création du répertoire destination...")
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'mkdir -p {self.dst_path}'"
            else:
                cmd = f"mkdir -p {self.dst_path}"
            self._execute_ssh(self.dst_app, self.dst_env, cmd)
            
            # Extraire le tar sur le remote
            print("📦 Extraction sur le remote...")
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'tar xzf {remote_tar} -C {self.dst_path}'"
            else:
                cmd = f"tar xzf {remote_tar} -C {self.dst_path}"
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
            
        finally:
            # Nettoyage systématique (même en cas d'erreur)
            print("🧹 Nettoyage...")
            self._execute_ssh(self.dst_app, self.dst_env, f"rm -f {remote_tar}")
            if os.path.exists(local_tar):
                os.remove(local_tar)


def main():
    """Point d'entrée pour l'outil copy"""
    tool = CopyTool(sys.argv[1:])
    tool.run()


if __name__ == "__main__":
    main()
