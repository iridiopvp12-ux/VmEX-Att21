# att/app/ui/menu_window.py

import FreeSimpleGUI as sg
from FreeSimpleGUI import Window, Element, Column, Text, Button
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import sys
import traceback
import typing

from app.config import ConfigLoader
from app.ui import empresa_cadastro_window
from app.fiscal.template_generator import gerar_template_de_regras

if typing.TYPE_CHECKING:
    try:
        from app.app_controller import AppController
    except ImportError:
        AppController = Any

class MenuWindow:
    """Encapsula a criação e o loop de eventos da janela do Menu Principal."""

    def __init__(self, config: ConfigLoader, username: str, permissions: List[str]):
        """Inicializa a janela do menu."""
        self.config = config
        self.username = username
        self.user_permissions = permissions
        self.window: Optional[Window] = None

        self.card_definitions = [
            {
                'key': '-ANALISADOR-', 'title': 'Analisador Fiscal', 'desc': 'Análise fiscal para Comercio',
                'permission': 'run_analysis', 'icon': '📊', 'tooltip': 'Executa análises fiscais detalhadas para empresas comerciais.'
            },
            # --- MODIFICAÇÃO: Bloco do Analisador Indústrias comentado ---
            # {
            #     'key': '-ANALISADOR_INDUSTRIAS-', 'title': 'Analisador Indústrias', 'desc': 'Análise fiscal para indústrias',
            #     'permission': 'run_analysis_industrias', 'icon': '🏭', 'tooltip': 'Realiza análises fiscais específicas para o setor industrial.'
            # },
            # --- MODIFICAÇÃO: Bloco da Automação Linhares comentado ---
            # {
            #     'key': '-AUTOMA_LHS-', 'title': 'Automação Linhares', 'desc': 'Extração de NFSe',
            #     'permission': 'run_automation_lhs', 'icon': '🤖', 'tooltip': 'Automatiza a extração de Notas Fiscais de Serviço Eletrônicas (NFSe) de Linhares.'
            # },
            {
                'key': '-FILTRO_SPED-', 'title': 'Filtro Sped', 'desc': 'Filtragem de arquivos SPED',
                'permission': 'run_filtro_sped', 'icon': '🔍', 'tooltip': 'Filtra arquivos SPED Fiscal por período de datas para análise.'
            },
            {
                'key': '-GERAR_TEMPLATE-', 'title': 'Gerar Template de Apuração', 'desc': 'Cria um arquivo Excel (.xlsx) a partir das regras de apuração',
                'permission': 'admin', 'icon': '📝', 'tooltip': 'Gera um template de apuração em formato Excel (.xlsx) baseado nas regras definidas no sistema.'
            },
        ]

        self.admin_card_def = {
                'key': '-ADMIN_MENU-', 'title': 'Administração', 'desc': 'Gerenciar usuários/logs',
                'permissions': ['manage_users', 'view_logs'], 'icon': '⚙️',
                'tooltip': 'Acessa as opções de gerenciamento de usuários e visualização de logs.'
            }

        self.empresas_card_def = {
                'key': '-ADMIN_EMPRESAS-', 'title': 'Gerenciar Empresas', 'desc': 'Cadastrar empresas e regras',
                'permissions': ['admin'], 'icon': '🏢',
                'tooltip': 'Cadastra novas empresas e define regras específicas de automação.'
            }

        self.ferramentas_map: Dict[str, str] = {card['key']: card['key'] for card in self.card_definitions}

        self.show_admin_section = False
        self.show_admin_users_button = any(p in self.user_permissions for p in self.admin_card_def['permissions'])
        self.show_admin_empresas_button = any(p in self.user_permissions for p in self.empresas_card_def['permissions'])

        if self.show_admin_users_button:
            self.ferramentas_map[self.admin_card_def['key']] = self.admin_card_def['key']
            self.show_admin_section = True
        if self.show_admin_empresas_button:
            self.ferramentas_map[self.empresas_card_def['key']] = self.empresas_card_def['key']
            self.show_admin_section = True

        self.chaves_cards_validas = list(self.ferramentas_map.keys())

    def _create_styled_button(self, card_data: Dict[str, Any]) -> Button:
        key = card_data['key']
        title = card_data['title']
        desc = card_data['desc']
        icon = card_data.get('icon', '')
        tooltip = card_data.get('tooltip', title)
        font_family = self.config.font_family
        font_card_title = (font_family, 12, 'bold')
        default_card_bg = '#2D3748'
        default_card_text = '#E2E8F0'
        default_card_hover = '#4A5568'
        theme_def = self.config.theme_definition or {}
        btn_colors = self.config.btn_colors or {}
        card_colors = btn_colors.get('card', {})
        card_bg_color = card_colors.get('normal_bg', default_card_bg)
        card_text_color = card_colors.get('text', default_card_text)
        card_hover_bg_color = card_colors.get('hover_bg', default_card_hover)
        card_button_color = (card_text_color, card_bg_color)
        card_mouseover_colors = (card_text_color, card_hover_bg_color)
        button_width_chars = 35
        button_height_lines = 4
        icon_str = f"{icon}  " if icon else ""
        button_text = f"{icon_str}{title}\n{desc}"

        return sg.Button(
            button_text, key=key, size=(button_width_chars, button_height_lines),
            font=font_card_title, button_color=card_button_color,
            mouseover_colors=card_mouseover_colors, border_width=1,
            pad=(15, 15), tooltip=tooltip
        )

    def _handle_click(self, event: str, controller: 'AppController') -> None: # type: ignore
        print(f"Handling event: {event}")
        if event is None: return

        if event == '-GERAR_TEMPLATE-':
            try:
                # Constrói o caminho para o arquivo de regras de forma robusta,
                # baseando-se na localização deste próprio arquivo (menu_window.py).
                # Isso funciona tanto em modo de desenvolvimento quanto no executável (PyInstaller).
                # __file__ -> /path/to/att/app/ui/menu_window.py
                # .parent -> /path/to/att/app/ui
                # .parent -> /path/to/att/app
                regras_path = Path(__file__).parent.parent / 'fiscal' / 'regras_apuracao.json'

                save_path = sg.popup_get_file(
                    'Salvar Template de Apuração',
                    save_as=True,
                    default_extension=".xlsx",
                    file_types=(("Excel Files", "*.xlsx"),),
                    no_window=True # Usa o diálogo de arquivo nativo do SO
                )
                if save_path:
                    gerar_template_de_regras(str(regras_path), save_path)
                    sg.popup_ok(f"Template gerado com sucesso em:\n{save_path}")

            except FileNotFoundError:
                 sg.popup_error(f"Arquivo de regras não encontrado no caminho esperado:\n{regras_path}.\n\nVerifique se o arquivo 'regras_apuracao.json' existe na pasta 'fiscal'.")
            except Exception as e:
                sg.popup_error(f"Ocorreu um erro ao gerar o template:\n{e}\n\n{traceback.format_exc()}")

        elif event == self.empresas_card_def['key']:
            print("Button/Card clicked, launching tool: Gerenciar Empresas")
            current_window = self.window # Salva referência
            if current_window: current_window.hide()
            try:
                empresa_cadastro_window.main(self.config)
            except Exception as e:
                sg.popup_error(f"Erro ao abrir Gerenciar Empresas:\n{e}\n{traceback.format_exc()}")
            finally:
                if current_window: current_window.un_hide()

        elif event in self.ferramentas_map and event != self.empresas_card_def['key']:
            print(f"Button/Card clicked, launching tool via controller: {event}")

            # --- Bloco de hide/unhide ADICIONADO ---
            current_window = self.window # Salva referência
            if current_window: current_window.hide()
            try:
                controller._launch_tool(event)
            except Exception as e:
                 print(f"Erro retornado ao menu_window por _launch_tool: {e}")
                 sg.popup_error(f"Erro ao lançar ferramenta '{event}':\n{e}")
            finally:
                 if current_window:
                    try:
                        current_window.un_hide()
                        current_window.bring_to_front()
                    except Exception as unhide_e:
                         print(f"Erro ao re-exibir menu: {unhide_e}")
            # --- FIM DA ALTERAÇÃO ---

        elif event == '-LOGOUT-':
            print("Logout button event handled in run loop.")


    def _build_layout(self) -> List[List[Element]]:
        font_family = self.config.font_family
        font_small = (font_family, 10)
        theme = self.config.theme_definition or {}
        bg_color = theme.get('BACKGROUND', '#1E1E1E')
        text_color = theme.get('TEXT', '#E0E0E0')
        separator_color = theme.get('INPUT', '#4A5568')
        logo_placeholder_color = theme.get('INPUT', '#4A5568')
        logout_icon = ""

        header = [
            [
                sg.Text("VM", font=(font_family, 14, 'bold'), background_color=bg_color, text_color=logo_placeholder_color, pad=((10,10), (10,5))),
                sg.Text(f"Bem-vindo, {self.username.capitalize()}!", font=(font_family, 18, 'bold'), background_color=bg_color, text_color=text_color, pad=((0,0), (10,5))),
                sg.Push(background_color=bg_color),
                sg.Button(f'{logout_icon} Logout', key='-LOGOUT-', font=font_small, button_color=self.config.btn_colors.get('exit',{}).get('normal','#6C757D'), mouseover_colors=self.config.btn_colors.get('exit',{}).get('hover','#868E96'), pad=((0,10), (10,5)))
            ],
            [sg.HorizontalSeparator(color=separator_color)]
        ]

        layout_cards = []
        for card_def in self.card_definitions:
            required_permission = card_def.get('permission')
            if not required_permission or required_permission in self.user_permissions:
                layout_cards.append(self._create_styled_button(card_def))

        cards_por_linha = 2
        button_width_chars = 35
        button_height_lines = 4

        layout_cards_rows = []
        for i in range(0, len(layout_cards), cards_por_linha):
            linha_atual = layout_cards[i:i + cards_por_linha]
            while len(linha_atual) < cards_por_linha:
                 linha_atual.append(sg.Text('', size=(button_width_chars+4, button_height_lines+2), background_color=bg_color))
            layout_cards_rows.append([sg.Push(bg_color), *linha_atual, sg.Push(bg_color)])

        layout_principal = [
            [sg.Column(header, expand_x=True, background_color=bg_color)],
            [sg.VPush(background_color=bg_color)],
            [sg.Column(layout_cards_rows, background_color=bg_color, expand_x=True, element_justification='center', pad=((0,0), (20,20)))],
        ]

        if self.show_admin_section:
            admin_buttons_row = []
            if self.show_admin_users_button:
                admin_users_button = self._create_styled_button(self.admin_card_def)
                admin_buttons_row.append(admin_users_button)
            if self.show_admin_empresas_button:
                admin_empresas_button = self._create_styled_button(self.empresas_card_def)
                admin_buttons_row.append(admin_empresas_button)

            layout_admin_section = [
                [sg.VPush(background_color=bg_color)],
                [sg.HorizontalSeparator(color=separator_color, pad=((0,0),(10,15)))],
                [sg.Push(background_color=bg_color), *admin_buttons_row, sg.Push(background_color=bg_color)],
                [sg.VPush(background_color=bg_color)]
            ]
            layout_principal.extend(layout_admin_section)
        else:
             layout_principal.append([sg.VPush(background_color=bg_color)])

        return layout_principal

    def run(self, controller: 'AppController') -> bool: # type: ignore
        layout = self._build_layout()
        theme = self.config.theme_definition or {}
        bg_color = theme.get('BACKGROUND', '#1E1E1E')
        cards_por_linha = 2

        num_cards_visiveis = sum(1 for card in self.card_definitions if not card.get('permission') or card.get('permission') in self.user_permissions)
        num_card_rows = (num_cards_visiveis + cards_por_linha - 1) // cards_por_linha
        base_height = 120
        card_row_height = 125
        admin_height = 200 if self.show_admin_section else 50
        window_height = base_height + (num_card_rows * card_row_height) + admin_height
        window_width = 800
        window_height = max(window_height, 550)

        try:
            self.window = sg.Window('VM Contadores - Hub de Ferramentas', layout, size=(window_width, window_height),
                                     element_justification='center', finalize=True, resizable=True,
                                     icon=self.config.app_icon_path, background_color=bg_color)
        except Exception as e:
            sg.popup_error(f"Erro ao criar a janela do menu:\n{e}", title="Erro de Layout")
            print(f"Erro ao criar a janela do menu: {e}")
            traceback.print_exc()
            return False

        wants_to_logout = False
        while True:
            try:
                event, values = self.window.read()
            except Exception as e:
                print(f"Erro durante window.read(): {e}")
                sg.popup_error(f"Ocorreu um erro na interface: {e}", title="Erro")
                wants_to_logout = False
                break

            if event == sg.WIN_CLOSED:
                wants_to_logout = False; break
            if event == '-LOGOUT-':
                wants_to_logout = True; break

            if event is not None and event != sg.TIMEOUT_EVENT:
                self._handle_click(event, controller)

        if self.window:
            try:
                self.window.close()
            except Exception as close_e:
                print(f"Erro ao fechar a janela do menu: {close_e}")
        self.window = None
        return wants_to_logout