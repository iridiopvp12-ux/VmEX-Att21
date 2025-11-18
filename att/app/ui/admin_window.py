# att/app/ui/admin_window.py (CORREÇÃO 4)

import FreeSimpleGUI as sg
# --- Importar Tipos Essenciais ---
from typing import Dict, Any, List, Optional, Type, TYPE_CHECKING
import traceback
import sys
from pathlib import Path

# --- [INÍCIO DA CORREÇÃO] ---

# Importa permissões (seguro, é um dicionário)
try:
    from app.auth import AVAILABLE_PERMISSIONS
except ImportError:
    AVAILABLE_PERMISSIONS = {}

# Bloco de importações APENAS para o type checker (Pylance)
if TYPE_CHECKING:
    from app.config import ConfigLoader
    from app.auth import AuthManager
    
    ConfigLoader_Type = ConfigLoader
    AuthManager_Type = AuthManager
    
    ActualConfigLoader = ConfigLoader 
    ActualAuthManager = AuthManager

# Bloco de importações para tempo de execução (runtime)
else:
    try:
        from app.config import ConfigLoader as ActualConfigLoader
        from app.auth import AuthManager as ActualAuthManager
        ConfigLoader_Type = ActualConfigLoader
        AuthManager_Type = ActualAuthManager
    except ImportError as main_import_error:
        print(f"ERRO CRÍTICO de importação em admin_window: {main_import_error}. Verifique sys.path.")
        traceback.print_exc()
        
        ConfigLoader_Type = Any
        AuthManager_Type = Any
        ActualConfigLoader = None
        ActualAuthManager = None
        
# --- [FIM DA CORREÇÃO] ---


class AdminWindow:
    """Interface para gerenciar usuários, utilizando o AuthManager."""

    def __init__(self, config: Optional[ConfigLoader_Type]):
        # O config ainda é necessário para temas, fontes, etc.
        self.config = config 
        self.auth_manager: Optional[AuthManager_Type] = None
        self.window: sg.Window | None = None
        self.selected_user: str | None = None
        self.admin_user_setting: str | None = None

        # Pylance agora reconhece 'ActualAuthManager'
        if self.config and ActualAuthManager is not None:
            try:
                # [CORREÇÃO]
                # O ConfigLoader real (passado do menu) não fornece as
                # chaves de segurança. Vamos defini-las estaticamente
                # com base no bloco MockConfig (no final deste arquivo).

                # 1. Define o caminho do DB estaticamente
                # (baseado em: att/app/ui/admin_window.py -> att/)
                db_path = Path(__file__).parent.parent.parent / 'database_usuarios.json'
                
                # 2. Define o usuário admin padrão estaticamente
                admin_user = 'admin' 
                
                # Salva o nome do admin para usar em outras funções
                self.admin_user_setting = admin_user 

                # Inicializa o AuthManager com os valores estáticos
                self.auth_manager = ActualAuthManager(db_path, admin_user)

            except Exception as e:
                # Captura qualquer outro erro (ex: AuthManager falha ao carregar)
                sg.popup_error(f"Erro crítico ao inicializar AuthManager na AdminWindow:\n{e}", title="Erro Auth")
                # auth_manager permanece None
                
        elif not self.config:
             sg.popup_error("Erro: Configuração não fornecida para AdminWindow.", title="Erro Config")
        elif ActualAuthManager is None:
            sg.popup_error("Erro: Módulo AuthManager não carregado.", title="Erro Import")

    #
    # O RESTANTE DO CÓDIGO (NÃO PRECISA MUDAR NADA ABAIXO)
    #
    def _save_user_changes(self, values: Dict[str, Any]) -> None:
        """Coleta dados da UI e usa o AuthManager para salvar as alterações."""
        if not self.auth_manager or not hasattr(self.auth_manager, 'update_user') or not hasattr(self.auth_manager, 'add_user'):
             sg.popup_error("AuthManager não inicializado corretamente.", title="Erro")
             return

        username = self.selected_user if self.selected_user else values['-NEW_USER-'].strip()
        password = values['-NEW_PASS-']
        confirm_password = values['-CONFIRM_PASS-']

        if not username:
            sg.popup_error("Nome de usuário é obrigatório.", title="Erro")
            return

        permissions = [perm_key for perm_key in AVAILABLE_PERMISSIONS if values.get(f'-PERM_{perm_key}-', False)]

        try:
            if self.selected_user: # Editando
                self.auth_manager.update_user(
                    username=self.selected_user,
                    new_password=password if password else None,
                    permissions=permissions
                )
                sg.popup_ok(f"Usuário '{self.selected_user}' atualizado.", title="Sucesso")
                # Atualiza a lista após salvar
                if self.window and hasattr(self.auth_manager, 'get_all_users'):
                    self.window['-USER_LIST-'].update(self.auth_manager.get_all_users())


            else: # Criando
                if not password:
                    sg.popup_error("Senha é obrigatória para novos usuários.", title="Erro")
                    return
                if password != confirm_password:
                    sg.popup_error("As senhas não coincidem.", title="Erro")
                    return

                self.auth_manager.add_user(username, password, permissions)
                sg.popup_ok(f"Usuário '{username}' criado com sucesso.", title="Sucesso")
                self._reset_form_to_add_mode() # Limpa form
                # Atualiza a lista após salvar
                if self.window and hasattr(self.auth_manager, 'get_all_users'):
                    self.window['-USER_LIST-'].update(self.auth_manager.get_all_users())


        except ValueError as e:
            sg.popup_error(str(e), title="Erro")
        except Exception as e:
             sg.popup_error(f"Erro inesperado ao salvar: {e}", title="Erro")
             print(traceback.format_exc())

    def _delete_selected_user(self) -> None:
        """Exclui o usuário atualmente selecionado."""
        if not self.auth_manager or not hasattr(self.auth_manager, 'delete_user'):
             sg.popup_error("AuthManager não inicializado corretamente.", title="Erro")
             return
        if not self.selected_user:
            sg.popup_error("Nenhum usuário selecionado.", title="Erro")
            return

        # Impede a exclusão do admin principal
        # Usa self.admin_user_setting (que agora vem do valor estático 'admin')
        if self.config and self.admin_user_setting and self.selected_user.lower() == self.admin_user_setting.lower():
            sg.popup_error("O administrador principal não pode ser excluído.", title="Ação InvCálida")
            return

        if sg.popup_yes_no(f"Tem certeza que deseja excluir o usuário '{self.selected_user}'?\nEsta ação não pode ser desfeita.", title="Confirmar Exclusão") == 'Yes':
            try:
                self.auth_manager.delete_user(self.selected_user)
                sg.popup_ok(f"Usuário '{self.selected_user}' excluído.", title="Sucesso")
                self._reset_form_to_add_mode() # Limpa form
                # Atualiza a lista após excluir
                if self.window and hasattr(self.auth_manager, 'get_all_users'):
                    self.window['-USER_LIST-'].update(self.auth_manager.get_all_users())
            except ValueError as e:
                sg.popup_error(str(e), title="Erro")
            except Exception as e:
                sg.popup_error(f"Erro inesperado ao excluir: {e}", title="Erro")
                print(traceback.format_exc())

    def _update_form_for_edit(self, username: str) -> None:
        """Preenche o formulário com os dados do usuário selecionado."""
        if not self.window or not self.auth_manager or not hasattr(self.auth_manager, 'get_user_data'):
             print("[WARN] _update_form_for_edit: Janela ou AuthManager não inicializado.")
             return

        self.selected_user = username
        user_data = self.auth_manager.get_user_data(username)
        if not user_data:
            sg.popup_error(f"Não foi possível carregar dados para '{username}'.", title="Erro")
            return

        self.window['-NEW_USER-'].update(value=username, disabled=True)
        self.window['-NEW_PASS-'].update(value='')
        self.window['-CONFIRM_PASS-'].update(value='')
        self.window['-SAVE_BUTTON-'].update(text="Salvar Alterações")

        # Usa self.admin_user_setting
        is_main_admin = (self.config and self.admin_user_setting and username.lower() == self.admin_user_setting.lower())
        self.window['-DELETE-'].update(disabled=is_main_admin)
        self.window['-NEW_USER_BTN-'].update(visible=True) # Botão para voltar a adicionar

        user_permissions = user_data.get('permissions', [])
        available_perms_keys = AVAILABLE_PERMISSIONS.keys() if AVAILABLE_PERMISSIONS else []
        for perm_key in available_perms_keys:
            perm_checkbox = self.window.find_element(f'-PERM_{perm_key}-', silent_on_error=True)
            if perm_checkbox:
                perm_checkbox.update(value=(perm_key in user_permissions))
                is_admin_perm_and_main_admin = (is_main_admin and perm_key == 'admin')
                is_manage_perm_and_main_admin = (is_main_admin and perm_key == 'manage_users')
                perm_checkbox.update(disabled=is_admin_perm_and_main_admin or is_manage_perm_and_main_admin)


    def _reset_form_to_add_mode(self) -> None:
        """Limpa o formulário para o modo de adição."""
        if not self.window: return

        self.selected_user = None
        self.window['-NEW_USER-'].update(value='', disabled=False)
        self.window['-NEW_PASS-'].update(value='')
        self.window['-CONFIRM_PASS-'].update(value='')
        self.window['-SAVE_BUTTON-'].update(text="Criar Novo Usuário")
        self.window['-DELETE-'].update(disabled=True)
        self.window['-NEW_USER_BTN-'].update(visible=False) # Esconde o botão
        available_perms_keys = AVAILABLE_PERMISSIONS.keys() if AVAILABLE_PERMISSIONS else []
        for perm_key in available_perms_keys:
             perm_checkbox = self.window.find_element(f'-PERM_{perm_key}-', silent_on_error=True)
             if perm_checkbox:
                 perm_checkbox.update(value=False, disabled=False)

        new_user_element = self.window.find_element('-NEW_USER-', silent_on_error=True)
        if new_user_element:
            new_user_element.set_focus()


    def _build_layout(self) -> List[List[sg.Element]]:
        """Cria o layout da janela de admin."""
        if ActualAuthManager is None or ActualConfigLoader is None or not self.config:
            return [[sg.Text("Erro Crítico: Falha ao carregar componentes (Auth/Config).", text_color='red')], [sg.Button("Fechar")]]

        # Usa o 'config' para temas/fontes, o que sabemos que funciona
        theme = self.config.theme_definition if hasattr(self.config, 'theme_definition') else {}
        btn_colors = self.config.btn_colors if hasattr(self.config, 'btn_colors') else {}
        font_family = self.config.font_family if hasattr(self.config, 'font_family') else sg.DEFAULT_FONT[0]
        font = (font_family, 10)
        bg_color = theme.get('BACKGROUND', '#1E1E1E')

        user_list_values = self.auth_manager.get_all_users() if self.auth_manager else ["Erro ao carregar"]
        user_list_col = [
            [sg.Text("Usuários", font=(font_family, 12, 'bold'), background_color=bg_color)],
            [sg.Listbox(values=user_list_values, size=(25, 15), 
                        key='-USER_LIST-',
                        enable_events=True, font=font, expand_y=True)],
            [sg.Button("Novo Usuário", key='-NEW_USER_BTN-', font=font, visible=False)]
        ]

        perm_layout = []
        available_perms = AVAILABLE_PERMISSIONS if AVAILABLE_PERMISSIONS else {}
        for key, description in sorted(available_perms.items(), key=lambda item: item[1]):
            perm_layout.append([sg.Checkbox(description, key=f'-PERM_{key}-', font=font, background_color=bg_color)])

        edit_details_col = [
            [sg.Text("Detalhes do Usuário", font=(font_family, 12, 'bold'), background_color=bg_color)],
            [sg.Text("Usuário:", size=(12, 1), font=font, background_color=bg_color), sg.Input(key='-NEW_USER-', font=font, expand_x=True)],
            [sg.Text("Nova Senha:", size=(12, 1), font=font, background_color=bg_color), sg.Input(key='-NEW_PASS-', font=font, password_char='*', expand_x=True)],
            [sg.Text("Confirmar Senha:", size=(12, 1), font=font, background_color=bg_color), sg.Input(key='-CONFIRM_PASS-', font=font, password_char='*', expand_x=True)],
            [sg.HorizontalSeparator(pad=((0,0),(10,10)))],
            [sg.Text("Permissões:", font=(font_family, 11, 'bold'), background_color=bg_color)],
            [sg.Column(perm_layout, background_color=bg_color, scrollable=True, vertical_scroll_only=True, size=(None, 150), expand_x=True, expand_y=True)],
            [sg.HorizontalSeparator(pad=((0,0),(10,10)))],
            [
                sg.Button("Salvar Alterações", key='-SAVE_BUTTON-', font=font, button_color=btn_colors.get('add',{}).get('normal','#28A745'), mouseover_colors=btn_colors.get('add',{}).get('hover','#2ECC71')),
                sg.Button("Excluir", key='-DELETE-', font=font, button_color=btn_colors.get('delete',{}).get('normal','#DC3545'), mouseover_colors=btn_colors.get('delete',{}).get('hover','#E74C3C'), disabled=True)
            ]
        ]

        return [
            [sg.Column(user_list_col, background_color=bg_color, expand_y=True),
             sg.VerticalSeparator(),
             sg.Column(edit_details_col, background_color=bg_color, expand_y=True)],
            [sg.HorizontalSeparator()],
            [sg.Push(background_color=bg_color), sg.Button('Fechar', key='-EXIT-', font=(font_family, 11), button_color=btn_colors.get('exit',{}).get('normal','#6C757D'), mouseover_colors=btn_colors.get('exit',{}).get('hover','#868E96'))]
        ]

    def run(self) -> None:
        """Exibe a janela e gerencia seu loop de eventos."""
        if not self.config or ActualAuthManager is None:
            if ActualAuthManager is None and self.config:
                 sg.popup_error("Erro: Módulo AuthManager não carregado. Janela Admin não pode iniciar.", title="Erro Import")
            elif not self.config:
                 sg.popup_error("Erro: Configuração não fornecida. Janela Admin não pode iniciar.", title="Erro Config")
            print("ERRO: Não foi possível iniciar AdminWindow: AuthManager ou Configuração ausente.")
            return

        layout = self._build_layout()
        window_size = (750, 500) if len(layout) > 2 else (400, 100)
        
        bg_color = '#1E1E1E'
        if hasattr(self.config, 'theme_definition') and self.config.theme_definition:
            bg_color = self.config.theme_definition.get('BACKGROUND', '#1E1E1E')

        if not self.auth_manager:
             # O popup de erro já foi mostrado no __init__
             print("[ERRO] AuthManager não foi inicializado. Encerrando 'run'.")
             return

        app_icon = self.config.app_icon_path if hasattr(self.config, 'app_icon_path') else None
        self.window = sg.Window("Admin - Gerenciar Usuários", layout, finalize=True, modal=True,
                                background_color=bg_color,
                                icon=app_icon, size=window_size, resizable=True)

        if len(layout) <= 2: 
            self.window.read(close=True)
            return

        try:
            self.window['-USER_LIST-'].update(self.auth_manager.get_all_users())
            self._reset_form_to_add_mode()
        except Exception as load_err:
             sg.popup_error(f"Erro ao carregar usuÁrios iniciais:\n{load_err}", title="Erro")
             if self.window: self.window.close()
             return

        while True:
            try:
                event, values = self.window.read()

                if event in (sg.WIN_CLOSED, '-EXIT-'):
                    break
                elif event == '-USER_LIST-':
                    if values['-USER_LIST-']:
                        self._update_form_for_edit(values['-USER_LIST-'][0])
                elif event == '-NEW_USER_BTN-':
                    self._reset_form_to_add_mode()
                elif event == '-SAVE_BUTTON-':
                    self._save_user_changes(values)
                elif event == '-DELETE-':
                    self._delete_selected_user()
            except Exception as loop_err:
                 sg.popup_error(f"Erro inesperado no loop da janela Admin:\n{loop_err}", title="Erro")
                 print(traceback.format_exc())

        if self.window:
             self.window.close()
        self.window = None

# Bloco para teste (opcional)
if __name__ == '__main__':
    
    # O MockConfig simula o ConfigLoader real (só com temas/fontes)
    class MockConfig:
        font_family = 'Segoe UI'
        theme_definition = {'BACKGROUND': '#1E1E1E', 'TEXT': '#E0E0E0', 'INPUT': '#2C2C2C'}
        btn_colors = {
            'main': {'normal': '#007ACC'}, 'exit': {'normal': '#6C757D'},
            'add': {'normal': '#28A745', 'hover': '#2ECC71'},
            'delete': {'normal': '#DC3545', 'hover': '#E74C3C'}
        }
        app_icon_path = None
        # Note que 'database_usuarios' e 'admin_default_user' NÃO estão aqui,
        # assim como no ConfigLoader real.

    project_root_test = Path(__file__).resolve().parent.parent.parent
    if str(project_root_test) not in sys.path:
        sys.path.insert(0, str(project_root_test))

    AuthManagerForTest = None

    try:
        from app.auth import AuthManager as AuthManager_Test, AVAILABLE_PERMISSIONS
        AuthManagerForTest = AuthManager_Test
    except ImportError:
        print("Erro: Não foi possível importar AuthManager para teste.")
        AVAILABLE_PERMISSIONS = {}

    if AuthManagerForTest:
        mock_config = MockConfig()
        try:
             # O __init__ agora usa o mock_config (para temas)
             # mas define os valores de segurança internamente.
             admin_win = AdminWindow(mock_config) 
             if admin_win.auth_manager:
                 admin_win.run()
        except Exception as test_run_err:
            sg.popup_error(f"Erro ao rodar AdminWindow em modo de teste:\n{test_run_err}")
            print(traceback.format_exc())
    else:
        sg.popup_error("Falha ao carregar AuthManager para teste.")