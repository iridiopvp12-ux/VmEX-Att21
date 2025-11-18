import FreeSimpleGUI as sg
import threading
import subprocess
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple

# --- MODIFICAÇÃO: Importa de app.utils ---
# from app.utils import resource_path # Não utilizado neste arquivo
# --- FIM DA MODIFICAÇÃO ---

from app.config import ConfigLoader
from app.ui.admin_window import AdminWindow
from app.auth import AuthManager # Necessário se AdminWindow for chamado daqui

from app.fiscal_logic import (
    setup_logging,
    executar_analise_completa
)


class AnalyzerWindow:
    """Encapsula a criação e o loop de eventos da janela do Analisador Fiscal."""

    def __init__(self, config: ConfigLoader, username: str, permissions: List[str]):
        self.config = config
        self.username = username
        self.permissions = permissions
        self.window: sg.Window | None = None
        self.report_path: Optional[Path] = None
        self.log_filename: Optional[Path] = None

    def _build_layout(self) -> List[List[sg.Element]]:
        """Cria o layout da janela do analisador."""
        font_family = self.config.font_family
        btn_main = self.config.btn_colors.get('main', {})
        btn_admin = self.config.btn_colors.get('admin', {})
        btn_exit = self.config.btn_colors.get('exit', {})
        INPUT_BG_COLOR = self.config.theme_definition.get('INPUT', '#1E293B')
        TEXT_COLOR = self.config.theme_definition.get('TEXT', '#FAFAFA')
        BG_COLOR = self.config.theme_definition.get('BACKGROUND', '#0F172A')

        # --- MODIFICAÇÃO: Linha de Regras Detalhadas separada ---
        linha_regras_detalhadas = [
             # Aumentado o size[0] (largura) do Texto
             sg.Text('Regras Detalhadas (NCM):', size=(22, 1), justification='right', font=(font_family, 10),
                     background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR),
             sg.Input(key='-REGRAS_DETALHADAS-', readonly=True, enable_events=True, disabled=True), # Começa desabilitado
             sg.FileBrowse('📁 Procurar', file_types=(("Excel", "*.xlsx;*.xls"),), font=(font_family, 10),
                           tooltip='(Opcional) Selecione o arquivo .xlsx/.xls com as regras de NCM (Planilha1)',
                           disabled=True, key='-BROWSE_DETALHES-') # Chave para habilitar/desabilitar
        ]
        # --- FIM DA MODIFICAÇÃO ---
        
        ### --- MUDANÇA: Linha de Template de Apuração separada ---
        linha_apuracao = [
            sg.Text('Arquivo Template:', size=(22, 1), justification='right', font=(font_family, 10),
                     background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR),
            sg.Input(key='-TEMPLATE_APURACAO-', readonly=True, enable_events=True, disabled=True), # Começa desabilitado
            sg.FileBrowse('📁 Procurar Template', file_types=(("Excel", "*.xlsx"),), font=(font_family, 10),
                          tooltip='(Opcional) Selecione sua planilha .xlsx de Apuração para preenchimento automático',
                          disabled=True, key='-BROWSE_APURACAO-') # Começa desabilitado e com key
        ]
        ### --- FIM DA MUDANÇA ---


        input_section = [
            [sg.Text('Arquivo SPED Fiscal:', size=(22, 1), justification='right', font=(font_family, 10), # Tamanho ajustado
                     background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR),
             sg.Input(key='-SPED_FILE-', readonly=True, enable_events=True),
             sg.FileBrowse('📁Procurar SPED', file_types=(("Arquivos de Texto", "*.txt"),), font=(font_family, 10),
                           tooltip='Selecione o arquivo SPED .txt a ser analisado')],
            [sg.Text('Pasta com os XMLs:', size=(22, 1), justification='right', font=(font_family, 10), # Tamanho ajustado
                     background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR),
             sg.Input(key='-XML_FOLDER-', readonly=True, enable_events=True),
             sg.FolderBrowse('📁 Procurar XML', font=(font_family, 10),
                             tooltip='Selecione a pasta contendo os arquivos XML das notas fiscais')],
            [sg.Text('Arquivo de Regras (Acum.):', size=(22, 1), justification='right', font=(font_family, 10), # Tamanho ajustado e texto
                     background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR),
             sg.Input(key='-REGRAS_FILE-', readonly=True, enable_events=True),
             sg.FileBrowse('📁 Procurar REGRAS', file_types=(("CSV/Excel", "*.csv;*.xlsx;*.xls"),), font=(font_family, 10),
                           tooltip='Selecione o arquivo .csv ou .xlsx/.xls com as regras de CNPJ/CFOP x Acumulador')],

            # --- MODIFICAÇÃO: Checkbox para mostrar/ocultar ---
            [sg.Checkbox('Usar Regras Detalhadas (NCM)?', key='-TOGGLE_DETALHES-', default=False, enable_events=True,
                         background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR, pad=((10,0),(10,0)))],
            # Coloca a linha dentro de um Column para poder ocultá-la com uma única chave
            [sg.Column([linha_regras_detalhadas], key='-LINHA_DETALHES-', visible=False, background_color=INPUT_BG_COLOR, pad=(0,0))],
            # --- FIM DA MODIFICAÇÃO ---
            
            ### --- MUDANÇA: Adicionado Checkbox e Linha Colapsável para Apuração ---
            [sg.Checkbox('Apuração (Opcional)', key='-TOGGLE_APURACAO-', default=False, enable_events=True,
                         background_color=INPUT_BG_COLOR, text_color=TEXT_COLOR, pad=((10,0),(10,0)))],
            [sg.Column([linha_apuracao], key='-LINHA_APURACAO-', visible=False, background_color=INPUT_BG_COLOR, pad=(0,0))]
            ### --- FIM DA MUDANÇA ---
        ]

        botoes_rodape = [
            sg.Button('✅ Abrir Relatório', key='-OPEN_REPORT-', font=(font_family, 11, 'bold'),
                      button_color=btn_main.get('normal', '#007ACC'),
                      mouseover_colors=btn_main.get('hover', '#0099FF'),
                      disabled_button_color=('#FAFAFA', btn_main.get('disabled', '#4A4A4A')),
                      visible=False, disabled=True,
                      tooltip='Abrir a planilha Excel gerada com o resultado da análise'),
            sg.Push(),
        ]

        if 'manage_users' in self.permissions:
            botoes_rodape.append(
                sg.Button('⚙️ Gerenciar Usuários', key='-ADMIN_PANEL-', font=(font_family, 11, 'bold'),
                          button_color=btn_admin.get('normal', '#5A5A5A'),
                          mouseover_colors=btn_admin.get('hover', '#7A7A7A'),
                          tooltip='Abrir painel para criar novos usuários')
            )

        botoes_rodape.append(
            sg.Button('⬅️ Voltar', key='-SAIR-', font=(font_family, 11, 'bold'),
                      button_color=btn_exit.get('normal', '#4B5563'),
                      mouseover_colors=btn_exit.get('hover', '#6B7280'),
                      tooltip='Voltar para o menu principal')
        )

        layout = [
            [sg.Text('Analisador Fiscal Massucatti', font=(font_family, 22, 'bold'), justification='center',
                     expand_x=True, pad=((0,0),(15,5)), background_color=BG_COLOR, text_color=TEXT_COLOR)],
            [sg.Text('Conciliação de SPED Fiscal vs. XMLs de Notas Fiscais', font=(font_family, 11),
                     justification='center', expand_x=True, background_color=BG_COLOR, text_color=TEXT_COLOR)],
            [sg.HorizontalSeparator(pad=((0,0),(10,15)))],
            
            [sg.Frame('Configurações de Análise',
                      input_section,
                      font=(font_family, 12, 'bold'),
                      pad=(10, 10),
                      expand_x=True,
                      background_color=INPUT_BG_COLOR,
                      title_color=TEXT_COLOR,
                      border_width=1,
                      element_justification='left')],
            
            [sg.Button('▶️ INICIAR ANÁLISE COMPLETA', key='-START-', font=(font_family, 14, 'bold'),
                       size=(35, 2), button_color=btn_main.get('normal', '#007ACC'),
                       mouseover_colors=btn_main.get('hover', '#0099FF'),
                       disabled_button_color=('#FAFAFA', btn_main.get('disabled', '#4A4A4A')),
                       disabled=True, tooltip='Iniciar o processo de conciliação fiscal',
                       pad=((0,0), (20, 20)))], 
            
            [sg.Multiline(size=(90, 10), key='-OUTPUT-', background_color='#212121', text_color='#E0E0E0',
                          disabled=True, autoscroll=True, reroute_stdout=True, reroute_stderr=True,
                          font=(font_family, 9), expand_x=True)],
            [sg.ProgressBar(100, orientation='h', size=(60, 20), key='-PROGRESS_BAR-', expand_x=True)],
            
            [sg.Graph((20,20), (0,0), (20,20), key='-STATUS_DOT-', background_color=BG_COLOR),
             sg.Text('Status: Aguardando arquivos...', key='-STATUS_TEXT-', font=(font_family, 10),
                     expand_x=True, background_color=BG_COLOR, text_color=TEXT_COLOR)],
            
            [sg.HorizontalSeparator(pad=((0,0),(15,5)))],
            botoes_rodape
        ]
        return layout

    def _open_report(self) -> None:
        """Abre o arquivo de relatório gerado."""
        if self.report_path and self.report_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self.report_path.resolve()))
                elif sys.platform == "darwin": # macOS
                    subprocess.run(['open', str(self.report_path.resolve())])
                else: # linux variants
                    subprocess.run(['xdg-open', str(self.report_path.resolve())])
            except Exception as e:
                sg.popup_error(f"Não foi possível abrir o relatório automaticamente.\nErro: {e}\n\nCaminho: {self.report_path.resolve()}", title="Erro")
        else:
            sg.popup_error("Arquivo de relatório não encontrado.", title="Erro")


    def run(self) -> None:
        """Exibe a janela do analisador e gerencia seu loop de eventos."""
        layout = self._build_layout()
        
        ### --- MUDANÇA: Aumentei um pouco mais a altura (de 820 para 850) para o novo checkbox ---
        self.window = sg.Window('Massucatti - Analisador Fiscal', layout, size=(800, 850), 
                                finalize=True, element_justification='center', modal=True,
                                icon=self.config.app_icon_path)
        ### --- FIM DA MUDANÇA ---

        status_dot = self.window['-STATUS_DOT-']
        status_dot_id = status_dot.draw_circle((10,10), 8, fill_color='#5A5A5A', line_color='#5A5A5A')

        self.log_filename = setup_logging(self.config.base_path, self.window['-OUTPUT-'], self.username)

        if 'run_analysis' not in self.permissions:
            self.window['-START-'].update(disabled=True, text="PERMISSÃO NEGADA")
            self.window['-STATUS_TEXT-'].update('Status: Sem permissão para executar análises.')
            status_dot.delete_figure(status_dot_id)
            status_dot_id = status_dot.draw_circle((10,10), 8, fill_color='#E74C3C', line_color='#E74C3C')

        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED or event == '-SAIR-': break

            if event == '-ADMIN_PANEL-':
                if 'manage_users' in self.permissions:
                    admin_win = AdminWindow(self.config)
                    admin_win.run()
                else:
                    sg.popup_error("Você não tem permissão para gerenciar usuários.", title="Acesso Negado")

            
            ### --- MUDANÇA: Adicionado '-TOGGLE_APURACAO-' à lista de eventos ---
            if event in ('-SPED_FILE-', '-XML_FOLDER-', '-REGRAS_FILE-', '-REGRAS_DETALHADAS-', 
                         '-TOGGLE_DETALHES-', '-TEMPLATE_APURACAO-', '-TOGGLE_APURACAO-'):
            ### --- FIM DA MUDANÇA ---
            
                # Arquivos obrigatórios
                obrigatorios_ok = all(values.get(k) for k in ['-SPED_FILE-', '-XML_FOLDER-', '-REGRAS_FILE-'])
                # Verifica regras detalhadas apenas se o checkbox estiver marcado
                detalhes_visiveis = values.get('-TOGGLE_DETALHES-', False)
                detalhes_ok = (not detalhes_visiveis) or (detalhes_visiveis and values.get('-REGRAS_DETALHADAS-'))

                # O template de apuração é opcional, então NÃO é incluído no 'pode_iniciar'
                pode_iniciar = obrigatorios_ok and detalhes_ok

                # Só habilita if tiver os arquivos E a permissão
                if 'run_analysis' in self.permissions:
                    self.window['-START-'].update(disabled=not pode_iniciar)
            
            # --- MODIFICAÇÃO: Lógica para mostrar/ocultar linha de detalhes ---
            if event == '-TOGGLE_DETALHES-':
                visivel = values['-TOGGLE_DETALHES-']
                self.window['-LINHA_DETALHES-'].update(visible=visivel)
                # Habilita/desabilita input e botão de procurar detalhes
                self.window['-REGRAS_DETALHADAS-'].update(disabled=not visivel)
                self.window['-BROWSE_DETALHES-'].update(disabled=not visivel)
                # Limpa o campo se for ocultado
                if not visivel:
                    self.window['-REGRAS_DETALHADAS-'].update('')
                # Reavalia se o botão START deve ser habilitado
                obrigatorios_ok = all(values.get(k) for k in ['-SPED_FILE-', '-XML_FOLDER-', '-REGRAS_FILE-'])
                detalhes_ok = (not visivel) or (visivel and values.get('-REGRAS_DETALHADAS-'))
                pode_iniciar = obrigatorios_ok and detalhes_ok
                if 'run_analysis' in self.permissions:
                    self.window['-START-'].update(disabled=not pode_iniciar)
            # --- FIM DA MODIFICAÇÃO ---
            
            ### --- MUDANÇA: Lógica para mostrar/ocultar linha de APURAÇÃO ---
            if event == '-TOGGLE_APURACAO-':
                visivel = values['-TOGGLE_APURACAO-']
                self.window['-LINHA_APURACAO-'].update(visible=visivel)
                # Habilita/desabilita input e botão
                self.window['-TEMPLATE_APURACAO-'].update(disabled=not visivel)
                self.window['-BROWSE_APURACAO-'].update(disabled=not visivel)
                # Limpa o campo se for ocultado
                if not visivel:
                    self.window['-TEMPLATE_APURACAO-'].update('')
                # OBS: Não é necessário reavaliar o botão '-START-' aqui,
                # pois este campo é opcional e não afeta 'pode_iniciar'.
            ### --- FIM DA MUDANÇA ---


            if event == '-START-':
                self.log_filename = setup_logging(self.config.base_path, self.window['-OUTPUT-'], self.username)
                self.window['-OUTPUT-'].update('')
                self.window['-START-'].update(disabled=True)
                self.window['-OPEN_REPORT-'].update(visible=False, disabled=True)
                status_dot.delete_figure(status_dot_id)
                status_dot_id = status_dot.draw_circle((10,10), 8, fill_color='#F1C40F', line_color='#F1C40F')
                self.window['-STATUS_TEXT-'].update('Status: Iniciando análise...')
                self.window['-PROGRESS_BAR-'].update(0, 100)

                sped_path = Path(values['-SPED_FILE-'])
                xml_path = Path(values['-XML_FOLDER-'])
                regras_path = Path(values['-REGRAS_FILE-'])

                # Obtém o caminho das regras detalhadas APENAS se o checkbox estiver marcado
                regras_detalhadas_path = None
                if values.get('-TOGGLE_DETALHES-') and values.get('-REGRAS_DETALHADAS-'):
                    try:
                        regras_detalhadas_path = Path(values['-REGRAS_DETALHADAS-'])
                    except TypeError:
                        sg.popup_warning("Caminho para regras detalhadas inválido. A análise detalhada será ignorada.", title="Aviso")
                        regras_detalhadas_path = None

                # --- ★ MODIFICAÇÃO: Obter o caminho do template de apuração (opcional) ★ ---
                template_apuracao_path: Optional[Path] = None
                
                ### --- MUDANÇA: Verifica se o checkbox de apuração está marcado ---
                if values.get('-TOGGLE_APURACAO-') and values.get('-TEMPLATE_APURACAO-'):
                ### --- FIM DA MUDANÇA ---
                    try:
                        temp_path = Path(values['-TEMPLATE_APURACAO-'])
                        if temp_path.exists():
                            template_apuracao_path = temp_path
                        else:
                            sg.popup_warning(f"Arquivo de template não encontrado:\n{temp_path}\n\nO preenchimento automático será ignorado.", title="Aviso")
                            template_apuracao_path = None
                    except Exception:
                        sg.popup_warning("Caminho do template de apuração inválido. O preenchimento automático será ignorado.", title="Aviso")
                        template_apuracao_path = None
                
                threading.Thread(target=executar_analise_completa,
                                 args=(sped_path, xml_path, regras_path, self.window, self.username,
                                       self.config.cfop_sem_credito_icms, self.config.cfop_sem_credito_ipi,
                                       self.config.tolerancia_valor,
                                       regras_detalhadas_path, # Arg 9
                                       template_apuracao_path  # Arg 10 (Novo)
                                      ),
                                 daemon=True).start()
                
            # ... (Restante do loop run: -PROGRESS_UPDATE-, -XML_PARSE_ERROR-, -THREAD_DONE-, -THREAD_ERROR-, -OPEN_REPORT- permanece o mesmo) ...
            if event == '-PROGRESS_UPDATE-':
                progress_data: Tuple[int, int] = values[event]
                max_val = progress_data[1] if progress_data[1] > 0 else 100
                current_val = progress_data[0]
                self.window['-PROGRESS_BAR-'].update(current_count=current_val, max=max_val)
                if max_val > 0 :
                    percent = int((current_val / max_val) * 100)
                    self.window['-STATUS_TEXT-'].update(f'Status: Processando XMLs... ({percent}%)')

            if event == '-XML_PARSE_ERROR-':
                sg.popup_warning(f"XML mal formatado ignorado:\n{values[event]}", title="Aviso")

            if event == '-THREAD_DONE-':
                result_data: Tuple[Path, int] = values[event]
                self.report_path, total_problemas = result_data
                status_msg = (f'Concluído! ({total_problemas} notas com inconsistências)' if total_problemas > 0 else
                            'Concluído! Nenhuma inconsistência encontrada.')
                status_dot.delete_figure(status_dot_id)
                status_dot_id = status_dot.draw_circle((10,10), 8, fill_color='#2ECC71', line_color='#2ECC71')
                self.window['-STATUS_TEXT-'].update(f'Status: {status_msg}')
                self.window['-OPEN_REPORT-'].update(visible=True, disabled=False)
                # Reabilita o botão START se tiver permissão e arquivos válidos
                obrigatorios_ok = all(values.get(k) for k in ['-SPED_FILE-', '-XML_FOLDER-', '-REGRAS_FILE-'])
                detalhes_visiveis = values.get('-TOGGLE_DETALHES-', False)
                detalhes_ok = (not detalhes_visiveis) or (detalhes_visiveis and values.get('-REGRAS_DETALHADAS-'))
                pode_iniciar = obrigatorios_ok and detalhes_ok
                if 'run_analysis' in self.permissions:
                        self.window['-START-'].update(disabled=not pode_iniciar)
                sg.popup_ok('Análise de conciliação concluída!', title="Sucesso")

            if event == '-THREAD_ERROR-':
                error_message = values.get(event, "Erro desconhecido")
                status_dot.delete_figure(status_dot_id)
                status_dot_id = status_dot.draw_circle((10,10), 8, fill_color='#E74C3C', line_color='#E74C3C')
                self.window['-STATUS_TEXT-'].update('Status: ERRO NA ANÁLISE!')
                log_msg_display = f"Consulte o arquivo de log para mais detalhes técnicos:\n{self.log_filename}" if self.log_filename else "Não foi possível criar o arquivo de log."
                sg.popup_error(f"A análise falhou.\n\nDetalhe: {error_message}\n\n{log_msg_display}", title="Erro na Análise")
                # Reabilita o botão START se tiver permissão e arquivos válidos
                obrigatorios_ok = all(values.get(k) for k in ['-SPED_FILE-', '-XML_FOLDER-', '-REGRAS_FILE-'])
                detalhes_visiveis = values.get('-TOGGLE_DETALHES-', False)
                detalhes_ok = (not detalhes_visiveis) or (detalhes_visiveis and values.get('-REGRAS_DETALHADAS-'))
                pode_iniciar = obrigatorios_ok and detalhes_ok
                if 'run_analysis' in self.permissions:
                        self.window['-START-'].update(disabled=not pode_iniciar)

            if event == '-OPEN_REPORT-':
                self._open_report()

        if self.window:
            self.window.close()
        self.window = None