import sys
import os
import FreeSimpleGUI as sg
from pathlib import Path
import json
import traceback
import shutil  
import logging
from typing import Optional 


APP_NAME = "MeuAppFiscal" 


def get_app_data_path() -> Path:
    """
    Retorna o caminho para a pasta de dados do aplicativo em AppData\Roaming.
    Cria a pasta se ela não existir.
    """
    try:
        
        app_data_dir = Path(os.environ['APPDATA']) / APP_NAME
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return app_data_dir
    except Exception as e:
        sg.popup_error(f"Erro Crítico: Não foi possível criar o diretório de dados em AppData.\n{e}", title="Erro de Permissão")
        sys.exit(1)

def get_resource_path(relative_path: str) -> Path:
    """
    Retorna o caminho para um recurso BUNDLED (read-only).
    Funciona em dev (.py) e no .exe --onefile.
    """
    try:
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).resolve().parent
        
        return base_path / relative_path
    except Exception as e:
        sg.popup_error(f"Erro Crítico: Não foi possível localizar o caminho do recurso.\n{e}", title="Erro de Recurso")
        sys.exit(1)
# Fim get_resource_path

DATA_PATH = get_app_data_path()
db_usuarios_path = DATA_PATH / 'database_usuarios.json'
db_empresas_path = DATA_PATH / 'database.db'


config_path = get_resource_path('config.json')


if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))


try:
    from app.config import ConfigLoader
except ImportError as e:
    sg.popup_error(f"Erro fatal: Não foi possível importar ConfigLoader.\n{e}", title="Erro de Importação")
    sys.exit(1)

try:
    from app.logging_config import setup_logging
except ImportError as e:
    sg.popup_error(f"Erro fatal ao importar 'logging_config':\n{e}", title="Erro de Log")
    sys.exit(1)


try:
    config_obj = ConfigLoader(
        config_path=config_path,
        db_usuarios_path=db_usuarios_path,
        icons_path=None, 
        base_path=DATA_PATH,
        db_empresas_path=db_empresas_path
    )
    
    
    setup_logging(config_obj.log_directory_path, config_obj.log_level, "SYSTEM")

except Exception as e:
    # Se falhar aqui (ex: config.json inválido), só podemos logar no console
    logging.basicConfig(level=logging.ERROR)
    logging.critical(f"Falha crítica ao carregar ConfigLoader ou configurar logging: {e}\n{traceback.format_exc()}")
    sg.popup_error(f"Erro fatal ao carregar configuração: {e}", title="Erro de Configuração")
    sys.exit(1)


def initialize_data_files():
    """
    Verifica se os arquivos de dados existem em AppData.
    Se não existirem, copia a "versão mestre" (de dentro do .exe) para lá.
    """
    
    # --- database_usuarios.json ---
    if not db_usuarios_path.exists():
        logging.info(f"'database_usuarios.json' não encontrado em AppData. Copiando versão mestre...")
        try:
            master_db_user = get_resource_path('database_usuarios.json')
            shutil.copy2(master_db_user, db_usuarios_path)
            logging.info("Cópia do 'database_usuarios.json' concluída.")
        except Exception as e:
            logging.critical(f"Erro fatal ao copiar 'database_usuarios.json' mestre: {e}", exc_info=True)
            sg.popup_error(f"Erro fatal ao copiar 'database_usuarios.json' mestre.\n{e}", title="Erro de Instalação")
            sys.exit(1)

    # --- database.db ---
    if not db_empresas_path.exists():
        logging.info(f"'database.db' não encontrado em AppData. Copiando versão mestre...")
        try:
            master_db = get_resource_path('database.db')
            shutil.copy2(master_db, db_empresas_path)
            logging.info("Cópia do 'database.db' concluída.")
        except Exception as e:
            logging.critical(f"Erro fatal ao copiar 'database.db' mestre: {e}", exc_info=True)
            sg.popup_error(f"Erro fatal ao copiar 'database.db' mestre.\n{e}", title="Erro de Instalação")
            sys.exit(1)


try:
    from app.app_controller import AppController
    # Importar empresa_logic aqui para inicializar o banco
    from app import empresa_logic
except ImportError as e:
    
    logging.critical(f"Erro fatal: Não foi possível importar os módulos principais.\n{traceback.format_exc()}", exc_info=True)
    sg.popup_error(f"Erro fatal: Não foi possível importar os módulos principais.\n"
                   f"Detalhe do erro: {e}\n{traceback.format_exc()}",
                   title="Erro de Importação")
    sys.exit(1)


if __name__ == "__main__":
    # --- Verificação de Domínio ---
    allowed_domain = "MASSUCATTI"
    user_domain = os.getenv("USERDOMAIN", "N/A").upper()

    if user_domain != allowed_domain.upper():
        sg.popup_error(
            "Acesso não autorizado.\n\nEste aplicativo é de uso exclusivo na rede da empresa.",
            title="Acesso Negado"
        )
        sys.exit(0)
    # --- Fim da Verificação ---

    config = None # Define config no escopo mais amplo
    try:
        logging.info("Aplicação 'MeuAppFiscal' iniciada.")
        
        initialize_data_files()
                
        config = config_obj 
                
        empresa_logic.inicializar_banco(config.db_empresas_path)

        # Aplica o tema
        theme_def = config.theme_definition
        if theme_def and isinstance(theme_def, dict):
            sg.theme_add_new(config.theme_name, theme_def)
            sg.theme(config.theme_name)
        else:
            print(f"Aviso: Definição do tema '{config.theme_name}' inválida ou ausente no config.json. Usando tema padrão.")
        
        # Instancia e roda o controlador principal
        controller = AppController(config)
        controller.run()

    except FileNotFoundError as e:
        logging.critical(f"Erro fatal: Arquivo de recurso não encontrado:\n{e}", exc_info=True)
        sg.popup_error(f"Erro fatal: Arquivo de recurso não encontrado:\n{e}\n"
                       f"Verifique se o arquivo foi incluído no PyInstaller.\n"
                       f"O aplicativo será encerrado.", title="Erro de Recurso")
        print(traceback.format_exc())
        sys.exit(1)
    except json.JSONDecodeError as e:
        config_path_str = str(config_path) if config_path else "config.json"
        logging.critical(f"Erro fatal ao ler o arquivo JSON: {config_path_str}\nDetalhe: {e}", exc_info=True)
        sg.popup_error(f"Erro fatal ao ler o arquivo JSON:\n{config_path_str}\n\n"
                       f"Verifique se o JSON está formatado corretamente.\nDetalhe: {e}", title="Erro de Configuração")
        print(traceback.format_exc())
        sys.exit(1)
    except Exception as e:
        # Este é o "pega tudo", e também vai logar no arquivo de rede
        logging.critical(f"Erro inesperado na inicialização:\n{traceback.format_exc()}", exc_info=True)
        sg.popup_error(f"Erro inesperado na inicialização:\n{e}\n\n{traceback.format_exc()}", title="Erro Fatal")
        print(traceback.format_exc())
        sys.exit(1)