# app/ui/login_window.py (MODIFICADO)

import FreeSimpleGUI as sg
import os
from typing import Optional, Tuple, List

from app.config import ConfigLoader
from app.auth import AuthManager

class LoginWindow:
    """Encapsula a criação e o loop de eventos da janela de Login."""
    
    def __init__(self, config: ConfigLoader, auth_manager: AuthManager):
        """
        Inicializa a janela de login.
        """
        self.config = config
        self.auth_manager = auth_manager # Recebe o AuthManager
        self.window: sg.Window | None = None
    
    def _build_layout(self) -> list:
        """
        Cria o layout da janela de login.
        """
        font_family = self.config.font_family
        BG_COLOR = self.config.theme_definition.get('BACKGROUND', '#0F172A')
        TEXT_COLOR = self.config.theme_definition.get('TEXT', '#FAFAFA')
        
        layout = [
            [sg.VPush(background_color=BG_COLOR)],
            [sg.Text('VM CONTADORES', font=(font_family, 25, 'bold'), justification='center', expand_x=True, pad=((0,0),(0,5)), background_color=BG_COLOR, text_color=TEXT_COLOR)],
            [sg.Text('Acesso ao Sistema', font=(font_family, 12), justification='center', expand_x=True, pad=((0,0),(0,20)), background_color=BG_COLOR, text_color=TEXT_COLOR)],
            [sg.Text('Usuário:', size=(8, 1), font=(font_family, 11), background_color=BG_COLOR, text_color=TEXT_COLOR), 
             sg.Input(key='-USUARIO-', font=(font_family, 11), size=(25,1))],
            [sg.Text('Senha:', size=(8, 1), font=(font_family, 11), background_color=BG_COLOR, text_color=TEXT_COLOR), 
             sg.Input(key='-SENHA-', font=(font_family, 11), size=(25,1), password_char='*')],
            [sg.VPush(background_color=BG_COLOR)],
            [sg.Column([
                [sg.Button('Login', key='-LOGIN-', font=(font_family, 12, 'bold'), size=(15, 2), 
                           button_color=self.config.btn_colors['main']['normal'], 
                           mouseover_colors=self.config.btn_colors['main']['hover'], 
                           bind_return_key=True),
                 sg.Button('Sair', key='-SAIR-', font=(font_family, 12), size=(10, 2),
                           button_color=self.config.btn_colors['exit']['normal'],
                           mouseover_colors=self.config.btn_colors['exit']['hover'])]
            ], justification='center', background_color=BG_COLOR)],
            [sg.VPush(background_color=BG_COLOR)],
        ]
        return layout   

    def run(self) -> Tuple[Optional[str], List[str]]:
        """
        Exibe a janela de login e gerencia seu loop de eventos.
        Retorna (username, permissions) em caso de sucesso, ou (None, []) em caso de falha/saída.
        """
        layout = self._build_layout()
        self.window = sg.Window('Acesso ao Sistema', layout, size=(450, 300), 
                                element_justification='center', 
                                finalize=True, 
                                background_color=self.config.theme_definition.get('BACKGROUND', '#0F172A'),
                                icon=self.config.app_icon_path)
     
        usuario_logado: Optional[str] = None
        permissoes_usuario: List[str] = []

        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED or event == '-SAIR-':
                break
                
            if event == '-LOGIN-':
                usuario_digitado = values['-USUARIO-']
                senha_digitada = values['-SENHA-']
                
                if not usuario_digitado:
                    sg.popup_error("Nome de usuário é obrigatório.")
                    continue
                
                
                is_first_setup = (
                    usuario_digitado.lower() == self.config.admin_user and
                    self.auth_manager.get_user_data(usuario_digitado)["password"] == "temp_placeholder"
                )
            
                
                if is_first_setup and not senha_digitada:
                    sg.popup_error("Primeiro login do Admin. Por favor, defina uma senha.", title="Configuração Inicial")
                    continue

                success, username, permissions = self.auth_manager.authenticate(usuario_digitado, senha_digitada)
                
                if success:
                    usuario_logado = username
                    permissoes_usuario = permissions
                    if is_first_setup:
                        sg.popup_ok(f"Bem-vindo, {username}!\nSenha de administrador definida com sucesso.", title="Configuração Inicial")
                    break
                else:
                    sg.popup_error('Usuário ou Senha inválidos.')

        self.window.close()
        return usuario_logado, permissoes_usuario
  
  