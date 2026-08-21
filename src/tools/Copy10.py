#!/usr/bin/env python3
"""Outil de copie de fichiers/répertoires entre local et remote (100% paramiko)"""

import os
import sys
import shutil
import subprocess
from uuid import uuid4
from src.lib.base import BaseTool
from src.lib.ssh import SSHExecutor
from src.lib.env import env


class CopyTool(BaseTool):
    """Copie de fichiers/répertoires entre local et remote"""

    def __init__(self, args):
        super().__init__(args)
        self.recursive = False
        self.target_user = None
        self.mode = None
        self.verbose = False
        self.force = False
        self.preserve = False

    # ------------------------------------------------------------
    # Parsing et affichage
    # ------------------------------------------------------------

    def parse_args(self):
        if len(self.args) < 2:
            self.print_usage()
            sys.exit(1)

        i = 0
        args_clean = []
        while i < len(self.args):
            arg = self.args[i]
            if arg in ("-r", "--recursive"):
                self.recursive = True
                i += 1
            elif arg in ("-u", "--user"):
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
                        print(f"❌ Mode invalide : {self.mode}")
                        sys.exit(1)
                    i += 2
                else:
                    print("❌ L'option --mode nécessite une valeur")
                    sys.exit(1)
            elif arg in ("-p", "--preserve"):
                self.preserve = True
                i += 1
            elif arg in ("-v", "--verbose"):
                self.verbose = True
                i += 1
            elif arg in ("-f", "--force"):
                self.force = True
                i += 1
            elif arg in ("-h", "--help"):
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

        # Détection des types
        self.src_type = self._detect_type(self.source)
        self.dst_type = self._detect_type(self.destination)

        # Extraction des infos remote
        if self.src_type == "remote":
            self.src_app, self.src_env, self.src_path = self._parse_remote(self.source)
            self._check_app_env(self.src_app, self.src_env)
        if self.dst_type == "remote":
            self.dst_app, self.dst_env, self.dst_path = self._parse_remote(self.destination)
            self._check_app_env(self.dst_app, self.dst_env)

        # Vérifications locales
        if self.src_type == "local" and not os.path.exists(self.source):
            print(f"❌ Source locale inexistante : {self.source}")
            sys.exit(1)
        if self.dst_type == "local":
            dst_dir = os.path.dirname(self.destination) or "."
            if dst_dir and not os.path.exists(dst_dir):
                print(f"❌ Répertoire destination inexistant : {dst_dir}")
                sys.exit(1)

    def _detect_type(self, path):
        return "remote" if ":" in path and path.count(":") >= 2 else "local"

    def _parse_remote(self, path):
        parts = path.split(":", 2)
        if len(parts) != 3:
            print(f"❌ Format remote invalide : {path}")
            print("   Format attendu : appli:env:/path")
            sys.exit(1)
        return parts[0], parts[1], parts[2]

    def _check_app_env(self, app, env):
        if not self.config.app_exists(app):
            print(f"❌ Application '{app}' inconnue")
            self.list_apps()
            sys.exit(1)
        if not self.config.env_exists(app, env):
            print(f"❌ Environnement '{env}' inconnu pour '{app}'")
            self.list_envs(app)
            sys.exit(1)

    def print_usage(self):
        print("""
📋 copy - Copie de fichiers/répertoires entre local et remote

USAGE:
    copy <source> <destination> [options]

FORMATS:
    Local   : /path/to/file  ou  ./relative/path
    Remote  : appli:env:/path/to/file

OPTIONS:
    -r, --recursive         Copie récursive (répertoires)
    -u, --user <user>       Utilisateur cible (ex: root, devops)
    --mode <mode>           Permissions finales (ex: 600, 644, 755)
    -v, --verbose           Affiche la progression
    -f, --force             Écrase les fichiers existants
    -h, --help              Affiche cette aide

EXEMPLES:
    copy appli1:prod:/var/log/app.log ./logs/
    copy ./mon_script.sh appli1:prod:/tmp/ -u devops --mode 755
    copy appli1:prod:/etc/config.yml appli2:recette:/etc/config.yml -u root --mode 600
""")

    # ------------------------------------------------------------
    # Exécution principale
    # ------------------------------------------------------------

    def run(self):
        self.parse_args()

        # Demander le mot de passe si nécessaire
        if self.src_type == "remote" or self.dst_type == "remote":
            self.password = self.get_password()

        # Déterminer le flux
        if self.src_type == "remote" and self.dst_type == "local":
            self._copy_remote_to_local()
        elif self.src_type == "local" and self.dst_type == "remote":
            self._copy_local_to_remote()
        elif self.src_type == "remote" and self.dst_type == "remote":
            self._copy_remote_to_remote()
        else:
            print(f"❌ Flux non supporté : {self.src_type} → {self.dst_type}")
            sys.exit(1)

    # ------------------------------------------------------------
    # Utilitaires SSH / SFTP
    # ------------------------------------------------------------

    def _get_remote_info(self, app, env):
        info = self.config.get_connection_info(app, env)
        return info["user"], info["host"], int(info["port"])

    def _get_ssh_client(self, app, env):
        user, host, port = self._get_remote_info(app, env)
        ssh = SSHExecutor(self.password)
        client = ssh.connect(host, user, port)
        if isinstance(client, dict) and "error" in client:
            raise Exception(f"Erreur de connexion à {app}:{env}: {client['error']}")
        return client

    def _exec_remote(self, app, env, command):
        """Exécute une commande sur un remote et retourne (code, stdout, stderr)"""
        client = self._get_ssh_client(app, env)
        try:
            ssh = SSHExecutor(self.password)
            result = ssh.exec_command(client, command)
            return result["code"], result["stdout"], result["stderr"]
        finally:
            client.close()

    def _sftp_transfer(self, client, src, dst, direction="download"):
        """Transfert SFTP avec progression (si verbose)"""
        sftp = client.open_sftp()
        try:
            if direction == "download":
                size = sftp.stat(src).st_size
            else:
                size = os.path.getsize(src)

            def callback(transferred, total):
                if self.verbose and total > 0:
                    pct = (transferred / total) * 100
                    bar = "█" * int(40 * transferred / total) + "░" * (40 - int(40 * transferred / total))
                    print(f"\r📊 {pct:.1f}% [{bar}] {transferred}/{total} octets", end="", flush=True)

            if direction == "download":
                sftp.get(src, dst, callback=callback)
            else:
                sftp.put(src, dst, callback=callback)

            if self.verbose:
                print()
        finally:
            sftp.close()

    # ------------------------------------------------------------
    # Gestion des droits et permissions
    # ------------------------------------------------------------

    def _get_default_group(self, app, env, user):
        cmd = f"dersudo du- root -c 'id -gn {user}'"
        code, out, _ = self._exec_remote(app, env, cmd)
        return out.strip() if code == 0 else user

    def _set_remote_permissions(self, app, env, path, user, mode):
        group = self._get_default_group(app, env, user)
        if user:
            self._exec_remote(app, env, f"dersudo du- root -c 'chown {user}:{group} {path}'")
        if mode:
            self._exec_remote(app, env, f"dersudo du- root -c 'chmod {mode} {path}'")

    # ------------------------------------------------------------
    # FLUX 1 : Remote → Local
    # ------------------------------------------------------------

    def _copy_remote_to_local(self):
        print(f"📥 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.destination}")
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")

        # Déterminer la destination finale
        if os.path.isdir(self.destination) or self.destination.endswith("/"):
            dest_path = os.path.join(self.destination, os.path.basename(self.src_path))
        else:
            dest_path = self.destination

        # Vérifier si c'est un répertoire
        code, out, _ = self._exec_remote(self.src_app, self.src_env, f"if [ -d {self.src_path} ]; then echo 'dir'; else echo 'file'; fi")
        is_dir = out.strip() == "dir"

        if is_dir and not self.recursive:
            print(f"❌ {self.src_path} est un répertoire. Utilisez -r.")
            sys.exit(1)

        if is_dir:
            self._remote_dir_to_local(dest_path)
        else:
            self._remote_file_to_local(dest_path)

        if self.mode and os.path.exists(dest_path):
            os.chmod(dest_path, int(self.mode, 8))

    def _remote_file_to_local(self, dest_path):
        if self.target_user:
            # Avec sudo : copie vers /tmp puis SFTP
            uid = uuid4().hex
            remote_tmp = f"/tmp/{uid}"
            try:
                # Copier le fichier vers /tmp
                cmd = f"dersudo du- {self.target_user} -c 'cp {self.src_path} {remote_tmp}'"
                code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                if code != 0:
                    raise Exception(f"Erreur copie vers /tmp: {err}")
                # Chmod 644 pour lecture
                self._exec_remote(self.src_app, self.src_env, f"dersudo du- {self.target_user} -c 'chmod 644 {remote_tmp}'")
                # Transfert SFTP
                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    self._sftp_transfer(client, remote_tmp, dest_path, "download")
                finally:
                    client.close()
            finally:
                self._exec_remote(self.src_app, self.src_env, f"rm -f {remote_tmp}")
        else:
            # Sans sudo : SFTP direct
            client = self._get_ssh_client(self.src_app, self.src_env)
            try:
                self._sftp_transfer(client, self.src_path, dest_path, "download")
            finally:
                client.close()

    def _remote_dir_to_local(self, dest_path):
        uid = uuid4().hex
        remote_tar = f"/tmp/{uid}.tar.gz"
        local_tar = f"/tmp/{uid}.tar.gz"

        try:
            # Créer le tar sur le remote
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'tar czf {remote_tar} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}'"
                code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                if code != 0:
                    raise Exception(f"Erreur tar: {err}")
                self._exec_remote(self.src_app, self.src_env, f"dersudo du- {self.target_user} -c 'chmod 644 {remote_tar}'")
            else:
                cmd = f"tar czf {remote_tar} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
                code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                if code != 0:
                    raise Exception(f"Erreur tar: {err}")

            # Télécharger le tar
            client = self._get_ssh_client(self.src_app, self.src_env)
            try:
                self._sftp_transfer(client, remote_tar, local_tar, "download")
            finally:
                client.close()

            # Extraire localement
            parent = os.path.dirname(dest_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
                subprocess.run(f"tar xzf {local_tar} -C {parent}", shell=True, check=True)
            else:
                subprocess.run(f"tar xzf {local_tar} -C /", shell=True, check=True)

        finally:
            # Nettoyage systématique
            self._exec_remote(self.src_app, self.src_env, f"rm -f {remote_tar}")
            if os.path.exists(local_tar):
                os.remove(local_tar)

    # ------------------------------------------------------------
    # FLUX 2 : Local → Remote
    # ------------------------------------------------------------

    def _copy_local_to_remote(self):
        print(f"📤 Copie de {self.source} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")

        if os.path.isdir(self.source):
            if not self.recursive:
                print(f"❌ {self.source} est un répertoire. Utilisez -r.")
                sys.exit(1)
            self._local_dir_to_remote()
        else:
            self._local_file_to_remote()

    def _local_file_to_remote(self):
        if self.target_user:
            uid = uuid4().hex
            remote_tmp = f"/tmp/{uid}"
            try:
                # Upload vers /tmp
                client = self._get_ssh_client(self.dst_app, self.dst_env)
                try:
                    self._sftp_transfer(client, self.source, remote_tmp, "upload")
                finally:
                    client.close()
                # Créer le répertoire destination
                dst_dir = os.path.dirname(self.dst_path)
                if dst_dir:
                    self._exec_remote(self.dst_app, self.dst_env, f"dersudo du- {self.target_user} -c 'mkdir -p {dst_dir}'")
                # Copier vers la destination
                cmd = f"dersudo du- {self.target_user} -c 'cp {remote_tmp} {self.dst_path}'"
                code, _, err = self._exec_remote(self.dst_app, self.dst_env, cmd)
                if code != 0:
                    raise Exception(f"Erreur copie vers destination: {err}")
                # Appliquer permissions
                self._set_remote_permissions(self.dst_app, self.dst_env, self.dst_path, self.target_user, self.mode)
            finally:
                self._exec_remote(self.dst_app, self.dst_env, f"rm -f {remote_tmp}")
        else:
            # SFTP direct
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                dst_dir = os.path.dirname(self.dst_path)
                if dst_dir:
                    self._exec_remote(self.dst_app, self.dst_env, f"mkdir -p {dst_dir}")
                self._sftp_transfer(client, self.source, self.dst_path, "upload")
            finally:
                client.close()

    def _local_dir_to_remote(self):
        uid = uuid4().hex
        local_tar = f"/tmp/{uid}.tar.gz"
        remote_tar = f"/tmp/{uid}.tar.gz"

        try:
            # Créer le tar local
            src_parent = os.path.dirname(self.source)
            src_base = os.path.basename(self.source)
            if src_parent:
                subprocess.run(f"tar czf {local_tar} -C {src_parent} {src_base}", shell=True, check=True)
            else:
                subprocess.run(f"tar czf {local_tar} -C / {src_base}", shell=True, check=True)

            # Upload du tar
            client = self._get_ssh_client(self.dst_app, self.dst_env)
            try:
                self._sftp_transfer(client, local_tar, remote_tar, "upload")
            finally:
                client.close()

            # Créer le répertoire destination
            if self.target_user:
                self._exec_remote(self.dst_app, self.dst_env, f"dersudo du- {self.target_user} -c 'mkdir -p {self.dst_path}'")
            else:
                self._exec_remote(self.dst_app, self.dst_env, f"mkdir -p {self.dst_path}")

            # Extraire le tar
            if self.target_user:
                cmd = f"dersudo du- {self.target_user} -c 'tar xzf {remote_tar} -C {self.dst_path}'"
            else:
                cmd = f"tar xzf {remote_tar} -C {self.dst_path}"
            code, _, err = self._exec_remote(self.dst_app, self.dst_env, cmd)
            if code != 0:
                raise Exception(f"Erreur extraction: {err}")

            # Appliquer permissions récursivement
            if self.target_user or self.mode:
                if self.target_user:
                    group = self._get_default_group(self.dst_app, self.dst_env, self.target_user)
                    self._exec_remote(self.dst_app, self.dst_env, f"dersudo du- root -c 'chown -R {self.target_user}:{group} {self.dst_path}'")
                if self.mode:
                    self._exec_remote(self.dst_app, self.dst_env, f"dersudo du- root -c 'chmod -R {self.mode} {self.dst_path}'")

        finally:
            # Nettoyage
            self._exec_remote(self.dst_app, self.dst_env, f"rm -f {remote_tar}")
            if os.path.exists(local_tar):
                os.remove(local_tar)

    # ------------------------------------------------------------
    # FLUX 3 : Remote → Remote (via local)
    # ------------------------------------------------------------

    def _copy_remote_to_remote(self):
        print(f"📤 Copie de {self.src_app}:{self.src_env}:{self.src_path} → {self.dst_app}:{self.dst_env}:{self.dst_path}")
        if self.target_user:
            print(f"   👤 En tant que : {self.target_user}")
        if self.mode:
            print(f"   🔒 Mode : {self.mode}")

        # Vérifier si la source est un répertoire
        code, out, _ = self._exec_remote(self.src_app, self.src_env, f"if [ -d {self.src_path} ]; then echo 'dir'; else echo 'file'; fi")
        is_dir = out.strip() == "dir"
        if is_dir and not self.recursive:
            print(f"❌ {self.src_path} est un répertoire. Utilisez -r.")
            sys.exit(1)

        uid = uuid4().hex
        local_temp = f"/tmp/{uid}"
        local_tar = f"/tmp/{uid}.tar.gz"
        remote_temp_src = None

        try:
            # --------------------------------------------------------
            # Étape 1 : Remote1 → Local
            # --------------------------------------------------------
            print("📥 Étape 1/2: Téléchargement depuis la source...")

            if is_dir:
                # Créer un tar sur le remote source
                remote_temp_src = f"/tmp/{uid}.tar.gz"
                if self.target_user:
                    cmd = f"dersudo du- {self.target_user} -c 'tar czf {remote_temp_src} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}'"
                    code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                    if code != 0:
                        raise Exception(f"Erreur tar source: {err}")
                    self._exec_remote(self.src_app, self.src_env, f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp_src}'")
                else:
                    cmd = f"tar czf {remote_temp_src} -C {os.path.dirname(self.src_path)} {os.path.basename(self.src_path)}"
                    code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                    if code != 0:
                        raise Exception(f"Erreur tar source: {err}")

                # Télécharger le tar
                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    self._sftp_transfer(client, remote_temp_src, local_tar, "download")
                finally:
                    client.close()

                # Extraire localement
                os.makedirs(os.path.dirname(local_temp), exist_ok=True)
                subprocess.run(f"tar xzf {local_tar} -C {os.path.dirname(local_temp)}", shell=True, check=True)
                # Supprimer le tar local
                os.remove(local_tar)

            else:
                # Fichier
                if self.target_user:
                    remote_temp_src = f"/tmp/{uid}"
                    cmd = f"dersudo du- {self.target_user} -c 'cp {self.src_path} {remote_temp_src}'"
                    code, _, err = self._exec_remote(self.src_app, self.src_env, cmd)
                    if code != 0:
                        raise Exception(f"Erreur copie source vers /tmp: {err}")
                    self._exec_remote(self.src_app, self.src_env, f"dersudo du- {self.target_user} -c 'chmod 644 {remote_temp_src}'")
                else:
                    remote_temp_src = self.src_path  # transfert direct

                client = self._get_ssh_client(self.src_app, self.src_env)
                try:
                    self._sftp_transfer(client, remote_temp_src, local_temp, "download")
                finally:
                    client.close()

            # Nettoyer le remote_temp_src s'il est différent de self.src_path
            if remote_temp_src and remote_temp_src != self.src_path:
                self._exec_remote(self.src_app, self.src_env, f"rm -f {remote_temp_src}")
                remote_temp_src = None

            print(f"✅ Téléchargement terminé : {local_temp}")

            # --------------------------------------------------------
            # Étape 2 : Local → Remote2
            # --------------------------------------------------------
            print("📤 Étape 2/2: Envoi vers la destination...")

            # Déterminer si local_temp est un répertoire
            is_local_dir = os.path.isdir(local_temp)

            if is_local_dir:
                # Utiliser la fonction existante pour copier un répertoire local vers remote
                # On sauvegarde self.source pour ne pas perturber
                original_source = self.source
                self.source = local_temp
                try:
                    self._local_dir_to_remote()
                finally:
                    self.source = original_source
            else:
                # Fichier
                original_source = self.source
                self.source = local_temp
                try:
                    if self.target_user:
                        self._local_file_to_remote()
                    else:
                        self._local_file_to_remote()
                finally:
                    self.source = original_source

            print(f"✅ Copie réussie : {self.dst_app}:{self.dst_env}:{self.dst_path}")

        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            sys.exit(1)
        finally:
            # Nettoyage local
            print("🧹 Nettoyage...")
            if os.path.exists(local_temp):
                if os.path.isdir(local_temp):
                    shutil.rmtree(local_temp)
                else:
                    os.remove(local_temp)
            if os.path.exists(local_tar):
                os.remove(local_tar)
            # Nettoyage remote source si encore présent
            if remote_temp_src:
                self._exec_remote(self.src_app, self.src_env, f"rm -f {remote_temp_src}")


def main():
    tool = CopyTool(sys.argv[1:])
    tool.run()


if __name__ == "__main__":
    main()
