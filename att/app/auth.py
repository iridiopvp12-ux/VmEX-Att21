# att/app/auth.py (CORRIGIDO - Removido salt externo, bcrypt gera o próprio, tratamento de erro reforçado)

import FreeSimpleGUI as sg
import json
import logging
from pathlib import Path
import bcrypt
from typing import Dict, List, Tuple, Optional, Any
import traceback # Adicionado para logs de erro

# Mantém as permissões como antes
AVAILABLE_PERMISSIONS = {
    'run_analysis': 'Executar Análise Fiscal (Geral)',
    'run_analysis_industrias': 'Executar Análise Fiscal (Indústrias)',
    'run_automation_lhs': 'Executar Automação Linhares',
    'run_filtro_sped': 'Executar Filtro Sped',
    'manage_users': 'Gerenciar Usuários',
    'view_logs': 'Visualizar Logs',
    'admin': 'Administrador Geral (Acesso Total)'
}

class AuthManager:
    """Gerencia o carregamento, validação, adição, edição e permissões de usuários."""

    # --- CORREÇÃO: Removido parâmetro 'salt' ---
    def __init__(self, users_file: Path | str, admin_user: str):
        """Inicializa o gerenciador de autenticação."""
        self.users_file = Path(users_file) if isinstance(users_file, str) else users_file
        self.admin_user = admin_user.lower()
        # self.salt_str não é mais necessário com bcrypt
        self.users: Dict[str, Dict[str, Any]] = self._load_users()

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Carrega usuários do arquivo JSON, garantindo que o admin sempre exista."""
        users_data = {}
        admin_must_have_all_perms = list(AVAILABLE_PERMISSIONS.keys()) # Todas as permissões para o admin

        try:
            if self.users_file.exists() and self.users_file.stat().st_size > 0:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)

                if not isinstance(loaded_data, dict):
                    raise json.JSONDecodeError("Arquivo de usuários não contém um dicionário JSON válido.", self.users_file.name, 0)

                for username, data in loaded_data.items():
                    username_lower = username.lower()
                    if isinstance(data, dict) and "password" in data and "permissions" in data:
                        if isinstance(data["permissions"], list):
                            valid_perms = [p for p in data["permissions"] if p in AVAILABLE_PERMISSIONS]
                            if username_lower == self.admin_user:
                                users_data[username_lower] = {"password": data["password"], "permissions": admin_must_have_all_perms}
                            else:
                                users_data[username_lower] = {"password": data["password"], "permissions": sorted(list(set(valid_perms)))}
                        else:
                            logging.warning(f"Permissões inválidas (não é lista) para '{username_lower}'. Definindo padrão.")
                            default_perms = admin_must_have_all_perms if username_lower == self.admin_user else ['run_analysis']
                            users_data[username_lower] = {"password": data["password"], "permissions": default_perms}
                    elif isinstance(data, str):
                        logging.warning(f"Convertendo usuário '{username_lower}' do formato antigo.")
                        default_perms = admin_must_have_all_perms if username_lower == self.admin_user else ['run_analysis', 'run_automation_lhs']
                        users_data[username_lower] = {"password": data, "permissions": default_perms}
                    else:
                        logging.warning(f"Dados inválidos ignorados para '{username_lower}' no arquivo de usuários.")

            if self.admin_user not in users_data:
                logging.warning(f"Usuário admin '{self.admin_user}' não encontrado ou arquivo vazio. Criando com senha temporária.")
                users_data[self.admin_user] = {"password": "temp_placeholder", "permissions": admin_must_have_all_perms}
            else:
                # Garante que o admin carregado do arquivo TENHA todas as permissões
                users_data[self.admin_user]["permissions"] = admin_must_have_all_perms

        except json.JSONDecodeError as json_err:
            logging.error(f"Erro ao decodificar JSON do arquivo de usuários ({self.users_file}): {json_err}", exc_info=True)
            sg.popup_error(f"Erro ao ler o arquivo de usuários:\n{json_err}\nVerifique o formato JSON em {self.users_file}", title="Erro Crítico de Usuários")
            users_data = {self.admin_user: {"password": "temp_placeholder", "permissions": admin_must_have_all_perms}}
        except (FileNotFoundError, PermissionError, OSError) as io_err:
            logging.error(f"Erro de I/O ao carregar o arquivo de usuários ({self.users_file}): {io_err}", exc_info=True)
            sg.popup_error(f"Erro ao acessar o arquivo de usuários:\n{io_err}\nVerifique as permissões ou se o arquivo existe em {self.users_file.parent}", title="Erro Crítico de Usuários")
            users_data = {self.admin_user: {"password": "temp_placeholder", "permissions": admin_must_have_all_perms}}
        except Exception as e:
             logging.error(f"Erro inesperado ao carregar usuários: {e}", exc_info=True)
             sg.popup_error(f"Erro inesperado ao carregar usuários:\n{e}", title="Erro Crítico de Usuários")
             users_data = {} # Retorna vazio em erro grave

        # Verificação final de segurança:
        if self.admin_user not in users_data:
             logging.error("Fallback crítico: Usuário admin não pôde ser criado ou carregado.")
             users_data[self.admin_user] = {"password": "temp_placeholder", "permissions": admin_must_have_all_perms}
        
        users_data[self.admin_user]["permissions"] = admin_must_have_all_perms
        return users_data

    def _save_users(self) -> None:
        """Salva o dicionário de usuários no arquivo JSON com tratamento de erro robusto (escrita atômica)."""
        if self.admin_user in self.users:
            self.users[self.admin_user]["permissions"] = list(AVAILABLE_PERMISSIONS.keys())
        
        temp_file = self.users_file.with_suffix(self.users_file.suffix + '.tmp') 

        try:
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            # 1. Escreve no arquivo temporário
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=2, ensure_ascii=False)
            
            # 2. Renomeia o temporário para o original (operação atômica)
            temp_file.replace(self.users_file)
            logging.info(f"Banco de dados de usuários salvo em {self.users_file}")
            
        except (IOError, OSError) as io_err:
            logging.error(f"Falha de I/O ao salvar o banco de dados de usuários ({self.users_file}): {io_err}", exc_info=True)
            sg.popup_error(f"Falha ao salvar usuários:\n{io_err}\nVerifique as permissões de escrita ou espaço em disco.", title="Erro ao Salvar")
            if temp_file.exists():
                try: temp_file.unlink()
                except OSError: pass 
        except Exception as e:
            logging.error(f"Erro inesperado ao salvar usuários: {e}", exc_info=True)
            sg.popup_error(f"Erro inesperado ao salvar usuários:\n{e}", title="Erro ao Salvar")
            if temp_file.exists():
                try: temp_file.unlink()
                except OSError: pass

    # --- CORREÇÃO: Usar bcrypt.gensalt() para gerar hash ---
    def _hash_password(self, password: str) -> str:
        """Cria um hash seguro da senha usando bcrypt."""
        try:
            password_bytes = password.encode('utf-8')
            # Gera um novo salt para cada hash e o embute no resultado
            hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
            return hashed_bytes.decode('utf-8')
        except Exception as e:
            logging.error(f"Erro ao gerar hash da senha: {e}", exc_info=True)
            raise ValueError("Erro interno ao processar a senha.") from e
    # --- FIM DA CORREÇÃO ---

    def _check_password(self, password: str, hashed_pw: str) -> bool:
        """Verifica a senha digitada contra o hash salvo."""
        try:
            password_bytes = password.encode('utf-8')
            hashed_pw_bytes = hashed_pw.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_pw_bytes)
        except ValueError as ve: 
            logging.error(f"Hash inválido encontrado no banco de dados durante checkpw: {hashed_pw[:10]}... Erro: {ve}")
            return False
        except Exception as e:
            logging.error(f"Erro inesperado ao verificar senha com bcrypt: {e}", exc_info=True)
            return False

    def get_all_users(self) -> List[str]:
        """Retorna uma lista com todos os nomes de usuário ordenados."""
        return sorted(list(self.users.keys()))

    def get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Retorna os dados (senha e permissões) de um usuário (case-insensitive)."""
        return self.users.get(username.lower())

    def add_user(self, username: str, password: str, permissions: List[str]):
        """Adiciona um novo usuário."""
        username_lower = username.lower()
        if not username or not password:
            raise ValueError("Nome de usuário e senha são obrigatórios.")
        if username_lower in self.users:
            raise ValueError(f"Usuário '{username}' já existe.")

        valid_permissions = [p for p in permissions if p in AVAILABLE_PERMISSIONS]
        if len(valid_permissions) != len(permissions):
             logging.warning("Tentativa de adicionar usuário com permissões inválidas. Apenas permissões válidas foram salvas.")

        hashed_pw = self._hash_password(password) # Usa a função corrigida

        self.users[username_lower] = {
            "password": hashed_pw,
            "permissions": sorted(list(set(valid_permissions)))
        }
        self._save_users()
        logging.info(f"Usuário '{username_lower}' criado com sucesso com permissões: {valid_permissions}")

    def update_user(self, username: str, new_password: Optional[str], permissions: List[str]):
        """Atualiza a senha (se fornecida) e as permissões de um usuário."""
        username_lower = username.lower()
        if username_lower not in self.users:
            raise ValueError("Usuário não encontrado.")

        valid_permissions = [p for p in permissions if p in AVAILABLE_PERMISSIONS]
        if len(valid_permissions) != len(permissions):
             logging.warning(f"Tentativa de atualizar usuário '{username_lower}' com permissões inválidas. Apenas permissões válidas foram salvas.")

        if new_password:
            hashed_pw = self._hash_password(new_password) # Usa a função corrigida
            self.users[username_lower]["password"] = hashed_pw
            logging.info(f"Senha do usuário '{username_lower}' atualizada.")

        if username_lower == self.admin_user:
            self.users[username_lower]["permissions"] = list(AVAILABLE_PERMISSIONS.keys())
        else:
            self.users[username_lower]["permissions"] = sorted(list(set(valid_permissions)))

        self._save_users()
        logging.info(f"Permissões do usuário '{username_lower}' atualizadas para: {self.users[username_lower]['permissions']}")

    def delete_user(self, username: str):
        """Remove um usuário do banco de dados."""
        username_lower = username.lower()
        if username_lower == self.admin_user:
            logging.warning("Tentativa de excluir o usuário administrador principal.")
            raise ValueError("O administrador principal não pode ser excluído.")

        if username_lower in self.users:
            del self.users[username_lower]
            self._save_users()
            logging.info(f"Usuário '{username_lower}' excluído.")
        else:
             raise ValueError("Usuário não encontrado para exclusão.")


    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str], List[str]]:
        """Verifica as credenciais do usuário."""
        self.reload_users() 

        username_lower = username.lower()
        user_data = self.users.get(username_lower)

        # Primeiro login do admin com senha placeholder
        if user_data and username_lower == self.admin_user and user_data.get("password") == "temp_placeholder":
            if password: 
                try:
                    self.update_user(username_lower, password, list(AVAILABLE_PERMISSIONS.keys()))
                    self.reload_users() 
                    user_data = self.users.get(username_lower) 
                    
                    if user_data and self._check_password(password, user_data.get("password", "")):
                        return True, username_lower, user_data.get("permissions", [])
                    else:
                        logging.error("Erro inesperado após definir a senha inicial do admin.")
                        return False, None, []
                except ValueError as ve: 
                     logging.error(f"Erro ao definir a senha inicial do admin: {ve}", exc_info=True)
                     sg.popup_error(f"Erro ao definir a senha inicial do admin:\n{ve}", title="Erro")
                     return False, None, []
                except Exception as e:
                    logging.error(f"Erro inesperado ao definir a senha inicial do admin: {e}", exc_info=True)
                    sg.popup_error(f"Erro inesperado ao definir a senha inicial do admin:\n{e}", title="Erro")
                    return False, None, []
            else:
                sg.popup_error("Primeiro login do Admin. Por favor, defina uma senha.", title="Configuração Inicial")
                return False, None, []

        # Login normal
        if user_data:
            hashed_pw_from_db = user_data.get("password")
            if hashed_pw_from_db and hashed_pw_from_db != "temp_placeholder" and self._check_password(password, hashed_pw_from_db):
                permissions = list(AVAILABLE_PERMISSIONS.keys()) if username_lower == self.admin_user else user_data.get("permissions", [])
                logging.info(f"Usuário '{username_lower}' autenticado com sucesso.")
                return True, username_lower, permissions
            else:
                log_msg = "Senha incorreta."
                if hashed_pw_from_db == "temp_placeholder":
                    log_msg = "Senha placeholder encontrada para usuário não-admin (erro)."
                elif not hashed_pw_from_db:
                    log_msg = "Hash de senha ausente no banco de dados."
                logging.warning(f"Falha na autenticação para o usuário '{username_lower}'. {log_msg}")
        else:
             logging.warning(f"Tentativa de login com usuário inexistente: '{username_lower}'.")

        return False, None, []

    def reload_users(self):
        """Recarrega os usuários do arquivo."""
        logging.info("Recarregando usuários do arquivo...")
        self.users = self._load_users()