# att/app/ui/sped_filter_window.py
# (Corrigido - Trocado 'text_color' por 'title_color' nos Frames)

import FreeSimpleGUI as sg
from pathlib import Path
import threading
from datetime import date, datetime
from typing import Optional, Dict, Any, Tuple
import traceback

# Importações essenciais para a classe
from app.config import ConfigLoader

# Importa a lógica de negócios
try:
    from app.sped_filter_logic import SpedFilterLogic
except ImportError:
    # Tratamento para caso o script seja executado fora do contexto principal
    print("Aviso: Erro ao importar SpedFilterLogic. Pode ser esperado se fora do app principal.")
    SpedFilterLogic = Any

class SpedFilterWindow:
    """
    Janela para filtrar arquivos SPED por data, construída com FreeSimpleGUI
    para ser compatível com o AppController.
    """

    def __init__(self, config: ConfigLoader, username: str):
        """
        Inicializa a janela do filtro SPED.
        
        Args:
            config: O objeto ConfigLoader da aplicação.
            username: O nome do usuário logado (pode ser usado para logs, etc.)
        """
        self.config = config
        self.username = username
        self.logic = SpedFilterLogic()
        self.window: sg.Window | None = None
        self.is_processing = False

        # Formato de data que o sg.CalendarButton retorna
        self.CALENDAR_FORMAT = '%Y-%m-%d %H:%M:%S'
        
        # Tema e fontes
        self.theme = self.config.theme_definition or {}
        self.font_family = self.config.font_family
        self.font_std = (self.font_family, 10)
        self.font_bold = (self.font_family, 11, 'bold')
        self.BG_COLOR = self.theme.get('BACKGROUND', '#1E1E1E')
        self.TEXT_COLOR = self.theme.get('TEXT', '#E0E0E0')
        self.INPUT_BG = self.theme.get('INPUT', '#4A5568')

    def _parse_date_from_str(self, date_str: str) -> Optional[date]:
        """Converte a string de data do PySimpleGUI para um objeto date."""
        if not date_str:
            return None
        try:
            # O CalendarButton retorna um formato como '2023-10-25 14:30:00'
            dt = datetime.strptime(date_str, self.CALENDAR_FORMAT)
            return dt.date()
        except ValueError:
            sg.popup_error(f"Formato de data inválido: {date_str}")
            return None

    def _build_layout(self) -> list:
        """Cria o layout da janela com FreeSimpleGUI."""
        
        file_frame = [
            sg.Text("Arquivo SPED:", font=self.font_std, background_color=self.BG_COLOR),
            sg.Input(key='-IN_FILE-', readonly=True, font=self.font_std, size=(50, 1),
                     background_color=self.INPUT_BG, text_color=self.TEXT_COLOR),
            sg.FileBrowse("Procurar", font=self.font_std, target='-IN_FILE-',
                          file_types=(("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")))
        ]
        
        date_frame = [
            sg.Text("Data Início:", font=self.font_std, background_color=self.BG_COLOR),
            sg.Input(key='-START_DATE-', size=(12, 1), font=self.font_std,
                     background_color=self.INPUT_BG, text_color=self.TEXT_COLOR),
            sg.CalendarButton('Calendário', target='-START_DATE-', format=self.CALENDAR_FORMAT, font=self.font_std,
                               button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC')),
            
            sg.Push(background_color=self.BG_COLOR),
            
            sg.Text("Data Fim:", font=self.font_std, background_color=self.BG_COLOR),
            sg.Input(key='-END_DATE-', size=(12, 1), font=self.font_std,
                     background_color=self.INPUT_BG, text_color=self.TEXT_COLOR),
            sg.CalendarButton('Calendário', target='-END_DATE-', format=self.CALENDAR_FORMAT, font=self.font_std,
                               button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC')),
        ]

        progress_frame = [
            sg.Text("Aguardando seleção de arquivo...", key='-STATUS-', font=self.font_std,
                    background_color=self.BG_COLOR, text_color=self.TEXT_COLOR, size=(60, 2)),
            sg.ProgressBar(100, orientation='h', size=(45, 20), key='-PROGRESS-', bar_color=('#007ACC', '#4A5568'))
        ]

        layout = [
            [sg.Text("Filtrador de SPED por Período", font=(self.font_family, 18, 'bold'),
                     background_color=self.BG_COLOR, text_color=self.TEXT_COLOR, justification='center', expand_x=True)],
            
            # --- CORREÇÃO APLICADA AQUI ---
            [sg.Frame("1. Selecione o arquivo SPED", [file_frame], font=self.font_bold,
                      background_color=self.BG_COLOR, title_color=self.TEXT_COLOR, expand_x=True, pad=(0, 5))],
            
            # --- CORREÇÃO APLICADA AQUI ---
            [sg.Frame("2. Selecione o Período", [date_frame], font=self.font_bold,
                      background_color=self.BG_COLOR, title_color=self.TEXT_COLOR, expand_x=True, pad=(0, 5))],
            
            [sg.Button("3. Gerar Novo SPED Filtrado", key='-RUN-', font=self.font_bold,
                       button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC'), expand_x=True, pad=(0, 10), size=(0, 2))],
            
            # --- CORREÇÃO APLICADA AQUI ---
            [sg.Frame("Progresso", [progress_frame], font=self.font_bold,
                      background_color=self.BG_COLOR, title_color=self.TEXT_COLOR, expand_x=True, pad=(0, 5))],
            
            [sg.Button("Voltar", key='-BACK-', font=self.font_std,
                       button_color=self.config.btn_colors.get('exit',{}).get('normal','#6C757D'), size=(10, 1))]
        ]
        
        return layout

    def set_processing_state(self, processing: bool):
        """Habilita/desabilita controles durante o processamento."""
        self.is_processing = processing
        state = not processing # True para habilitar, False para desabilitar

        if not self.window: return # Janela pode ter sido fechada

        self.window['-RUN-'].update(
            text="Processando..." if processing else "3. Gerar Novo SPED Filtrado",
            disabled=processing
        )
        self.window['-BACK-'].update(disabled=processing)
        self.window['-IN_FILE-'].update(disabled=processing)
        self.window['Procurar'].update(disabled=processing)
        self.window['-START_DATE-'].update(disabled=processing)
        self.window['-END_DATE-'].update(disabled=processing)
        self.window['Calendário'].update(disabled=processing)
        self.window['Calendário0'].update(disabled=processing) # O segundo botão de calendário

    def _run_filter_thread(self, input_path: str, output_path: str, start_date: date, end_date: date):
        """
        Função executada na thread separada para não travar a UI.
        """
        try:
            def progress_callback(percent: int):
                # Envia um evento de volta para a thread principal (GUI)
                if self.window:
                    self.window.write_event_value('-THREAD_UPDATE-', (f"Processando... {percent}%", percent))
            
            # Chama a lógica de negócios
            success, message = self.logic.filter_sped_by_date(
                input_path,
                output_path,
                start_date,
                end_date,
                encoding='latin-1', # Codificação padrão do SPED
                progress_callback=progress_callback
            )
        
        except Exception as e:
            success = False
            message = f"Erro crítico na thread: {e}"
            
        finally:
            # Envia o evento de conclusão para a thread principal
            if self.window:
                self.window.write_event_value('-THREAD_DONE-', (success, message))

    def _start_filtering(self, values: Dict[str, Any]):
        """Valida os inputs e inicia a thread de processamento."""
        
        input_path = values['-IN_FILE-']
        if not input_path or not Path(input_path).exists():
            sg.popup_error("Arquivo SPED de entrada inválido ou não selecionado.")
            return

        start_date = self._parse_date_from_str(values['-START_DATE-'])
        end_date = self._parse_date_from_str(values['-END_DATE-'])

        if not start_date or not end_date:
            sg.popup_error("Datas de início e fim são obrigatórias.")
            return

        if end_date < start_date:
            sg.popup_error("A data final não pode ser anterior à data inicial.")
            return

        # 1. Pedir local para salvar
        default_filename = f"SPED_FILTRADO_{start_date.strftime('%Y%m%d')}_a_{end_date.strftime('%Y%m%d')}.txt"
        output_path = sg.popup_get_file(
            "Salvar novo arquivo SPED",
            save_as=True,
            default_extension=".txt",
            file_types=(("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")),
            default_path=default_filename,
            no_window=True # Usa o seletor de arquivos nativo do OS
        )
        
        if not output_path:
            if self.window: self.window['-STATUS-'].update("Geração cancelada.")
            return

        # 2. Iniciar processamento
        self.set_processing_state(True)
        self.window['-STATUS-'].update("Iniciando contagem de linhas...")
        self.window['-PROGRESS-'].update(0)

        threading.Thread(
            target=self._run_filter_thread,
            args=(input_path, output_path, start_date, end_date),
            daemon=True
        ).start()

    def run(self):
        """Exibe a janela e gerencia seu loop de eventos."""
        
        layout = self._build_layout()
        self.window = sg.Window(
            "Filtrador de SPED por Data",
            layout,
            modal=True, # Bloqueia o menu principal
            background_color=self.BG_COLOR,
            finalize=True,
            icon=self.config.app_icon_path
        )
        
        # Centralizar (opcional, mas bom)
        # self.window.move_to_center()

        while True:
            try:
                event, values = self.window.read()

                if event == sg.WIN_CLOSED or event == '-BACK-':
                    if self.is_processing:
                        if sg.popup_yes_no("O processamento está em andamento. Deseja realmente sair?") == 'Yes':
                            break
                    else:
                        break
                
                elif event == '-RUN-':
                    self._start_filtering(values)
                
                # --- Eventos vindos da Thread ---
                elif event == '-THREAD_UPDATE-':
                    message, percent = values[event]
                    self.window['-STATUS-'].update(message)
                    self.window['-PROGRESS-'].update(percent)
                
                elif event == '-THREAD_DONE-':
                    success, message = values[event]
                    self.set_processing_state(False)
                    self.window['-STATUS-'].update(message)
                    self.window['-PROGRESS-'].update(100 if success else 0)
                    
                    if success:
                        sg.popup_ok(message, title="Sucesso")
                    else:
                        sg.popup_error(message, title="Erro no Processamento")

            except Exception as e:
                sg.popup_error(f"Erro inesperado no loop da janela: {e}")
                traceback.print_exc()
                break # Sai do loop em caso de erro grave na UI

        if self.window:
            self.window.close()
        self.window = None