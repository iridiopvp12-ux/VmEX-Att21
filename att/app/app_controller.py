# att/app/app_controller.py

import sys
import FreeSimpleGUI as sg
from pathlib import Path
import json
from typing import List, Optional, Any
import traceback
import logging # <-- 1. IMPORTADO LOGGING
from datetime import datetime # <-- 2. IMPORTAR DATETIME

# --- Bloco de Segurança de Importação ---
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --- 3. IMPORTAR A FUNÇÃO DE LOGGING DO NOVO ARQUIVO ---
try:
    from app.logging_config import setup_logging
except ImportError as e:
    logging.error(f"FALHA CRÍTICA: app_controller não pôde importar 'setup_logging' do logging_config. {e}")
    # Cria uma função dummy para não quebrar
    def setup_logging(*args, **kwargs):
        print(f"ERRO: Função setup_logging não importada. {e}")


# --- Importações da Estrutura da Aplicação (usando 'app.') ---
try:
    from app.config import ConfigLoader
    from app.auth import AuthManager
    from app.ui.login_window import LoginWindow
    from app.ui.menu_window import MenuWindow
    from app.ui.analyzer_window import AnalyzerWindow
    # --- MODIFICAÇÃO: Importação do AnalyzerIndustriasWindow comentada ---
    # from app.ui import analyzer_industrias_window
    from app.ui.admin_window import AdminWindow
    # --- MODIFICAÇÃO: Importação do AutomacaoWindow comentada ---
    # from app.ui import automacao_window
    from app.ui.admin_menu_window import AdminMenuWindow
    from app.ui import sped_filter_window

except ImportError as e:
    sg.popup_error(f"Erro crítico de importação no Controlador:\n{e}\n\n"
                   f"Verifique as dependências e a estrutura de pastas.\n"
                   f"Python Path atual: {sys.path}",
                   title="Erro de Importação")
    print(f"Erro de importação no app_controller: {e}")
    traceback.print_exc()
    sys.exit(1)


class AppController:
    """
    Classe principal que gerencia o ciclo de vida e o fluxo da aplicação.
    """
    def __init__(self, config: ConfigLoader) -> None:
        self.config: ConfigLoader = config
        self.logged_in_user: str | None = None
        self.user_permissions: List[str] = []
        try:
            self.authenticator: AuthManager = AuthManager(
                # --- MODIFICAÇÃO: Corrigido de 'self.config.db_path' para 'self.config.db_usuarios_path' ---
                self.config.db_usuarios_path,
                self.config.admin_user
            )
        except Exception as e:
            sg.popup_error(f"Erro ao inicializar o AuthManager:\n{e}", title="Erro de Autenticação")
            traceback.print_exc()
            sys.exit(1)


    def run(self) -> None:
        """Inicia o loop principal da aplicação (Login -> Menu)."""
        if not self.config or not self.authenticator:
            logging.error("Falha na inicialização do controller (config ou auth). Encerrando.")
            sg.popup_error("Falha na inicialização do controller (config ou auth). Encerrando.")
            return
        try:
            while True:
                login_win = LoginWindow(self.config, self.authenticator)
                username, permissions = login_win.run()

                logging.debug(f"DEBUG: Login bem-sucedido. Usuário: '{username}', Permissões carregadas: {permissions}")

                if not username:
                    break # Usuário fechou a janela de login
                    
                # --- 4. RECONFIGURA O LOGGING COM O USUÁRIO ---
                logging.info(f"Usuário '{username}' logado. Reconfigurando logging...")
                setup_logging(self.config.log_directory_path, self.config.log_level, username)
                # logging.current_user = username # Esta linha pode dar erro se 'logging' não tiver 'current_user'
                # --- FIM DA ADIÇÃO ---

                self.logged_in_user = username
                self.user_permissions = permissions

                menu_win = MenuWindow(self.config, self.logged_in_user, self.user_permissions)
                wants_to_logout = menu_win.run(self)

                # --- 5. RECONFIGURA O LOGGING PARA "SYSTEM" NO LOGOUT ---
                logging.info(f"Usuário '{username}' fazendo logout. Resetando logging para 'SYSTEM'.")
                setup_logging(self.config.log_directory_path, self.config.log_level, "SYSTEM")
                # logging.current_user = 'SYSTEM' # Esta linha pode dar erro se 'logging' não tiver 'current_user'
                # --- FIM DA ADIÇÃO ---

                if not wants_to_logout:
                    break # Usuário fechou o menu principal
            
            logging.info("Aplicação encerrada.") # Log de encerramento
            print("Aplicação encerrada.")
            
        except Exception as e:
            logging.critical(f"Erro inesperado no loop principal do AppController:\n{traceback.format_exc()}", exc_info=True)
            print(f"Erro inesperado no loop principal do AppController:")
            traceback.print_exc()
            sg.popup_error(f"Erro inesperado na aplicação:\n{e}", title="Erro Fatal")

    def _launch_tool(self, tool_key: str) -> None:
        """
        Inicia a janela da ferramenta correspondente à key do botão clicado no menu.
        Verifica as permissões antes de abrir a janela.
        """
        logging.info(f"Tentando iniciar ferramenta: {tool_key}") # <- Log mais informativo

        if not self.logged_in_user or not self.config:
            sg.popup_error("Erro de autenticação ou configuração.", title="Erro")
            logging.error("[ERROR] _launch_tool: Usuário não logado ou config ausente.")
            return

        logging.debug(f"[DEBUG] Tentando iniciar ferramenta: {tool_key} com permissões: {self.user_permissions}")

        try:
            if tool_key == '-ANALISADOR-':
                if 'run_analysis' in self.user_permissions:
                    logging.info("[INFO] Abrindo AnalyzerWindow...")
                    analyzer = AnalyzerWindow(self.config, self.logged_in_user, self.user_permissions)
                    analyzer.run()
                    logging.info("[INFO] AnalyzerWindow fechada.")
                else:
                    logging.warning(f"Usuário '{self.logged_in_user}' sem permissão 'run_analysis'.")
                    sg.popup_notify("Você não tem permissão para acessar esta ferramenta.", title="Acesso Negado")

           
            elif tool_key == '-FILTRO_SPED-':
                if 'run_filtro_sped' in self.user_permissions:
                    logging.info("[INFO] Abrindo SpedFilterWindow...")
                    sped_filter = sped_filter_window.SpedFilterWindow(
                        self.config, self.logged_in_user
                    )
                    sped_filter.run()
                    logging.info("[INFO] SpedFilterWindow fechada.")
                else:
                    logging.warning(f"Usuário '{self.logged_in_user}' sem permissão 'run_filtro_sped'.")
                    sg.popup_notify("Você não tem permissão para acessar esta ferramenta.", title="Acesso Negado")

            elif tool_key == '-ADMIN_MENU-':
                if 'manage_users' in self.user_permissions or 'view_logs' in self.user_permissions:
                    logging.info("[INFO] Abrindo AdminMenuWindow...")
                    admin_menu = AdminMenuWindow(self.config, self.logged_in_user)
                    admin_menu.run()
                    logging.info("[INFO] AdminMenuWindow fechada.")
                else:
                    logging.warning(f"Usuário '{self.logged_in_user}' sem permissão 'manage_users' ou 'view_logs'.")
                    sg.popup_notify("Você não tem permissão para acessar o painel admin.", title="Acesso Negado")

            else:
                if tool_key != '-ADMIN_EMPRESAS-': # -ADMIN_EMPRESAS- é tratado no menu_window
                    logging.warning(f"Ferramenta '{tool_key}' não reconhecida pelo AppController.")
                    sg.popup_no_wait(f"Ferramenta '{tool_key}' não reconhecida ou em desenvolvimento.",
                                     title="Aviso", background_color=sg.theme_background_color(), text_color=sg.theme_text_color())

        except Exception as e:
            logging.critical(f"Erro CRÍTICO ao iniciar ou rodar a ferramenta {tool_key}:\n{traceback.format_exc()}", exc_info=True)
            print(f"Erro CRÍTICO ao iniciar ou rodar a ferramenta {tool_key}:")
            traceback.print_exc()
            sg.popup_error(f"Ocorreu um erro CRÍTICO ao tentar abrir ou rodar a ferramenta '{tool_key}':\n\n{e}\n\nConsulte o terminal para mais detalhes.", title="Erro da Ferramenta")