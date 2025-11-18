import logging
import xml.etree.ElementTree as ET
import pandas as pd
import FreeSimpleGUI as sg
from pathlib import Path
from typing import List, Any, Dict, Optional, Tuple

# Importa as constantes da pasta local
from .constants import MAPA_FINNFE

# --- CONSTANTES DE NAMESPACE ---
# Define o namespace da NF-e (com prefixo 'nfe')
NS_NFE = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
# Define o namespace do CT-e (sem prefixo, formato ElementTree)
NS_CTE_URI = 'http://www.portalfiscal.inf.br/cte'
NS_CTE_FIND = f"{{{NS_CTE_URI}}}" # Formato {uri}Tag para buscas
# --- FIM DAS CONSTANTES ---


def processar_pasta_xml(pasta_xmls: Path, window: sg.Window) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Lê arquivos XML e retorna três DataFrames: (df_nfe_totais, df_nfe_itens, df_cte_totais)."""
    logging.info('Lendo arquivos XML (NF-e e CT-e)...')
    dados_totais: List[Dict[str, Any]] = []    # Para totais de NF-e
    dados_itens: List[Dict[str, Any]] = []      # Para itens de NF-e
    dados_cte_xml: List[Dict[str, Any]] = []    # Para totais de CT-e

    # --- HELPERS DE NF-e ---
    def get_text_nfe(element: Optional[ET.Element], path: str, default: str = '') -> str:
        if element is None: return default
        node = element.find(path, NS_NFE) # Usa namespace de NF-e
        return node.text.strip() if node is not None and node.text is not None else default 

    def get_float_nfe(element: Optional[ET.Element], path: str, default: float = 0.0) -> float:
        text_val = get_text_nfe(element, path, '') 
        if not text_val: return default
        try:
            return float(text_val.replace(',', '.')) 
        except (ValueError, TypeError):
            return default

    # --- HELPERS DE CT-e (CORRIGIDOS) ---
    def get_text_cte(element: Optional[ET.Element], tag_name: str, default: str = '') -> str:
        """Busca uma tag filha usando o namespace de CTe."""
        if element is None: return default
        node = element.find(f"{NS_CTE_FIND}{tag_name}") # Usa formato {uri}Tag
        return node.text.strip() if node is not None and node.text is not None else default 
    
    def get_float_cte(element: Optional[ET.Element], tag_name: str, default: float = 0.0) -> float:
        """Busca uma tag filha e converte para float."""
        text_val = get_text_cte(element, tag_name, '') 
        if not text_val: return default
        try: return float(text_val.replace(',', '.')) 
        except (ValueError, TypeError): return default
    # --- FIM DOS HELPERS ---

    try:
        lista_arquivos_xml = list(pasta_xmls.glob('*.xml')) + list(pasta_xmls.glob('*.XML'))
    except FileNotFoundError: raise Exception(f"A pasta de XMLs não foi encontrada: {pasta_xmls}")
    
    total_files = len(lista_arquivos_xml)
    logging.info(f"Encontrados {total_files} arquivos .xml/.XML para processar.")
    window.write_event_value('-PROGRESS_UPDATE-', (0, total_files))
    if not lista_arquivos_xml: raise Exception(f"Nenhum arquivo .xml ou .XML encontrado na pasta '{pasta_xmls}'.")

    chaves_processadas: set[str] = set()
    arquivos_com_erro = 0

    for i, arquivo in enumerate(lista_arquivos_xml):
        try:
            tree = ET.parse(str(arquivo))
            root = tree.getroot()
            
            # Tenta encontrar tags de NF-e e CT-e
            inf_nfe = root.find('.//nfe:infNFe', NS_NFE)
            
            # --- LÓGICA DE BUSCA DO CT-e CORRIGIDA ---
            cte_element = root.find(f"{NS_CTE_FIND}CTe") # Busca <CTe> na raiz <cteProc>
            if cte_element is not None:
                inf_cte = cte_element.find(f"{NS_CTE_FIND}infCte")
            else:
                # Fallback para caso o root não seja <cteProc>
                inf_cte = root.find(f".//{NS_CTE_FIND}infCte")
            # --- FIM DA CORREÇÃO DE BUSCA ---

            # --- LÓGICA NF-e (SE ENCONTRAR <infNFe>) ---
            if inf_nfe is not None:
                chave_nfe = inf_nfe.attrib.get('Id', '').replace('NFe', '')
                if not chave_nfe or len(chave_nfe) != 44:
                    logging.warning(f"Chave NFe inválida/ausente no XML: {arquivo.name}. Chave='{chave_nfe}'. Pulando.")
                    arquivos_com_erro += 1
                    continue

                if chave_nfe in chaves_processadas:
                    logging.warning(f"XML DUPLICADO (mesma chave): {arquivo.name}. Pulando.")
                    window.write_event_value('-PROGRESS_UPDATE-', (i + 1, total_files)) 
                    continue
                chaves_processadas.add(chave_nfe)
                
                # [INÍCIO - Lógica NF-e existente]
                ide = inf_nfe.find('nfe:ide', NS_NFE)
                emit = inf_nfe.find('nfe:emit', NS_NFE)
                dest = inf_nfe.find('nfe:dest', NS_NFE)
                
                numero_nf = get_text_nfe(ide, 'nfe:nNF')
                
                fin_nfe_code = get_text_nfe(ide, 'nfe:finNFe', default='1')
                tipo_nota_texto = MAPA_FINNFE.get(fin_nfe_code, 'Desconhecido') 
                
                cnpj_emitente = get_text_nfe(emit, 'nfe:CNPJ', default=get_text_nfe(emit, 'nfe:CPF'))
                
                cnpj_dest = get_text_nfe(dest, 'nfe:CNPJ')
                cpf_dest = get_text_nfe(dest, 'nfe:CPF')
                
                tipo_dest = 'OUTRO'
                if cnpj_dest and cnpj_dest.isdigit() and len(cnpj_dest) >= 14:
                    tipo_dest = 'PJ'
                elif cpf_dest and cpf_dest.isdigit() and len(cpf_dest) >= 11:
                    tipo_dest = 'PF'
                
                icms_tot_element = root.find('.//nfe:ICMSTot', NS_NFE)
                dados_impostos: Dict[str, float] = {
                    'VL_DOC_XML': round(get_float_nfe(icms_tot_element, 'nfe:vNF'), 2),
                    'ICMS_XML': round(get_float_nfe(icms_tot_element, 'nfe:vICMS'), 2),
                    'ICMS_ST_XML': round(get_float_nfe(icms_tot_element, 'nfe:vST'), 2),
                    'IPI_XML': round(get_float_nfe(icms_tot_element, 'nfe:vIPI'), 2),
                    'IPI_DEVOL_XML': round(get_float_nfe(icms_tot_element, 'nfe:vIPIDevol'), 2),
                    'FCP_ST_XML': round(get_float_nfe(icms_tot_element, 'nfe:vFCPST'), 2),
                    'ICMS_SN_XML': 0.0,
                    'ICMS_MONO_XML': 0.0
                }
                    
                cfops_set: set[str] = set()
                cest_set: set[str] = set()
                icms_sn_total_itens: float = 0.0
                icms_mono_total_itens: float = 0.0
                
                itens_list = root.findall('.//nfe:det', NS_NFE)
                if not itens_list:
                    logging.warning(f"Nenhum item (<det>) encontrado no XML: {chave_nfe}. Pulando itens.")

                for item in itens_list:
                    prod = item.find('nfe:prod', NS_NFE)
                    imposto = item.find('nfe:imposto', NS_NFE)
                    if prod is None or imposto is None: continue 

                    cfop_text = get_text_nfe(prod, 'nfe:CFOP'); cfops_set.add(cfop_text)
                    cest_code = get_text_nfe(prod, 'nfe:CEST'); cest_set.add(cest_code)
                    
                    cst_icms_xml = ''; vlr_bc_icms_xml = 0.0; p_icms_xml = 0.0
                    vlr_icms_sn_item = 0.0
                    
                    icms_element = imposto.find('nfe:ICMS', NS_NFE)
                    if icms_element is not None:
                        icms_type_tag = next(iter(icms_element), None) 
                        if icms_type_tag is not None:
                            cst_icms_xml = get_text_nfe(icms_type_tag, 'nfe:CST', default=get_text_nfe(icms_type_tag, 'nfe:CSOSN'))
                            vlr_bc_icms_xml = get_float_nfe(icms_type_tag, 'nfe:vBC') 
                            p_icms_xml_raw = get_float_nfe(icms_type_tag, 'nfe:pICMS')
                            if p_icms_xml_raw > 0: p_icms_xml = round(p_icms_xml_raw / 100.0, 4)
                            vlr_icms_sn_item = get_float_nfe(icms_type_tag, 'nfe:vCredICMSSN')
                    
                    icms_sn_total_itens += vlr_icms_sn_item
                    
                    vlr_icms_mono_item = 0.0
                    vlr_icms_mono_item += get_float_nfe(imposto.find('.//nfe:vICMSMono', NS_NFE), '.')
                    vlr_icms_mono_item += get_float_nfe(imposto.find('.//nfe:vICMSMonoOp', NS_NFE), '.')
                    vlr_icms_mono_item += get_float_nfe(imposto.find('.//nfe:vICMSMonoDifer', NS_NFE), '.')
                    vlr_icms_mono_item += get_float_nfe(imposto.find('.//nfe:vICMSMonoRet', NS_NFE), '.')
                    icms_mono_total_itens += vlr_icms_mono_item
                            
                    vlr_unit_base = get_float_nfe(prod, 'nfe:vUnCom'); quantidade = get_float_nfe(prod, 'nfe:qCom'); vlr_frete_item = get_float_nfe(prod, 'nfe:vFrete'); vlr_seguro_item = get_float_nfe(prod, 'nfe:vSeg'); vlr_desconto_item = get_float_nfe(prod, 'nfe:vDesc'); vlr_outras_desp = get_float_nfe(prod, 'nfe:vOutro')
                    vlr_icms_item = get_float_nfe(imposto.find('.//nfe:vICMS', NS_NFE), '.'); vlr_icms_st_item = get_float_nfe(imposto.find('.//nfe:vICMSST', NS_NFE), '.'); vlr_fcp_st_item = get_float_nfe(imposto.find('.//nfe:vFCPST', NS_NFE), '.'); vlr_pis_item = get_float_nfe(imposto.find('.//nfe:vPIS', NS_NFE), '.'); vlr_cofins_item = get_float_nfe(imposto.find('.//nfe:vCOFINS', NS_NFE), '.')
                    
                    vlr_ipi_item = get_float_nfe(imposto.find('.//nfe:vIPI', NS_NFE), '.')
                    imposto_devol = item.find('nfe:impostoDevol', NS_NFE) 
                    vlr_ipi_devolvido_item = 0.0
                    if imposto_devol is not None:
                        vlr_ipi_devolvido_item = get_float_nfe(imposto_devol, 'nfe:IPI/nfe:vIPIDevol')
                    vlr_ipi_item = vlr_ipi_item + vlr_ipi_devolvido_item
                    
                    vlr_prod_base = get_float_nfe(prod, 'nfe:vProd')

                    vlr_prod_calculado = round(vlr_prod_base + vlr_ipi_item + vlr_icms_st_item + vlr_fcp_st_item + vlr_frete_item + vlr_seguro_item - vlr_desconto_item + vlr_outras_desp, 2)
                    
                    icms_a_deduzir = 0.0
                    if vlr_icms_mono_item == 0.0:
                        icms_a_deduzir = round(vlr_icms_item, 2) + round(vlr_icms_sn_item, 2)
                    
                    bc_pis_cofins_item = round(
                        vlr_prod_calculado - 
                        icms_a_deduzir - 
                        round(vlr_icms_st_item, 2) - 
                        round(vlr_fcp_st_item, 2) - 
                        round(vlr_ipi_item, 2), 
                    2)

                    item_data: Dict[str, Any] = {
                        'CHV_NFE': chave_nfe, 'CNPJ_EMITENTE': cnpj_emitente, 'N_ITEM': item.attrib.get('nItem', ''), 
                        'TIPO_NOTA': tipo_nota_texto,
                        'TIPO_DESTINATARIO': tipo_dest,
                        'COD_PROD': get_text_nfe(prod, 'nfe:cProd'), 'DESC_PROD': get_text_nfe(prod, 'nfe:xProd'), 
                        'NCM': get_text_nfe(prod, 'nfe:NCM'), 
                        'CEST': cest_code,
                        'cBenef': get_text_nfe(prod, 'nfe:cBenef'), 
                        'CFOP': cfop_text, 
                        'QTD': quantidade, 
                        'UNID': get_text_nfe(prod, 'nfe:uCom'), 
                        'VLR_UNIT': vlr_unit_base, 
                        'VLR_PROD': vlr_prod_calculado, 
                        'DESPESA_XML': round(vlr_outras_desp, 2),
                        'VLR_ICMS': round(vlr_icms_item, 2), 
                        'VLR_ICMS_ST': round(vlr_icms_st_item, 2), 
                        'VLR_FCP_ST': round(vlr_fcp_st_item, 2), 
                        'VLR_IPI': round(vlr_ipi_item, 2), 
                        'VLR_PIS': round(vlr_pis_item, 2), 
                        'VLR_COFINS': round(vlr_cofins_item, 2), 
                        'VLR_ICMS_SN': round(vlr_icms_sn_item, 2),
                        'VLR_ICMS_MONO': round(vlr_icms_mono_item, 2), 
                        'BC_PIS_COFINS_CALC': bc_pis_cofins_item if bc_pis_cofins_item > 0 else 0.0, 
                        'VLR_TOTAL_NF': dados_impostos['VL_DOC_XML'],
                        'CST_ICMS_XML': cst_icms_xml, 
                        'VLR_BC_ICMS_XML': round(vlr_bc_icms_xml, 2),
                        'pICMS_XML': p_icms_xml
                    }
                    dados_itens.append(item_data)
                    
                dados_impostos['ICMS_SN_XML'] = round(icms_sn_total_itens, 2)
                dados_impostos['ICMS_MONO_XML'] = round(icms_mono_total_itens, 2)

                linha_completa: Dict[str, Any] = {
                    'CHV_NFE': chave_nfe, 
                    'NUM_NF': numero_nf,
                    'CNPJ_EMITENTE': cnpj_emitente,
                    'CFOP_XML': '/'.join(sorted(list(filter(None, cfops_set)))) if cfops_set else '',
                    'CEST_XML': '/'.join(sorted(list(filter(None, cest_set)))) if cest_set else '',
                    'TIPO_NOTA': tipo_nota_texto
                }
                linha_completa.update(dados_impostos)
                dados_totais.append(linha_completa)
                # [FIM - Lógica NF-e existente]
                
            # --- LÓGICA CT-e (SE ENCONTRAR <infCte>) ---
            elif inf_cte is not None:
                try:
                    chave_cte = inf_cte.attrib.get('Id', '').replace('CTe', '')
                    if not chave_cte or len(chave_cte) != 44:
                        logging.warning(f"Chave CTe inválida/ausente no XML: {arquivo.name}. Chave='{chave_cte}'. Pulando.")
                        arquivos_com_erro += 1
                        continue
                    
                    if chave_cte in chaves_processadas:
                        logging.warning(f"XML DUPLICADO (mesma chave): {arquivo.name}. Pulando.")
                        window.write_event_value('-PROGRESS_UPDATE-', (i + 1, total_files)) 
                        continue
                    chaves_processadas.add(chave_cte)

                    # --- LÓGICA DE BUSCA CT-e CORRIGIDA ---
                    # Navega pela estrutura do CT-e
                    ide = inf_cte.find(f"{NS_CTE_FIND}ide")
                    vPrest = inf_cte.find(f"{NS_CTE_FIND}vPrest")
                    imp = inf_cte.find(f"{NS_CTE_FIND}imp")
                    
                    icms_element = imp.find(f"{NS_CTE_FIND}ICMS") if imp is not None else None
                    icms_type_tag = next(iter(icms_element), None) if icms_element is not None else None # Pega o primeiro filho (ex: <ICMS00>)

                    # Extrai os dados totais do CT-e
                    
                    # --- MODIFICAÇÃO AQUI (LINHA 146) ---
                    num_cte_xml = get_text_cte(ide, 'nCT') # Pega o Número do CT-e
                    # --- FIM DA MODIFICAÇÃO ---
                    
                    cfop_xml = get_text_cte(ide, 'CFOP')
                    vlr_opr_xml = get_float_cte(vPrest, 'vTPrest')
                    
                    vlr_bc_xml = get_float_cte(icms_type_tag, 'vBC')
                    vlr_icms_xml = get_float_cte(icms_type_tag, 'vICMS')
                    cst_xml = get_text_cte(icms_type_tag, 'CST')
                    nat_cte = get_text_cte(ide, 'natOp')
                    # --- FIM DA LÓGICA DE BUSCA ---

                    # Adiciona à nova lista de CT-e
                    dados_cte_xml.append({
                        'CHV_CTE': chave_cte,
                        
                        # --- MODIFICAÇÃO AQUI (LINHA 161) ---
                        'NUM_CTE_XML': num_cte_xml, # Adiciona o número ao dicionário
                        # --- FIM DA MODIFICAÇÃO ---
                        
                        'CFOP_XML': cfop_xml,
                        'CST_XML': cst_xml,
                        'VL_OPR_XML': round(vlr_opr_xml, 2),
                        'VL_BC_ICMS_XML': round(vlr_bc_xml, 2),
                        'VL_ICMS_XML': round(vlr_icms_xml, 2)
                    })
                    logging.info(f"Processado CT-e: {chave_cte}")

                except Exception as e_cte:
                    logging.warning(f"Erro ao processar dados do CT-e {arquivo.name}: {e_cte}")
                    arquivos_com_erro += 1
                    continue
            
            # --- SE NÃO FOR NF-e NEM CT-e ---
            else:
                tag_name = root.tag.split('}')[-1] if '}' in root.tag else root.tag
                if tag_name not in ['cteProc', 'CteProc', 'nfeProc']: # Evita logar os 'envelopes'
                    logging.warning(f"XML não reconhecido (sem <infNFe> ou <infCte>): {arquivo.name}. Tag raiz: {tag_name}")
                # Não conta como erro, pode ser um XML de evento (CCE, etc.)
                continue
            
        except ET.ParseError: 
            logging.warning(f"Ignorando XML mal formatado: {arquivo.name}"); 
            window.write_event_value('-XML_PARSE_ERROR-', arquivo.name); 
            arquivos_com_erro += 1
            continue
        except Exception as e: 
            logging.error(f"Erro inesperado ao processar o XML {arquivo.name}: {e}"); 
            arquivos_com_erro += 1
            continue
        
        window.write_event_value('-PROGRESS_UPDATE-', (i + 1, total_files))

    if not dados_totais and not dados_cte_xml: 
        logging.warning("Nenhum XML de NF-e ou CT-e válido foi processado.")
    
    if arquivos_com_erro > 0:
        logging.warning(f"{arquivos_com_erro} de {total_files} arquivos XML não puderam ser processados.")

    logging.info("Processamento de XMLs (NF-e e CT-e) concluído.")
    df_totais = pd.DataFrame(dados_totais)
    df_itens = pd.DataFrame(dados_itens) 
    df_cte_xml = pd.DataFrame(dados_cte_xml) # NOVO

    if not df_totais.empty:
        df_totais.drop_duplicates(subset=['CHV_NFE'], keep='first', inplace=True)
    if not df_itens.empty:
        df_itens.drop_duplicates(subset=['CHV_NFE', 'N_ITEM'], keep='first', inplace=True)
    if not df_cte_xml.empty: # NOVO
        df_cte_xml.drop_duplicates(subset=['CHV_CTE'], keep='first', inplace=True)
    
    # EM VEZ DE USAR GLOBAL, RETORNAMOS OS TRÊS
    return df_totais, df_itens, df_cte_xml