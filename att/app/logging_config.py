# att/app/logging_config.py

import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from datetime import datetime
import FreeSimpleGUI as sg # Necessário para os popups de erro

# --- Filtro para injetar username ---
class UsernameFilter(logging.Filter):
    """
    Filtro de log personalizado para injetar o nome de usuário 
    (armazenado globalmente) em cada registro de log.
    """
    def filter(self, record):
        # Tenta pegar o username da variável global, se não, usa "SYSTEM"
        record.username = getattr(logging, 'current_user', 'SYSTEM')
        return True

# Define o usuário padrão no início
logging.current_user = 'SYSTEM'
# --- FIM DO NOVO FILTRO ---


# --- FUNÇÃO DE LOGGING (MOVIDA DO MAIN.PY) ---
def setup_logging(log_dir_str: Optional[str], level: str, username: str):
    """Configura o logger raiz para console e, opcionalmente, arquivo."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Formato do Log (MODIFICADO para incluir username, level, funcName e lineno)
    log_format = '%(asctime)s - [%(username)-10s] - %(levelname)-7s - %(name)s.%(funcName)s(L:%(lineno)d) - %(message)s'
    formatter = logging.Formatter(log_format)

    # Limpa handlers existentes para evitar duplicação
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # Handler 1: Console (Sempre ativo)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(UsernameFilter()) # <-- Adiciona filtro
    root_logger.addHandler(console_handler)

    # Handler 2: Arquivo de Rede (MODIFICADO: Agora é dinâmico)
    if log_dir_str and username != "SYSTEM": # Só cria log de arquivo se o usuário não for SYSTEM
        try:
            log_dir_path = Path(log_dir_str)
            
            # --- NOVO: Cria nome de arquivo único por sessão ---
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"{username}_{timestamp}.log"
            log_path = log_dir_path / log_filename
            # --- FIM NOVO ---
            
            # Tenta criar o diretório de rede (ignora se já existir)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(UsernameFilter()) # <-- Adiciona filtro
            root_logger.addHandler(file_handler)
            
            logging.info(f"Log de arquivo configurado. Salvando em: {log_path}")
            
        except PermissionError:
            # Erro comum em rede: falta de permissão
            msg = f"Erro de Permissão: Não foi possível escrever no arquivo de log em:\n{log_dir_str}\n\nVerifique as permissões da pasta de rede."
            logging.error(msg)
            sg.popup_warning(msg, title="Erro de Log")
        except Exception as e:
            # Outros erros (ex: caminho não encontrado, rede offline)
            msg = f"Erro inesperado ao configurar o log em arquivo:\n{e}"
            logging.error(msg)
            sg.popup_warning(msg, title="Erro de Log")
    else:
        if not log_dir_str:
            logging.info("Log de arquivo não configurado (sem diretório). Salvando apenas no console.")
        if username == "SYSTEM":
            logging.info("Log de arquivo pulado para 'SYSTEM'. Será ativado após login.")