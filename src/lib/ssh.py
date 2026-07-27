#!/usr/bin/env python3
"""Gestion des connexions SSH avec Paramiko"""

import paramiko
import socket
from src.lib.env import env

class SSHExecutor:
    """Gère les connexions SSH et l'exécution de commandes"""
    
    def __init__(self, password):
        self.password = password
        self.timeout = env.get_ssh_timeout()
        self.command_timeout = env.get_ssh_command_timeout()
    
    def connect(self, host, user, port):
        """Établit une connexion SSH"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                username=user,
                port=int(port),
                password=self.password,
                timeout=self.timeout
            )
            return client
        except paramiko.AuthenticationException:
            return {'error': 'Authentification échouée'}
        except paramiko.SSHException as e:
            return {'error': f'Erreur SSH : {str(e)}'}
        except socket.timeout:
            return {'error': f'Timeout après {self.timeout}s'}
        except Exception as e:
            return {'error': f'Erreur : {str(e)}'}
    
    def exec_command(self, client, command):
        """Exécute une commande sur une session SSH"""
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=self.command_timeout)
            return {
                'stdout': stdout.read().decode(),
                'stderr': stderr.read().decode(),
                'code': stdout.channel.recv_exit_status()
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'code': -1
            }
    
    def run_on_env(self, app, env, command, info, target_user=None):
        """Exécute une commande sur un environnement"""
        client = self.connect(info['host'], info['user'], info['port'])
        
        if isinstance(client, dict) and 'error' in client:
            return {
                'app': app,
                'env': env,
                'host': info['host'],
                'user': info['user'],
                'port': info['port'],
                'target_user': target_user,
                'stdout': '',
                'stderr': client['error'],
                'code': -1
            }
        
        result = self.exec_command(client, command)
        client.close()
        
        return {
            'app': app,
            'env': env,
            'host': info['host'],
            'user': info['user'],
            'port': info['port'],
            'target_user': target_user,
            **result
        }
