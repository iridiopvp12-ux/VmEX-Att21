# att/app/ui/automacao_window.py
# (VERSÃO HÍBRIDA - MODIFICADA PARA CHAMAR A NOVA LÓGICA)

import FreeSimpleGUI as sg
import threading
import traceback
import logging
import sys
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple, Callable

# Importações da aplicação
# (Certifique-se que os 'imports' abaixo funcionam na sua estrutura)
try:
    from app.config import ConfigLoader 
    from app.ui.admin_window import AdminWindow
    from app.auth import AuthManager
except ImportError:
    logging.warning("Não foi possível importar ConfigLoader/AdminWindow/AuthManager. Continuando...")
    # Classes 'dummy' para contornar a falta de importação
    class ConfigLoader: 
        theme_definition = {}
        font_family = "Arial"
        btn_colors = {}
        base_path = Path(".")
        app_icon_path = None
    class AdminWindow: pass
    class AuthManager: pass


# Lógica de negócios
try:
    from app import empresa_logic
    from app import automacao_logic  # <-- Deve conter a NOVA função híbrida
    from app.fiscal_logic import MultilineHandler, setup_logging 
except ImportError as e:
    try:
        from .. import automacao_logic
        from .. import empresa_logic
        from ..fiscal_logic import MultilineHandler, setup_logging
    except ImportError as e2:
        # Se mesmo a importação relativa falhar, tenta importar localmente
        # (Isso pode acontecer se automacao_logic.py estiver na mesma pasta)
        try:
            import automacao_logic # type: ignore
            # Crie 'dummies' para as outras lógicas se não forem essenciais aqui
            class fiscal_logic: # type: ignore
                def MultilineHandler(self, *args): pass
                def setup_logging(self, *args): 
                    logging.basicConfig(level=logging.INFO)
                    logging.info("Setup de logging 'dummy' ativado.")
                    return "dummy.log"
            setup_logging = fiscal_logic.setup_logging
            class MultilineHandler(logging.Handler): # Definição 'dummy'
                def __init__(self, *args):
                    super().__init__()
                def emit(self, record):
                    pass # Não faz nada
        except ImportError as e3:
             sg.popup_error(f"Erro fatal ao importar lógicas: {e2}\n\nTentativa local: {e3}", title="Erro de Importação")
             sys.exit(1)


class AutomacaoWindow:
    """
    Janela para executar a automação de download de NFSe de Linhares.
    (Versão Híbrida "Um por Um" / "Lote")
    """

    def __init__(self, config: ConfigLoader, username: str):
        self.config = config
        self.username = username
        self.window: sg.Window | None = None
        self.is_processing = False
        self.log_filename: Optional[Path] = None
        
        self.CALENDAR_FORMAT = '%Y-%m-%d %H:%M:%S'
        
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
            dt = datetime.strptime(date_str, self.CALENDAR_FORMAT)
            return dt.date()
        except ValueError:
            sg.popup_error(f"Formato de data inválido: {date_str}")
            return None

    def _formatar_cnpj(self, cnpj_raw: str) -> str:
        """Limpa e formata um CNPJ/CPF para o padrão com pontuação."""
        if not isinstance(cnpj_raw, str):
            return ""
        
        numeros = "".join(filter(str.isdigit, cnpj_raw))
        
        if len(numeros) == 14: # CNPJ
            return f"{numeros[0:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:14]}"
        elif len(numeros) == 11: # CPF (caso seja usado)
            return f"{numeros[0:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:11]}"
        else:
            return cnpj_raw # Retorna o original se for inválido

    def _build_layout(self) -> list:
        """Cria o layout da janela com FreeSimpleGUI."""
        
        login_frame_layout = [
            [sg.Text("Usuário Portal:", font=self.font_std, s=(12,1), background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Input(key='-PORTAL_USER-', font=self.font_std, s=(20,1), background_color=self.INPUT_BG, text_color=self.TEXT_COLOR)],
            [sg.Text("Senha Portal:", font=self.font_std, s=(12,1), background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Input(key='-PORTAL_PASS-', font=self.font_std, s=(20,1), password_char='*', background_color=self.INPUT_BG, text_color=self.TEXT_COLOR)],
            [sg.HorizontalSeparator()],
            [sg.Text("Data Início:", font=self.font_std, s=(12,1), background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Input(key='-START_DATE-', s=(12, 1), font=self.font_std, background_color=self.INPUT_BG, text_color=self.TEXT_COLOR),
             sg.CalendarButton('Calendário', target='-START_DATE-', format=self.CALENDAR_FORMAT, font=self.font_std,
                               button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC'))],
            [sg.Text("Data Fim:", font=self.font_std, s=(12,1), background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Input(key='-END_DATE-', s=(12, 1), font=self.font_std, background_color=self.INPUT_BG, text_color=self.TEXT_COLOR),
             sg.CalendarButton('Calendário', target='-END_DATE-', format=self.CALENDAR_FORMAT, font=self.font_std,
                               button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC'))],
        ]

        processar_frame_layout = [
            [sg.Text("CNPJ para Processar:", font=self.font_std, s=(16,1), background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Input(key='-CNPJ_ATUAL-', font=self.font_std, s=(20,1), background_color=self.INPUT_BG, text_color=self.TEXT_COLOR)],
            
            # [--- MUDANÇA DE LAYOUT: Adicionando um campo de lista ---]
            [sg.Text("Ou cole uma lista de CNPJs (um por linha):", font=self.font_std, background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Multiline(key='-CNPJ_LISTA-', font=self.font_std, s=(20, 5), background_color=self.INPUT_BG, text_color=self.TEXT_COLOR, expand_x=True)],
            
            [sg.Button("▶ PROCESSAR LISTA/ÚNICO", key='-RUN-', font=(self.font_family, 14, 'bold'),
                         button_color=self.config.btn_colors.get('main',{}).get('normal','#007ACC'), expand_x=True, pad=(0, 10), size=(0, 2))],
            [sg.Text("Status: Aguardando...", key='-STATUS-', font=self.font_std,
                     background_color=self.BG_COLOR, text_color=self.TEXT_COLOR, size=(40, 1))],
            [sg.ProgressBar(100, orientation='h', size=(30, 20), key='-PROGRESS-', bar_color=('#007ACC', '#4A5568'))]
        ]
        
        layout = [
            [sg.Text("Automação de Download NFSe - Linhares (HÍBRIDA)", font=(self.font_family, 18, 'bold'),
                     background_color=self.BG_COLOR, text_color=self.TEXT_COLOR, justification='center', expand_x=True)],
            [sg.HorizontalSeparator()],
            [
                sg.Frame("1. Configurações", login_frame_layout, font=self.font_bold,
                         background_color=self.BG_COLOR, title_color=self.TEXT_COLOR, vertical_alignment='top'),
                sg.Frame("2. Processar", processar_frame_layout, font=self.font_bold,
                         background_color=self.BG_COLOR, title_color=self.TEXT_COLOR, vertical_alignment='top')
            ],
            [sg.Text("Log de Execução:", font=self.font_bold, background_color=self.BG_COLOR, text_color=self.TEXT_COLOR)],
            [sg.Multiline(size=(90, 15), key='-OUTPUT-', background_color='#212121', text_color='#E0E0E0',
                          disabled=True, autoscroll=True, reroute_stdout=False, reroute_stderr=False,
                          font=(self.font_family, 9), expand_x=True, expand_y=True)],
            [sg.Button("Voltar", key='-BACK-', font=self.font_std,
                       button_color=self.config.btn_colors.get('exit',{}).get('normal','#6C757D'), size=(10, 1))]
        ]
        
        return layout

    def set_processing_state(self, processing: bool):
        """Habilita/desabilita controles durante o processamento."""
        self.is_processing = processing
        state = not processing

        if not self.window: return

        self.window['-RUN-'].update(
            text="Processando..." if processing else "▶ PROCESSAR LISTA/ÚNICO",
            disabled=processing
        )
        self.window['-BACK-'].update(disabled=processing)
        self.window['-PORTAL_USER-'].update(disabled=processing)
        self.window['-PORTAL_PASS-'].update(disabled=processing)
        self.window['-START_DATE-'].update(disabled=processing)
        self.window['-END_DATE-'].update(disabled=processing)
        self.window['Calendário'].update(disabled=processing)
        self.window['Calendário0'].update(disabled=processing)
        
        self.window['-CNPJ_ATUAL-'].update(disabled=processing)
        self.window['-CNPJ_LISTA-'].update(disabled=processing) # <-- Bloqueia a lista também

    
    def _run_automation_thread(self,
                                 portal_user: str, portal_pass: str,
                                 start_date: date, end_date: date,
                                 lista_cnpjs_para_processar: List[str]): # <-- Recebe uma LISTA
        """
        Função executada na thread.
        Prepara o 'callback' e chama a nova lógica híbrida em 'automacao_logic.py'.
        """
        
        def progress_callback(current: int, total: int, message: str = ""):
            """Função de callback para a lógica externa enviar updates para a GUI."""
            if self.window:
                # Se estivermos processando um lote, 'current' e 'total' vêm da lógica
                # Se for um item só, podemos forçar a barra (mas a lógica já faz isso)
                percent = int((current / total) * 100)
                status_msg = f"{message}" # A lógica de lote já envia a msg (X/Y)
                self.window.write_event_value('-THREAD_UPDATE-', (status_msg, percent))

        try:
            if self.window:
                log_user_suffix = f"{self.username}_automacao"
                # (A função 'setup_logging' deve vir da sua importação 'fiscal_logic')
                self.log_filename = setup_logging(self.config.base_path, self.window['-OUTPUT-'], log_user_suffix)
            
            download_path = self.config.base_path / "Downloads_Automacao"
            download_path.mkdir(parents=True, exist_ok=True)

            # ==================================================================
            # --- [MUDANÇA CRÍTICA AQUI] ---
            # Trocamos a chamada da função antiga pela NOVA função de lote
            # ==================================================================
            
            logging.info(f"Iniciando processamento híbrido em lote para {len(lista_cnpjs_para_processar)} CNPJ(s)...")

            # Esta é a chamada para o novo arquivo 'automacao_logic.py'
            automacao_logic.processar_automacao_hibrida_em_lote(
                portal_user=portal_user,
                portal_pass=portal_pass,
                lista_de_cnpjs=lista_cnpjs_para_processar, # Passa a LISTA
                start_date=start_date,
                end_date=end_date,
                base_download_path=download_path,
                progress_callback=progress_callback
            )
            
            # ==================================================================
            
            if self.window:
                self.window.write_event_value('-THREAD_DONE-', (f"Lote de {len(lista_cnpjs_para_processar)} CNPJ(s) processado!",))

        except Exception as e:
            logging.error(f"Erro crítico na thread de automação: {e}")
            logging.error(traceback.format_exc())
            if self.window:
                self.window.write_event_value('-THREAD_ERROR-', (f"{type(e).__name__}: {e}",))
        
    
    def run(self):
        """Exibe a janela e gerencia seu loop de eventos."""
        
        layout = self._build_layout()
        self.window = sg.Window(
            "Automação de Download NFSe - Linhares (HÍBRIDA)",
            layout,
            modal=True,
            background_color=self.BG_COLOR,
            finalize=True,
            resizable=True,
            icon=self.config.app_icon_path,
            size=(800, 700)
        )
        
        log_user_suffix = f"{self.username}_automacao_ui"
        # (A função 'setup_logging' deve vir da sua importação 'fiscal_logic')
        self.log_filename = setup_logging(self.config.base_path, None, log_user_suffix)
        
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
                    portal_user = values['-PORTAL_USER-']
                    portal_pass = values['-PORTAL_PASS-']
                    start_date = self._parse_date_from_str(values['-START_DATE-'])
                    end_date = self._parse_date_from_str(values['-END_DATE-'])
                    
                    # [--- MUDANÇA NA LÓGICA DE COLETA DE CNPJ ---]
                    cnpj_unico_raw = values['-CNPJ_ATUAL-']
                    lista_cnpjs_raw = values['-CNPJ_LISTA-']
                    
                    lista_cnpjs_final = []
                    
                    # 1. Processa o campo de lista
                    if lista_cnpjs_raw and lista_cnpjs_raw.strip():
                        cnpjs_da_lista = lista_cnpjs_raw.strip().split('\n')
                        for cnpj_raw in cnpjs_da_lista:
                            cnpj_limpo = cnpj_raw.strip()
                            if cnpj_limpo: # Ignora linhas em branco
                                cnpj_formatado = self._formatar_cnpj(cnpj_limpo)
                                if len("".join(filter(str.isdigit, cnpj_formatado))) not in (11, 14):
                                    sg.popup_error(f"O CNPJ/CPF da lista '{cnpj_limpo}' parece inválido. Corrija e tente novamente.")
                                    lista_cnpjs_final = [] # Limpa a lista para parar a execução
                                    break
                                lista_cnpjs_final.append(cnpj_formatado)
                        if not lista_cnpjs_final: # Se deu erro na validação
                            continue
                    
                    # 2. Processa o campo único (só se a lista estiver vazia)
                    elif cnpj_unico_raw and cnpj_unico_raw.strip():
                        cnpj_formatado = self._formatar_cnpj(cnpj_unico_raw)
                        if len("".join(filter(str.isdigit, cnpj_formatado))) not in (11, 14):
                            sg.popup_error(f"O CNPJ/CPF '{cnpj_unico_raw}' parece inválido.")
                            continue
                        lista_cnpjs_final.append(cnpj_formatado)

                    else:
                        sg.popup_error("Nenhum CNPJ foi fornecido. Preencha o campo 'CNPJ para Processar' ou a lista de CNPJs.")
                        continue
                    
                    # Validação de credenciais e datas
                    if not portal_user or not portal_pass:
                        sg.popup_error("Usuário e Senha do Portal são obrigatórios.")
                        continue
                    if not start_date or not end_date:
                        sg.popup_error("Datas de início e fim são obrigatórias.")
                        continue
                    if end_date < start_date:
                        sg.popup_error("A data final não pode ser anterior à data inicial.")
                        continue
                    
                    self.set_processing_state(True)
                    self.window['-OUTPUT-'].update('') # Limpa o log a cada processamento
                    self.window['-STATUS-'].update(f"Iniciando processamento para {len(lista_cnpjs_final)} CNPJ(s)...")
                    self.window['-PROGRESS-'].update(0)

                    threading.Thread(
                        target=self._run_automation_thread,
                        args=(portal_user, portal_pass, start_date, end_date, lista_cnpjs_final), # Passa a LISTA
                        daemon=True
                    ).start()

                elif event == '-THREAD_UPDATE-':
                    message, percent = values[event]
                    self.window['-STATUS-'].update(message)
                    self.window['-PROGRESS-'].update(percent)
                
                elif event == '-THREAD_DONE-':
                    message, = values[event]
                    self.set_processing_state(False)
                    self.window['-STATUS-'].update(message)
                    self.window['-PROGRESS-'].update(100)
                    sg.popup_ok(message, title="Sucesso")
                
                elif event == '-THREAD_ERROR-':
                    message, = values[event]
                    self.set_processing_state(False)
                    self.window['-STATUS-'].update(f"Erro: {message}")
                    self.window['-PROGRESS-'].update(0)
                    sg.popup_error(f"A automação falhou:\n\n{message}", title="Erro na Automação")

            except Exception as e:
                sg.popup_error(f"Erro inesperado no loop da janela: {e}")
                traceback.print_exc()
                break

        if self.window:
            self.window.close()
        self.window = None

# ==============================================================================
# --- EXEMPLO DE COMO USAR (SE EXECUTAR ESTE ARQUIVO DIRETAMENTE) ---
# ==============================================================================
if __name__ == "__main__":
    
    # Configura um logging básico se o arquivo for executado sozinho
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])

    # Cria classes 'dummy' para rodar a janela de forma independente
    class DummyConfigLoader:
        theme_definition = {
            'BACKGROUND': '#2E2E2E',
            'TEXT': '#E0E0E0',
            'INPUT': '#3C3C3C',
        }
        font_family = "Helvetica"
        btn_colors = {
            'main': {'normal': ('white', '#007ACC')},
            'exit': {'normal': ('white', '#6C757D')}
        }
        base_path = Path(".").resolve() # Pasta atual
        app_icon_path = None # Sem ícone

    # (A importação de 'automacao_logic' deve funcionar se estiver na mesma pasta)
    try:
        import automacao_logic
        
        # 'Mock' (simulação) da função de setup_logging
        def setup_logging_dummy(base_path, output_element, user_suffix):
            handler = MultilineHandler(output_element)
            logger = logging.getLogger()
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logging.info("Logging 'dummy' da GUI iniciado.")
            return "dummy.log"

        # Substitui a função real pela 'dummy'
        setup_logging = setup_logging_dummy # type: ignore

    except ImportError:
        sg.popup_error("Erro: O arquivo 'automacao_logic.py' não foi encontrado na mesma pasta.")
        sys.exit(1)
    except NameError:
         # 'MultilineHandler' não foi definido, vamos defini-lo
         class MultilineHandler(logging.Handler):
            def __init__(self, multiline_element):
                super().__init__()
                self.multiline_element = multiline_element
            def emit(self, record):
                if self.multiline_element:
                    try:
                        msg = self.format(record)
                        # Tenta atualizar o elemento de log da GUI
                        self.multiline_element.print(msg, text_color='white', background_color='black')
                    except Exception as e:
                        # Se a janela for fechada, isso pode falhar.
                        # print(f"Erro no handler de log: {e}") # Debug
                        pass # Ignora erros de GUI
         
         def setup_logging_dummy(base_path, output_element, user_suffix):
            handler = MultilineHandler(output_element)
            logger = logging.getLogger()
            # Remove handlers 'multiline' antigos para evitar duplicação
            logger.handlers = [h for h in logger.handlers if not isinstance(h, MultilineHandler)]
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logging.info("Logging 'dummy' da GUI iniciado (com handler definido localmente).")
            return "dummy.log"
         
         setup_logging = setup_logging_dummy


    # --- Iniciar a janela ---
    sg.theme('DarkGrey13') # Tema padrão bonito
    config = DummyConfigLoader()
    app_window = AutomacaoWindow(config=config, username="test_user")
    app_window.run()