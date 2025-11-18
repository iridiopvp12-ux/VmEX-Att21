import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import logging 

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def inicializar_banco(db_path: Path):
    """Cria a tabela de empresas se ela não existir, usando 'with'."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Tentando conectar/criar DB em: {db_path}")
        # --- MELHORIA: Usa 'with' para garantir fechamento ---
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS empresas (
                cnpj TEXT PRIMARY KEY,
                razao_social TEXT NOT NULL,
                regras_automacao TEXT  -- Armazena regras como texto JSON
            )
            ''')
            
        logger.info(f"Banco de dados '{db_path.name}' inicializado/verificado com sucesso.")
    except sqlite3.Error as db_err: # Captura erros específicos do SQLite
        logger.error(f"Erro de SQLite ao inicializar banco de dados em {db_path}: {db_err}", exc_info=True)
        raise # Re-levanta a exceção para que a camada superior (UI/Controller) saiba do erro
    except OSError as os_err: # Captura erros ao criar diretório
         logger.error(f"Erro de Sistema Operacional ao acessar/criar diretório para {db_path}: {os_err}", exc_info=True)
         raise
    except Exception as e: # Captura qualquer outro erro inesperado
        logger.error(f"Erro CRÍTICO inesperado ao inicializar banco de dados em {db_path}: {e}", exc_info=True)
        raise


def salvar_empresa(db_path: Path, cnpj: str, razao_social: str, regras_dict: Dict[str, Any]):
    """Salva ou atualiza uma empresa (INSERT OR REPLACE), usando 'with'."""
    try:
        regras_json = json.dumps(regras_dict) # Converte o dict para string JSON
        # --- MELHORIA: Usa 'with' ---
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO empresas (cnpj, razao_social, regras_automacao)
            VALUES (?, ?, ?)
            ''', (cnpj, razao_social, regras_json))
        logger.info(f"Empresa CNPJ {cnpj} salva/atualizada com sucesso.")
    except json.JSONDecodeError as json_err: 
         logger.error(f"Erro ao converter regras para JSON para CNPJ {cnpj}: {json_err}", exc_info=True)
         raise ValueError(f"Formato inválido das regras fornecidas para {cnpj}.") from json_err
    except sqlite3.Error as db_err:
        logger.error(f"Erro de SQLite ao salvar empresa CNPJ {cnpj}: {db_err}", exc_info=True)
        raise 
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar empresa CNPJ {cnpj}: {e}", exc_info=True)
        raise


def obter_regras_empresa(db_path: Path, cnpj: str) -> Optional[Dict[str, Any]]:
    """Busca as regras de automação para um CNPJ específico, usando 'with'."""
    try:
        # --- MELHORIA: Usa 'with' ---
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT regras_automacao FROM empresas WHERE cnpj = ?", (cnpj,))
            resultado = cursor.fetchone()
        
        if resultado and resultado[0]:
            try:
                regras_dict = json.loads(resultado[0])
                return regras_dict if isinstance(regras_dict, dict) else {}
            except json.JSONDecodeError as json_err:
                logger.error(f"Erro ao decodificar JSON das regras para CNPJ {cnpj}: {json_err}. Conteúdo: '{resultado[0]}'")
                return {}
        else:
            return None
    except sqlite3.Error as db_err:
        logger.error(f"Erro de SQLite ao obter regras da empresa CNPJ {cnpj}: {db_err}", exc_info=True)
        return None 
    except Exception as e:
        logger.error(f"Erro inesperado ao obter regras da empresa CNPJ {cnpj}: {e}", exc_info=True)
        return None


def listar_todas_empresas(db_path: Path, search_term: str = "") -> List[Tuple[str, str]]:
    """Retorna lista de (cnpj, razao_social), opcionalmente filtrada, usando 'with'."""
    try:
        # --- MELHORIA: Usa 'with' ---
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            if not search_term:
                cursor.execute("SELECT cnpj, razao_social FROM empresas ORDER BY razao_social")
            else:
                term = f"%{search_term}%" 
                cursor.execute("SELECT cnpj, razao_social FROM empresas WHERE cnpj LIKE ? OR razao_social LIKE ? ORDER BY razao_social", (term, term))
            empresas = cursor.fetchall()
        return empresas
    except sqlite3.Error as db_err:
        logger.error(f"Erro de SQLite ao listar empresas (termo: '{search_term}'): {db_err}", exc_info=True)
        return [] 
    except Exception as e:
        logger.error(f"Erro inesperado ao listar empresas: {e}", exc_info=True)
        return []
def delete_empresa(db_path: Path, cnpj: str):
    """Exclui uma empresa do banco de dados pelo CNPJ, usando 'with'."""
    rows_affected = 0
    try:

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM empresas WHERE cnpj = ?", (cnpj,))
            rows_affected = cursor.rowcount 
        
        if rows_affected > 0:
            logger.info(f"Empresa CNPJ {cnpj} excluída com sucesso.")
        else:
            logger.warning(f"Nenhuma empresa encontrada com o CNPJ {cnpj} para excluir.")
            
            
    except sqlite3.Error as db_err:
        logger.error(f"Erro de SQLite ao excluir empresa CNPJ {cnpj}: {db_err}", exc_info=True)
        raise 
    except Exception as e:
        logger.error(f"Erro inesperado ao excluir empresa CNPJ {cnpj}: {e}", exc_info=True)
        raise