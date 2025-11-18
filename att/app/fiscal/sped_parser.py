import logging
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional, IO

#Lendo C100/C190, D100/D190, C500/C590, D500/D590 ---
def _processar_linhas_sped(
    f: IO[Any], 
    dados_completos: List[Dict], 
    dados_itens_sped: List[Dict], 
    dados_analiticos_sped: List[Dict],
    dados_cte_sped_d190: List[Dict] 
) -> None:
    """Função auxiliar para processar as linhas de um arquivo SPED aberto."""
    
    # --- Variáveis de Estado (para rastrear o "pai" atual) ---
    current_invoice_data: Dict[str, Any] = {}
    current_cfops_nfe: set[str] = set()
    current_chv_nfe: str = ''
    current_chv_cte: str = ''
    current_chv_energia: str = ''
    current_chv_comunicacao: str = ''

    for linha in f:
        campos = linha.strip().split('|')
        reg_type = campos[1] if len(campos) > 1 else None
        
        # --- Lógica Bloco C (NF-e Mercadorias) ---
        if reg_type == 'C100':
            if current_invoice_data:
                current_invoice_data['CFOP_SPED'] = '/'.join(sorted(list(current_cfops_nfe))) if current_cfops_nfe else ''
                dados_completos.append(current_invoice_data)
            current_cfops_nfe = set(); current_chv_nfe = ''
            current_chv_cte = ''; current_chv_energia = ''; current_chv_comunicacao = ''
            if len(campos) > 27:
                current_invoice_data = {
                    'CHV_NFE': campos[9], 'VL_DOC_SPED': campos[12], 
                    'ICMS_SPED': campos[22], 'ICMS_ST_SPED': campos[23], 
                    'IPI_SPED': campos[25], 'PIS_SPED': campos[26], 'COFINS_SPED': campos[27], 
                    'FCP_ST_SPED': '0,00', 'IPI_DEVOL_SPED': '0,00', 
                    'ICMS_SN_SPED': '0,00', 'ICMS_MONO_SPED': '0,00',
                    'TIPO_NOTA_SPED': ''
                }
                current_chv_nfe = campos[9] 
            else: current_invoice_data = {}
                
        elif reg_type == 'C170' and current_chv_nfe:
            if len(campos) > 11 and campos[11]: current_cfops_nfe.add(campos[11])
            if len(campos) > 11: 
                
                # --- CORREÇÃO APLICADA: Valor IPI Total do Item ---
                # Pega o valor total do campo 24 diretamente, sem dividir pela quantidade.
                # O resultado será o IPI total referente àquela linha do item.
                vlr_ipi_item_sped = 0.0 
                
                # Campo 24 (VL_IPI)
                if len(campos) > 24: 
                    try:
                        vl_ipi_str = campos[24]
                        if vl_ipi_str:
                            vlr_ipi_item_sped = float(vl_ipi_str.replace(',', '.'))
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Erro ao ler IPI para item {campos[2]} da NFe {current_chv_nfe}: {e}")
                        vlr_ipi_item_sped = 0.0
                
                # Converte para string com vírgula (formato interno)
                vlr_ipi_item_str = str(vlr_ipi_item_sped).replace('.', ',')
                # --- FIM DA CORREÇÃO ---
                
                dados_itens_sped.append({
                    'CHV_NFE': current_chv_nfe, 
                    'N_ITEM_SPED': campos[2], # <-- Campo 02 (NUM_ITEM)
                    'COD_PROD_SPED': campos[3], 
                    'CFOP_SPED_ITEM': campos[11], 
                    'CST_ICMS_SPED_ITEM': campos[10] if len(campos) > 10 else '',
                    'VL_OPR_SPED_ITEM': campos[7] if len(campos) > 7 else '0,00',
                    'VL_BC_ICMS_SPED_ITEM': campos[13] if len(campos) > 13 else '0,00',
                    'VL_ICMS_SPED_ITEM': campos[15] if len(campos) > 15 else '0,00',
                    'VL_BC_ICMS_ST_SPED_ITEM': campos[16] if len(campos) > 16 else '0,00',
                    'VL_ICMS_ST_SPED_ITEM': campos[18] if len(campos) > 18 else '0,00',
                    'VLR_IPI_SPED_ITEM': vlr_ipi_item_str # Agora salva o valor total do item
                })
        
        elif reg_type == 'C190' and current_chv_nfe:
            if len(campos) > 11:
                if campos[3]: current_cfops_nfe.add(campos[3]) 
                dados_analiticos_sped.append({
                    'CHV_NFE': current_chv_nfe, 'CST_ICMS_SPED_ITEM': campos[2],
                    'CFOP_SPED_ITEM': campos[3], 'ALIQ_ICMS_SPED_ITEM': campos[4],
                    'VL_OPR_SPED_ITEM': campos[5], 'VL_BC_ICMS_SPED_ITEM': campos[6],
                    'VL_ICMS_SPED_ITEM': campos[7], 'VL_BC_ICMS_ST_SPED_ITEM': campos[8],
                    'VL_ICMS_ST_SPED_ITEM': campos[9], 'VLR_IPI_SPED_ITEM': campos[11]
                })

        # --- Lógica Bloco D (CT-e) ---
        elif reg_type == 'D100':
            if current_invoice_data:
                current_invoice_data['CFOP_SPED'] = '/'.join(sorted(list(current_cfops_nfe))) if current_cfops_nfe else ''
                dados_completos.append(current_invoice_data)
            current_invoice_data = {}; current_cfops_nfe = set(); current_chv_nfe = ''
            current_chv_cte = ''; current_chv_energia = ''; current_chv_comunicacao = ''
            if len(campos) > 9:
                current_chv_cte = campos[9]
        
        elif reg_type == 'D190' and current_chv_cte:
            if len(campos) > 9:
                dados_cte_sped_d190.append({
                    'CHV_CTE': current_chv_cte, 'CST_ICMS_SPED_D190': campos[2],
                    'CFOP_SPED_D190': campos[3], 'ALIQ_ICMS_SPED_D190': campos[4],
                    'VL_OPR_SPED_D190': campos[5], 'VL_BC_ICMS_SPED_D190': campos[6],
                    'VL_ICMS_SPED_D190': campos[7], 'VL_RED_BC_SPED_D190': campos[8],
                    'COD_OBS_SPED_D190': campos[9]
                })
                dados_analiticos_sped.append({
                    'CHV_NFE': current_chv_cte,
                    'CST_ICMS_SPED_ITEM': campos[2], 'CFOP_SPED_ITEM': campos[3],
                    'ALIQ_ICMS_SPED_ITEM': campos[4], 'VL_OPR_SPED_ITEM': campos[5],
                    'VL_BC_ICMS_SPED_ITEM': campos[6], 'VL_ICMS_SPED_ITEM': campos[7],
                    'VL_BC_ICMS_ST_SPED_ITEM': '0,00', 'VL_ICMS_ST_SPED_ITEM': '0,00',
                    'VLR_IPI_SPED_ITEM': '0,00'
                })

        # --- Lógica Bloco C (Energia Elétrica) ---
        elif reg_type == 'C500':
            if current_invoice_data:
                current_invoice_data['CFOP_SPED'] = '/'.join(sorted(list(current_cfops_nfe))) if current_cfops_nfe else ''
                dados_completos.append(current_invoice_data)
            current_invoice_data = {}; current_cfops_nfe = set(); current_chv_nfe = ''
            current_chv_cte = ''; current_chv_energia = ''; current_chv_comunicacao = ''
            if len(campos) > 23:
                chv_energia_c500 = campos[10]
                current_chv_energia = chv_energia_c500 if chv_energia_c500 else f"Energia_{campos[6]}_{campos[9]}"
                dados_completos.append({
                    'CHV_NFE': current_chv_energia,
                    'VL_DOC_SPED': campos[12],
                    'ICMS_SPED': campos[18],
                    'ICMS_ST_SPED': '0,00', 'IPI_SPED': '0,00', 
                    'PIS_SPED': campos[22], 'COFINS_SPED': campos[23],
                    'FCP_ST_SPED': '0,00', 'IPI_DEVOL_SPED': '0,00', 
                    'ICMS_SN_SPED': '0,00', 'ICMS_MONO_SPED': '0,00',
                    'CFOP_SPED': campos[8],
                    'TIPO_NOTA_SPED': 'Energia Elétrica (C500)'
                })

        elif reg_type == 'C590' and current_chv_energia:
            if len(campos) > 10:
                dados_analiticos_sped.append({
                    'CHV_NFE': current_chv_energia,
                    'CST_ICMS_SPED_ITEM': campos[2], 'CFOP_SPED_ITEM': campos[3],
                    'ALIQ_ICMS_SPED_ITEM': campos[4], 'VL_OPR_SPED_ITEM': campos[5],
                    'VL_BC_ICMS_SPED_ITEM': campos[6], 'VL_ICMS_SPED_ITEM': campos[7],
                    'VL_BC_ICMS_ST_SPED_ITEM': campos[8], 'VL_ICMS_ST_SPED_ITEM': campos[9],
                    'VLR_IPI_SPED_ITEM': '0,00'
                })
        
        # --- Lógica Bloco D (Comunicação) ---
        elif reg_type == 'D500':
            if current_invoice_data:
                current_invoice_data['CFOP_SPED'] = '/'.join(sorted(list(current_cfops_nfe))) if current_cfops_nfe else ''
                dados_completos.append(current_invoice_data)
            current_invoice_data = {}; current_cfops_nfe = set(); current_chv_nfe = ''
            current_chv_cte = ''; current_chv_energia = ''; current_chv_comunicacao = ''
            if len(campos) > 21:
                current_chv_comunicacao = f"Comunicação_{campos[6]}_{campos[9]}"
                dados_completos.append({
                    'CHV_NFE': current_chv_comunicacao,
                    'VL_DOC_SPED': campos[11],
                    'ICMS_SPED': campos[17],
                    'ICMS_ST_SPED': '0,00', 'IPI_SPED': '0,00', 
                    'PIS_SPED': campos[19], 'COFINS_SPED': campos[21],
                    'FCP_ST_SPED': '0,00', 'IPI_DEVOL_SPED': '0,00', 
                    'ICMS_SN_SPED': '0,00', 'ICMS_MONO_SPED': '0,00',
                    'CFOP_SPED': campos[8],
                    'TIPO_NOTA_SPED': 'Comunicação (D500)'
                })

        elif reg_type == 'D590' and current_chv_comunicacao:
            if len(campos) > 10:
                dados_analiticos_sped.append({
                    'CHV_NFE': current_chv_comunicacao,
                    'CST_ICMS_SPED_ITEM': campos[2], 'CFOP_SPED_ITEM': campos[3],
                    'ALIQ_ICMS_SPED_ITEM': campos[4], 'VL_OPR_SPED_ITEM': campos[5],
                    'VL_BC_ICMS_SPED_ITEM': campos[6], 'VL_ICMS_SPED_ITEM': campos[7],
                    'VL_BC_ICMS_ST_SPED_ITEM': campos[8], 'VL_ICMS_ST_SPED_ITEM': campos[9],
                    'VLR_IPI_SPED_ITEM': '0,00'
                })
                
    if current_invoice_data:
        current_invoice_data['CFOP_SPED'] = '/'.join(sorted(list(current_cfops_nfe))) if current_cfops_nfe else ''
        dados_completos.append(current_invoice_data)

# (2/6): Limpando colunas do D190 de CT-e e retornando DataFrames
def extrair_dados_sped(caminho_arquivo_sped: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lê o arquivo SPED e extrai dados dos registros C100/C190 (NF-e), D100/D190 (CT-e),
    C500/C590 (Energia) e D500/D590 (Comunicação).
    """
    # --- Lendo o arquivo SPED com tentativas de encoding ---
    logging.info('Lendo e processando arquivo SPED (C100, C190, D100, D190, C500, C590, D500, D590)...')
    dados_completos: List[Dict[str, Any]] = []
    dados_itens_sped: List[Dict[str, Any]] = []
    dados_analiticos_sped: List[Dict[str, Any]] = []
    dados_cte_sped_d190: List[Dict[str, Any]] = []
    
    encoding_to_try = 'latin-1'

    try:
        with open(caminho_arquivo_sped, 'r', encoding=encoding_to_try) as f:
            _processar_linhas_sped(f, dados_completos, dados_itens_sped, dados_analiticos_sped, dados_cte_sped_d190)
            
    except UnicodeDecodeError:
        logging.warning(f"Falha ao ler SPED com {encoding_to_try}. Tentando utf-8...")
        encoding_to_try = 'utf-8'
        try:
            with open(caminho_arquivo_sped, 'r', encoding=encoding_to_try) as f:
                _processar_linhas_sped(f, dados_completos, dados_itens_sped, dados_analiticos_sped, dados_cte_sped_d190)
        except Exception as e:
            raise Exception(f"Erro inesperado ao ler o arquivo SPED ({encoding_to_try}): {e}")
    except Exception as e:
        raise Exception(f"Erro inesperado ao ler o arquivo SPED ({encoding_to_try}): {e}")

    if not dados_completos: 
        logging.warning("Nenhum registro C100, C500 ou D500 válido foi encontrado no SPED.")
    
    df_sped = pd.DataFrame(dados_completos)
    if not df_sped.empty:
        numeric_cols_sped = ['VL_DOC_SPED', 'ICMS_SPED', 'ICMS_ST_SPED', 'IPI_SPED', 'PIS_SPED', 'COFINS_SPED', 'IPI_DEVOL_SPED', 'FCP_ST_SPED', 'ICMS_SN_SPED', 'ICMS_MONO_SPED']
        for col in numeric_cols_sped:
            if col in df_sped.columns: 
                df_sped[col] = pd.to_numeric(df_sped[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).round(2)
            else:
                df_sped[col] = 0.0 
            
        string_cols_sped = ['CHV_NFE', 'CFOP_SPED', 'TIPO_NOTA_SPED']
        for col in string_cols_sped:
            if col not in df_sped.columns:
                df_sped[col] = ''

        df_sped = df_sped.fillna('')
        if 'CHV_NFE' in df_sped.columns: df_sped.drop_duplicates(subset=['CHV_NFE'], keep='first', inplace=True)

    df_sped_itens = pd.DataFrame(dados_itens_sped)
    sped_item_cols_c170 = [
        'CHV_NFE', 'N_ITEM_SPED', 'COD_PROD_SPED', 'CFOP_SPED_ITEM', 'CST_ICMS_SPED_ITEM', 
        'VL_OPR_SPED_ITEM', 'VL_BC_ICMS_SPED_ITEM', 'VL_ICMS_SPED_ITEM', 
        'VL_BC_ICMS_ST_SPED_ITEM', 'VL_ICMS_ST_SPED_ITEM', 'VLR_IPI_SPED_ITEM'
    ]
    numeric_sped_item_cols_c170 = [
        'VL_OPR_SPED_ITEM', 'VL_BC_ICMS_SPED_ITEM', 'VL_ICMS_SPED_ITEM', 
        'VL_BC_ICMS_ST_SPED_ITEM', 'VL_ICMS_ST_SPED_ITEM', 'VLR_IPI_SPED_ITEM'
    ]
    if not df_sped_itens.empty:
        df_sped_itens = df_sped_itens.fillna('')
        for col in numeric_sped_item_cols_c170:
             if col in df_sped_itens.columns:
                  df_sped_itens[col] = pd.to_numeric(df_sped_itens[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).round(2)
             else:
                  df_sped_itens[col] = 0.0
        if 'CST_ICMS_SPED_ITEM' not in df_sped_itens.columns: df_sped_itens['CST_ICMS_SPED_ITEM'] = ''
        
        # --- CORREÇÃO (garante que N_ITEM_SPED seja string antes de duplicar) ---
        df_sped_itens['N_ITEM_SPED'] = df_sped_itens['N_ITEM_SPED'].astype(str)
        df_sped_itens.drop_duplicates(subset=['CHV_NFE', 'N_ITEM_SPED'], keep='first', inplace=True)
        # --- FIM DA CORREÇÃO ---
        
        logging.info(f"Encontrados {len(df_sped_itens)} registros de itens (C170) no SPED.")
    else:
        df_sped_itens = pd.DataFrame(columns=sped_item_cols_c170)
        logging.warning("Nenhum registro de item (C170) foi processado no SPED.")
            
    df_sped_analitico_combinado = pd.DataFrame(dados_analiticos_sped)
    numeric_sped_item_cols_combinados = [
        'ALIQ_ICMS_SPED_ITEM', 'VL_OPR_SPED_ITEM', 'VL_BC_ICMS_SPED_ITEM', 'VL_ICMS_SPED_ITEM', 
        'VL_BC_ICMS_ST_SPED_ITEM', 'VL_ICMS_ST_SPED_ITEM', 'VLR_IPI_SPED_ITEM'
    ]
    if not df_sped_analitico_combinado.empty:
        df_sped_analitico_combinado = df_sped_analitico_combinado.fillna('')
        for col in numeric_sped_item_cols_combinados:
             if col in df_sped_analitico_combinado.columns:
                  df_sped_analitico_combinado[col] = pd.to_numeric(df_sped_analitico_combinado[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).round(2)
             else:
                  df_sped_analitico_combinado[col] = 0.0
        logging.info(f"Encontrados {len(df_sped_analitico_combinado)} registros analíticos (C190, D190, C590, D590) no SPED.")
    else:
        df_sped_analitico_combinado = pd.DataFrame(columns=numeric_sped_item_cols_combinados + ['CHV_NFE', 'CST_ICMS_SPED_ITEM', 'CFOP_SPED_ITEM'])
        logging.warning("Nenhum registro analítico (C190, D190, C590, D590) foi processado no SPED.")

    df_sped_cte_d190 = pd.DataFrame(dados_cte_sped_d190)
    sped_item_cols_d190_bruto = [
        'CHV_CTE', 'CST_ICMS_SPED_D190', 'CFOP_SPED_D190', 'ALIQ_ICMS_SPED_D190',
        'VL_OPR_SPED_D190', 'VL_BC_ICMS_SPED_D190', 'VL_ICMS_SPED_D190'
    ]
    numeric_sped_item_cols_d190_bruto = [
        'ALIQ_ICMS_SPED_D190', 'VL_OPR_SPED_D190', 'VL_BC_ICMS_SPED_D190',
        'VL_ICMS_SPED_D190'
    ]
    if not df_sped_cte_d190.empty:
        cols_to_drop_d190 = ['VL_RED_BC_SPED_D190', 'COD_OBS_SPED_D190']
        for col_drop in cols_to_drop_d190:
            if col_drop in df_sped_cte_d190.columns:
                df_sped_cte_d190.drop(columns=[col_drop], inplace=True)
                
        df_sped_cte_d190 = df_sped_cte_d190.fillna('')
        for col in numeric_sped_item_cols_d190_bruto:
             if col in df_sped_cte_d190.columns:
                  df_sped_cte_d190[col] = pd.to_numeric(df_sped_cte_d190[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).round(2)
             else:
                  df_sped_cte_d190[col] = 0.0
        logging.info(f"Encontrados e limpos {len(df_sped_cte_d190)} registros analíticos (D190) de CT-e no SPED.")
    else:
        df_sped_cte_d190 = pd.DataFrame(columns=sped_item_cols_d190_bruto)
        logging.warning("Nenhum registro analítico (D190) de CT-e foi processado no SPED.")

    return df_sped, df_sped_itens, df_sped_analitico_combinado, df_sped_cte_d190