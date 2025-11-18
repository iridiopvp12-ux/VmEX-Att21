# app/fiscal/apuracao_logic.py
import logging
import pandas as pd
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from typing import Optional, Any, List, Union
import FreeSimpleGUI as sg
import json

def _encontrar_celula(ws: Worksheet, texto_procurado: str) -> Optional[tuple[int, int]]:
    """
    Encontra as coordenadas (linha, coluna) de uma célula baseada no texto exato.
    """
    if texto_procurado is None: return None
    texto_limpo = str(texto_procurado).strip()

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None and str(cell.value).strip() == texto_limpo:
                return (cell.row, cell.column)
    return None

def _escrever_valor_adjacente(ws: Worksheet, label_texto: str, valor: Any, offset_col: int = 1):
    """
    Escreve o valor na célula ao lado (offset_col=1) da célula onde encontrou o 'label_texto'.
    """
    coordenadas = _encontrar_celula(ws, label_texto)
    if coordenadas:
        (row, col) = coordenadas
        try:
            celula_alvo = ws.cell(row=row, column=col + offset_col)
            celula_alvo.value = valor
        except Exception as e:
            logging.warning(f"Erro ao escrever valor para '{label_texto}': {e}")
    else:
        # Loga aviso mas não para o processo
        logging.warning(f"RÓTULO NÃO ENCONTRADO NO EXCEL: '{label_texto}'")

def somar_por_cfop(df: pd.DataFrame, cfops: Union[str, List[str]], coluna_valor: str) -> float:
    """
    Filtra o DataFrame por uma lista de CFOPs e soma a coluna especificada.
    """
    if df.empty: return 0.0

    lista_cfops = [cfops] if isinstance(cfops, str) else cfops
    # Converte para string para garantir match
    mask = df['CFOP (SPED)'].astype(str).isin(lista_cfops)

    val = df[mask][coluna_valor].sum()
    return float(val)

def preencher_template_apuracao(template_path: Path, df_entradas: pd.DataFrame, df_saidas: pd.DataFrame) -> None:
    """
    Preenche o template de apuração com base em uma lista de regras estruturadas.
    """
    logging.info(f"Iniciando preenchimento da apuração: {template_path.name}")

    try:
        wb = load_workbook(template_path)
        ws = wb["Apuracao"] if "Apuracao" in wb.sheetnames else wb.active
    except Exception as e:
        logging.error(f"Erro ao carregar arquivo Excel: {e}"); raise

    # Carrega as regras de apuração a partir do arquivo JSON externo.
    try:
        regras_path = Path(__file__).parent / "regras_apuracao.json"
        with open(regras_path, 'r', encoding='utf-8') as f:
            regras_apuracao = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Erro ao carregar o arquivo de regras 'regras_apuracao.json': {e}")
        raise

    resultados = {}
    regras_por_id = {r['id']: r for r in regras_apuracao}

    # --- PASSO 1: Calcular todas as regras do tipo 'soma_df' ---
    regras_soma_df = [r for r in regras_apuracao if r.get('tipo') == 'soma_df']
    for regra in regras_soma_df:
        df_alvo = df_entradas if regra.get('tipo_df') == 'entradas' else df_saidas
        valor = 0.0

        if not df_alvo.empty:
            if regra.get('operacao') == 'total':
                valor = df_alvo[regra['coluna']].sum()
            elif regra.get('operacao') == 'cfop':
                valor = somar_por_cfop(df_alvo, regra.get('cfops', []), regra['coluna'])

        resultados[regra['id']] = valor

    # --- PASSO 2: Calcular regras 'soma_celulas' ---
    regras_soma_celulas = [r for r in regras_apuracao if r.get('tipo') == 'soma_celulas']
    for regra in regras_soma_celulas:
        valor_total = 0.0
        for id_soma in regra.get('ids_soma', []):
            valor_total += resultados.get(id_soma, 0.0)
        resultados[regra['id']] = valor_total

    # --- PASSO 3: Calcular regras 'formula' ---
    regras_formula = [r for r in regras_apuracao if r.get('tipo') == 'formula']
    for regra in regras_formula:
        formula_str = regra.get('formula_str', "")
        # Substitui os IDs pelos seus valores no dicionário de resultados
        for id_val, valor in resultados.items():
            formula_str = formula_str.replace(id_val, str(valor))

        try:
            # Avalia a expressão matemática de forma segura
            resultado_formula = eval(formula_str, {"__builtins__": None}, {})
            resultados[regra['id']] = resultado_formula
        except Exception as e:
            logging.error(f"Erro ao calcular a fórmula para a regra '{regra['id']}': {e}")
            resultados[regra['id']] = 0.0 # Define um valor padrão em caso de erro

    # --- PASSO FINAL: Escrever todos os resultados na planilha ---
    for id_regra, valor_calculado in resultados.items():
        label = regras_por_id[id_regra].get('label')
        if label:
            _escrever_valor_adjacente(ws, label, valor_calculado)

    try:
        wb.save(template_path)
        logging.info(f"Arquivo '{template_path.name}' atualizado com sucesso.")
    except Exception as e:
        sg.popup_error(f"Erro ao salvar apuração.\nVerifique se o arquivo '{template_path.name}' não está aberto.\nErro: {e}")
        raise
