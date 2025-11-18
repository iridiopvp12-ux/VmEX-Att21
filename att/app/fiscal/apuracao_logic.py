# app/fiscal/apuracao_logic.py
import logging
import pandas as pd
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from typing import Optional, Any, List, Union
import FreeSimpleGUI as sg

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
    Preenche o template com todos os campos disponíveis (Valor Contábil, BC ICMS, ICMS, BC ST, ST, IPI).
    """
    logging.info(f"Iniciando preenchimento da apuração: {template_path.name}")
    
    try:
        wb = load_workbook(template_path)
        ws = wb["Apuracao"] if "Apuracao" in wb.sheetnames else wb.active
    except Exception as e:
        logging.error(f"Erro ao carregar arquivo Excel: {e}"); raise

    # ==============================================================================
    # MAPEAMENTO COMPLETO
    # Certifique-se que sua planilha tenha estes nomes na Coluna A
    # ==============================================================================
    mapa_valores = {
        # --------------------------
        # 1. ENTRADAS (Totais)
        # --------------------------
        "Total Contabil Entradas": df_entradas['Total Operação'].sum() if not df_entradas.empty else 0,
        "Total Base ICMS Entradas": df_entradas['Base de Cálculo ICMS'].sum() if not df_entradas.empty else 0,
        "Total Credito ICMS": df_entradas['Total ICMS'].sum() if not df_entradas.empty else 0,
        "Total Credito IPI": df_entradas['Total IPI'].sum() if not df_entradas.empty else 0,
        # ST nas Entradas (Antecipação/Substituto)
        "Total Base ST Entradas": df_entradas['Base de Cálculo ICMS ST'].sum() if not df_entradas.empty else 0,
        "Total ICMS ST Entradas": df_entradas['Total ICMS ST'].sum() if not df_entradas.empty else 0,

        # --------------------------
        # 2. SAÍDAS (Totais)
        # --------------------------
        "Total Contabil Saidas": df_saidas['Total Operação'].sum() if not df_saidas.empty else 0,
        "Total Base ICMS Saidas": df_saidas['Base de Cálculo ICMS'].sum() if not df_saidas.empty else 0,
        "Total Debito ICMS": df_saidas['Total ICMS'].sum() if not df_saidas.empty else 0,
        "Total Debito IPI": df_saidas['Total IPI'].sum() if not df_saidas.empty else 0,
        # ST nas Saídas (Substituto)
        "Total Base ST Saidas": df_saidas['Base de Cálculo ICMS ST'].sum() if not df_saidas.empty else 0,
        "Total ICMS ST Saidas": df_saidas['Total ICMS ST'].sum() if not df_saidas.empty else 0,

        # --------------------------
        # 3. DETALHAMENTO SAÍDAS (Por CFOP)
        # --------------------------
        # Venda Produção Própria (5101, 6101, 5103, 6103...)
        "Venda Producao (5101/6101)": somar_por_cfop(df_saidas, ['5101', '6101', '5103', '6103'], 'Total Operação'),
        
        # Revenda Mercadoria (5102, 6102...)
        "Revenda Mercadoria (5102/6102)": somar_por_cfop(df_saidas, ['5102', '6102'], 'Total Operação'),
        
        # Venda com ST (5403, 5405, 6403...)
        "Venda c/ ST (5403/5405)": somar_por_cfop(df_saidas, ['5403', '5405', '6403', '6404'], 'Total Operação'),
        
        # Outras Saídas (Remessas, Bonificações - Ex: 5910, 5949)
        "Outras Saidas (Remessas/Bonif)": somar_por_cfop(df_saidas, ['5910', '6910', '5949', '6949'], 'Total Operação'),

        # --------------------------
        # 4. DETALHAMENTO ENTRADAS (Por CFOP)
        # --------------------------
        # Compra p/ Industrialização
        "Compra p/ Industrializacao (1101/2101)": somar_por_cfop(df_entradas, ['1101', '2101'], 'Total Operação'),
        
        # Compra p/ Comercialização
        "Compra p/ Comercializacao (1102/2102)": somar_por_cfop(df_entradas, ['1102', '2102'], 'Total Operação'),
        
        # Compra p/ Uso e Consumo
        "Uso e Consumo (1556/2556)": somar_por_cfop(df_entradas, ['1556', '2556'], 'Total Operação'),
        
        # Compra Ativo Imobilizado
        "Ativo Imobilizado (1551/2551)": somar_por_cfop(df_entradas, ['1551', '2551'], 'Total Operação'),
        
        # Compra com ST
        "Compra c/ ST (1403/2403)": somar_por_cfop(df_entradas, ['1403', '2403'], 'Total Operação'),
        
        # Devolução de Venda (Entrada)
        "Devolucao de Venda (1202/2202)": somar_por_cfop(df_entradas, ['1202', '2202'], 'Total Operação'),

        # --------------------------
        # 5. IMPOSTOS ESPECÍFICOS
        # --------------------------
        "ICMS da Producao Propria": somar_por_cfop(df_saidas, ['5101', '6101'], 'Total ICMS'),
        "ICMS da Revenda": somar_por_cfop(df_saidas, ['5102', '6102'], 'Total ICMS'),
        "ICMS ST da Revenda (5405)": somar_por_cfop(df_saidas, ['5405'], 'Total ICMS ST'),
    }

    for label, valor in mapa_valores.items():
        _escrever_valor_adjacente(ws, label, valor)

    try:
        wb.save(template_path)
        logging.info(f"Arquivo '{template_path.name}' atualizado com sucesso.")
    except Exception as e:
        sg.popup_error(f"Erro ao salvar apuração.\nVerifique se o arquivo '{template_path.name}' não está aberto.\nErro: {e}")
        raise