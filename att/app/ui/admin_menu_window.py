import FreeSimpleGUI as sg
import os
import subprocess
import platform
from pathlib import Path
from typing import List, Any
import sys
import typing # <-- IMPORT ADICIONADO

from app.config import ConfigLoader
# AdminWindow é importado corretamente pois é usado na funcionalidade
from app.ui.admin_window import AdminWindow

# --- BLOCO MOVIDO PARA TYPE CHECKING ---
# Para que o AppController possa ser tipado (só durante type checking)
if typing.TYPE_CHECKING:
    try:
        from app.app_controller import AppController
    except ImportError:
        AppController = Any # Fallback para o type checker
# --- FIM DA MODIFICAÇÃO ---

class AdminMenuWindow:
    """Janela que serve como hub para as funções administrativas."""

    def __init__(self, config: ConfigLoader, username: str):
        self.config = config; self.username = username
        self.window: sg.Window | None = None
        self.font_family = self.config.font_family

    def _get_log_folder_path(self) -> Path:
        """Retorna o caminho ESPECÍFICO para a pasta de logs na rede."""
        # Define o caminho de rede desejado diretamente
        network_path_str = r"\\srv-dc02\Documentos\contratos e alterações\Fiscal\Arquivos fiscais\Logs Automatizador"
        return Path(network_path_str)

    def _open_log_folder(self) -> None:
        """Abre a pasta de logs no explorador de arquivos com mais debug."""
        try:
            log_folder = self._get_log_folder_path()
            print(f"[DEBUG] Tentando abrir a pasta de logs em: {log_folder}") # Debug

            # Tenta resolver o caminho, mas usa o original se falhar (útil para UNC)
            try:
                log_folder_resolved = log_folder.resolve(strict=False) # strict=False evita erro se não existir
                print(f"[DEBUG] Caminho absoluto resolvido (ou tentado): {log_folder_resolved}")
            except Exception as resolve_err:
                 print(f"[WARN] Falha ao resolver caminho {log_folder}: {resolve_err}. Usando caminho original.")
                 log_folder_resolved = log_folder # Usa o caminho UNC original

            # Verifica se o caminho (resolvido ou original) existe como diretório
            if not log_folder_resolved.is_dir():
                 # Verifica se o PAI existe, talvez a pasta final ainda não foi criada
                 if log_folder_resolved.parent.is_dir():
                     print(f"[DEBUG] Pasta final não existe ({log_folder_resolved}), mas o diretório pai sim. Tentando abrir o pai...")
                     log_folder_to_open = log_folder_resolved.parent # Tenta abrir o pai
                 else:
                     print(f"[DEBUG] Pasta ou caminho pai não encontrado ou não é um diretório: {log_folder_resolved}")
                     sg.popup_ok(f"A pasta de logs ou seu caminho pai não foi encontrado.\nVerifique o acesso à rede e se o caminho está correto.\nCaminho esperado: {log_folder_resolved}", title="Aviso")
                     return
            else:
                 log_folder_to_open = log_folder_resolved # Abre a pasta final se ela existe

            print(f"[DEBUG] Tentando abrir com comando do sistema operacional: {log_folder_to_open}")
            system = platform.system()
            try:
                if system == "Windows":
                    print("[DEBUG] Usando os.startfile para Windows...")
                    os.startfile(log_folder_to_open) # Funciona bem com UNC paths no Windows
                elif system == "Darwin": # macOS
                    print("[DEBUG] Usando subprocess.run 'open' para macOS...")
                    subprocess.run(['open', str(log_folder_to_open)], check=True)
                else: # Linux and other Unix-like
                    print("[DEBUG] Usando subprocess.run 'xdg-open' para Linux/Unix...")
                    subprocess.run(['xdg-open', str(log_folder_to_open)], check=True)
                print("[DEBUG] Comando para abrir pasta executado.")
            except FileNotFoundError as fnf_error:
                print(f"[ERROR] Comando '{fnf_error.filename}' não encontrado no sistema.")
                sg.popup_error(f"Não foi possível encontrar o comando para abrir a pasta no seu sistema ('{fnf_error.filename}').\n"
                               f"Por favor, navegue manualmente para:\n{log_folder_to_open}", title="Erro")
            except subprocess.CalledProcessError as cpe_error:
                print(f"[ERROR] Erro ao executar comando para abrir pasta: {cpe_error}")
                sg.popup_error(f"Ocorreu um erro ao tentar abrir a pasta de logs automaticamente.\n"
                               f"Pode ser um problema de permissão ou caminho de rede inválido.\n"
                               f"Erro: {cpe_error}\n"
                               f"Por favor, navegue manualmente para:\n{log_folder_to_open}", title="Erro")
            except Exception as open_error: # Captura outros erros
                print(f"[ERROR] Erro inesperado ao tentar abrir a pasta: {open_error}")
                sg.popup_error(f"Ocorreu um erro inesperado ao tentar abrir a pasta:\n{open_error}\n"
                               f"Verifique as permissões e o acesso à rede.\n"
                               f"Por favor, navegue manualmente para:\n{log_folder_to_open}", title="Erro")

        except Exception as path_error:
            print(f"[ERROR] Erro ao criar ou processar o caminho da pasta de logs: {path_error}")
            sg.popup_error(f"Não foi possível processar o caminho da pasta de logs.\nVerifique se o caminho de rede está formatado corretamente.\nErro: {path_error}", title="Erro")


    def _build_layout(self) -> List[List[sg.Element]]:
        """Cria o layout do painel admin."""
        btn_exit = self.config.btn_colors.get('exit', {})
        btn_admin_action = self.config.btn_colors.get('admin', {})
        BG_COLOR = self.config.theme_definition.get('BACKGROUND', '#0F172A')
        TEXT_COLOR = self.config.theme_definition.get('TEXT', '#FAFAFA')

        layout = [
            [sg.Text('Painel Administrativo', font=(self.font_family, 20, 'bold'), justification='center',
                     expand_x=True, pad=((0,0),(15,10)), background_color=BG_COLOR, text_color=TEXT_COLOR)],
            [sg.HorizontalSeparator()],
            [sg.VPush(background_color=BG_COLOR)], # Adicionado VPush para centralizar verticalmente
            [sg.Button('Gerenciar Usuários', key='-MANAGE_USERS-', font=(self.font_family, 12), size=(25, 2),
                       button_color=btn_admin_action.get('normal', '#17A2B8'),
                       mouseover_colors=btn_admin_action.get('hover', '#1BC5E0'),
                       tooltip='Adicionar/editar/remover usuários do sistema')],
            [sg.Button('Abrir Pasta de Logs', key='-OPEN_LOGS-', font=(self.font_family, 12), size=(25, 2),
                       button_color=btn_admin_action.get('normal', '#17A2B8'),
                       mouseover_colors=btn_admin_action.get('hover', '#1BC5E0'),
                       tooltip=f'Abrir a pasta de logs em: {self._get_log_folder_path()}')],
            [sg.VPush(background_color=BG_COLOR)], # Adicionado VPush para centralizar verticalmente
            [sg.HorizontalSeparator()],
            [sg.Push(background_color=BG_COLOR),
             sg.Button('Voltar', key='-BACK-', font=(self.font_family, 11), size=(15, 1),
                       button_color=btn_exit.get('normal', '#6C757D'),
                       mouseover_colors=btn_exit.get('hover', '#868E96'),
                       tooltip='Voltar para o menu principal')]
        ]
        return layout

    def run(self) -> None:
        """Exibe o painel admin."""
        layout = self._build_layout()
        # Ajuste o tamanho da janela se necessário
        self.window = sg.Window('Massucatti - Painel Admin', layout, size=(450, 350), # Altura talvez menor
                                 finalize=True, modal=True, element_justification='center',
                                 icon=self.config.app_icon_path,
                                 background_color=self.config.theme_definition.get('BACKGROUND', '#0F172A')) # Usa a cor do tema
        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED or event == '-BACK-': break
            if event == '-MANAGE_USERS-':
                # Cria e roda a AdminWindow (gerenciamento de usuários)
                # Esconde esta janela antes de abrir a outra modal
                self.window.hide()
                try:
                    user_admin_win = AdminWindow(self.config); user_admin_win.run()
                finally:
                    # Garante que esta janela reapareça
                    self.window.un_hide()
            if event == '-OPEN_LOGS-':
                self._open_log_folder()
        if self.window:
            self.window.close()
        self.window = None