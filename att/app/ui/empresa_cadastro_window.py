# att/app/ui/empresa_cadastro_window.py (MODIFICADO com as regras selecionadas)

import FreeSimpleGUI as sg
import sys
from typing import TYPE_CHECKING, Any, Optional

# --- Importa a lógica e o ConfigLoader ---
try:
    from app import empresa_logic
    from app.config import ConfigLoader
except (ModuleNotFoundError, ImportError):
    print("Aviso: Importando 'empresa_logic' ou 'ConfigLoader' de forma não padrão.")
    try:
        import empresa_logic # type: ignore
        from config import ConfigLoader # type: ignore
    except ImportError:
        sg.popup_error("Erro fatal: Não foi possível carregar 'empresa_logic' ou 'ConfigLoader'.")
        sys.exit(1)

if TYPE_CHECKING:
    from app.config import ConfigLoader


def atualizar_tabela(window: sg.Window, config: 'ConfigLoader', search_term: str = ""):
    """Busca os dados no banco (com filtro) e atualiza a tabela na tela."""
    try:
        empresas_list = empresa_logic.listar_todas_empresas(config.db_empresas_path, search_term) 
        window['-TABELA_EMPRESAS-'].update(values=empresas_list) 
    except Exception as e:
        sg.popup_error(f"Erro ao carregar empresas:\n{e}")

def limpar_e_resetar_form(window: sg.Window):
    """Limpa os campos de input, checkboxes e reseta os botões para 'novo cadastro'."""
    window['-CNPJ-'].update('', disabled=False) 
    window['-RAZAO-'].update('')
    
    # Limpa regras mantidas
    window['-REGRA_IGNORAR_CANCELADAS-'].update(False)
    
    # --- LIMPAR NOVAS REGRAS (MANTIDAS) ---
    window['-REGRA_SIMPLES_NACIONAL-'].update(False)
    window['-REGRA_TOLERANCIA_ZERO-'].update(False)
    window['-REGRA_SEM_C170-'].update(False)
    window['-REGRA_IGNORAR_ICMS-'].update(False)
    window['-REGRA_EXIGIR_ACUMULADOR-'].update(False)
    
    window['-SALVAR-'].update('Salvar Empresa') 
    window['-EXCLUIR-'].update(disabled=True)    
    window['-TABELA_EMPRESAS-'].update(select_rows=[]) 
    
    window['-CNPJ-'].set_focus()


def carregar_empresa_para_edicao(window: sg.Window, config: 'ConfigLoader', cnpj: str, razao: str):
    """Busca regras da empresa e preenche o formulário para edição."""
    try:
        regras_dict = empresa_logic.obter_regras_empresa(config.db_empresas_path, cnpj) or {}
        
        window['-CNPJ-'].update(cnpj, disabled=True) 
        window['-RAZAO-'].update(razao)
        
        # Carrega regras mantidas
        window['-REGRA_IGNORAR_CANCELADAS-'].update(regras_dict.get('ignorar_canceladas', False))
        
        # --- CARREGAR NOVAS REGRAS (MANTIDAS) ---
        window['-REGRA_SIMPLES_NACIONAL-'].update(regras_dict.get('nao_calcular_pis_cofins', False))
        window['-REGRA_TOLERANCIA_ZERO-'].update(regras_dict.get('usar_tolerancia_zero', False))
        window['-REGRA_SEM_C170-'].update(regras_dict.get('sped_sem_c170_nfe', False))
        window['-REGRA_IGNORAR_ICMS-'].update(regras_dict.get('ignorar_validacao_icms', False))
        window['-REGRA_EXIGIR_ACUMULADOR-'].update(regras_dict.get('exigir_acumulador', False))
        
        window['-SALVAR-'].update('Atualizar Empresa')
        window['-EXCLUIR-'].update(disabled=False) 

    except Exception as e:
        sg.popup_error(f"Erro ao carregar dados da empresa '{cnpj}':\n{e}")
        limpar_e_resetar_form(window)


def create_window(config: 'ConfigLoader'):
    try:
        theme = config.theme_name
        font_family = config.font_family
        sg.theme(theme)
    except Exception:
        sg.theme('DarkBlue') 
        font_family = 'Segoe UI'

    font_std = (font_family, 10)
    font_bold = (font_family, 11, 'bold')
    font_frame = (font_family, 12, 'bold')

    # --- LAYOUT DE REGRAS ATUALIZADO (SOMENTE MARCADAS) ---
    layout_regras_automacao = [
        [sg.Checkbox('Ignorar Notas Fiscais Canceladas?', key='-REGRA_IGNORAR_CANCELADAS-', font=font_std)],
    ]

    layout_regras_analisador = [
        [sg.Checkbox('Não calcular PIS/COFINS (Simples Nacional)?', key='-REGRA_SIMPLES_NACIONAL-', font=font_std,
                     tooltip='Pula a validação de PIS/COFINS para este CNPJ.')],
        [sg.Checkbox('Usar Tolerância Zero (Valores Exatos)?', key='-REGRA_TOLERANCIA_ZERO-', font=font_std,
                     tooltip='Valida impostos e totais com R$ 0,00 de tolerância.')],
        [sg.Checkbox('SPED não escritura C170 (Ignorar Itens)?', key='-REGRA_SEM_C170-', font=font_std,
                     tooltip='Pula a validação de CFOP item a item (C170 vs <det>).')],
        [sg.Checkbox('Desativar validação de crédito de ICMS?', key='-REGRA_IGNORAR_ICMS-', font=font_std,
                     tooltip='Desativa completamente a verificação de STATUS_ICMS.')],
        [sg.Checkbox('Exigir Acumulador (Forçar "Revisar")?', key='-REGRA_EXIGIR_ACUMULADOR-', font=font_std,
                     tooltip='Se um acumulador não for encontrado, força o STATUS_GERAL da nota para "REVISAR".')],
    ]
    # --- FIM DA ATUALIZAÇÃO DO LAYOUT ---
    
    layout_cadastro = [
        [sg.Text('CNPJ:', size=(10, 1), font=font_std), sg.Input(key='-CNPJ-', size=(20, 1), font=font_std)],
        [sg.Text('Razão Social:', size=(10, 1), font=font_std), sg.Input(key='-RAZAO-', size=(40, 1), font=font_std)],
        [sg.HSeparator()],
        # --- SEPARADO EM DOIS FRAMES ---
        [sg.Frame('Regras de Automação', layout_regras_automacao, font=font_frame)],
        [sg.Frame('Regras do Analisador Fiscal (Geral)', layout_regras_analisador, font=font_frame)],
        [sg.Button('Salvar Empresa', key='-SALVAR-', font=font_std), 
         sg.Button('Limpar Campos', key='-LIMPAR-', font=font_std)]
    ]
    
    layout_lista_empresas = [
        [sg.Text('Buscar (CNPJ ou Razão):', font=font_std), 
         sg.Input(key='-BUSCA-', expand_x=True, enable_events=True, font=font_std),
         sg.Button('Buscar', key='-BUSCAR-', font=font_std),
         sg.Button('Limpar', key='-LIMPAR_BUSCA-', font=font_std)],
        [sg.Table(
            values=[], headings=['CNPJ', 'Razão Social'], key='-TABELA_EMPRESAS-',
            display_row_numbers=False, auto_size_columns=False, col_widths=[18, 40],
            justification='left', expand_x=True, expand_y=True, font=font_std,
            enable_events=True, 
            select_mode=sg.TABLE_SELECT_MODE_BROWSE 
        )],
        [sg.Push(), 
         sg.Button('Atualizar Lista', key='-ATUALIZAR-', font=font_std), 
         sg.Button('Excluir Selecionada', key='-EXCLUIR-', font=font_std, 
                   button_color=('white', '#DC3545'), disabled=True)] 
    ]

    layout = [
        [sg.Frame('Cadastrar/Editar Empresa', layout_cadastro, vertical_alignment='top', font=font_bold),
         sg.Frame('Empresas Salvas', layout_lista_empresas, expand_x=True, expand_y=True, font=font_bold)]
    ]

    # Ajustei a altura da janela para o novo layout
    window = sg.Window('Gestão de Empresas e Regras', layout, resizable=True, finalize=True, modal=True,
                       icon=config.app_icon_path, size=(800, 500)) 
    
    try:
        empresa_logic.inicializar_banco(config.db_empresas_path)
    except Exception as e:
         sg.popup_error(f"Erro CRÍTICO ao inicializar banco de dados de empresas:\n{e}", title="Erro DB")
         window.close() 
         return None 

    return window

def main(config: 'ConfigLoader'): 
    window = create_window(config)
    
    if window is None: 
        return

    atualizar_tabela(window, config)
    selected_cnpj: Optional[str] = None 

    while True:
        event, values = window.read()
        
        if event == sg.WIN_CLOSED:
            break
            
        if event == '-SALVAR-':
            cnpj = values['-CNPJ-'] 
            razao = values['-RAZAO-']
            
            if not cnpj or not razao:
                sg.popup_error('Erro: CNPJ e Razão Social são obrigatórios.')
                continue

            # --- DICIONÁRIO DE REGRAS ATUALIZADO (SOMENTE MARCADAS) ---
            regras_dict = {
                # Regra de Automação Mantida
                'ignorar_canceladas': values['-REGRA_IGNORAR_CANCELADAS-'],
                
                # Novas Regras (Analisador Fiscal) Mantidas
                'nao_calcular_pis_cofins': values['-REGRA_SIMPLES_NACIONAL-'],
                'usar_tolerancia_zero': values['-REGRA_TOLERANCIA_ZERO-'],
                'sped_sem_c170_nfe': values['-REGRA_SEM_C170-'],
                'ignorar_validacao_icms': values['-REGRA_IGNORAR_ICMS-'],
                'exigir_acumulador': values['-REGRA_EXIGIR_ACUMULADOR-'],
                
                # --- REGRAS REMOVIDAS ---
                # 'aproveitar_icms': False, 
                # 'regime_presumido_pis_cofins': False,
                # 'excluir_frete_base_pis_cofins': False,
            }
            # --- FIM DA ATUALIZAÇÃO ---
            
            try:
                empresa_logic.salvar_empresa(config.db_empresas_path, cnpj, razao, regras_dict) 
                
                msg = 'Empresa atualizada com sucesso.' if selected_cnpj else 'Empresa salva com sucesso.'
                sg.popup('Sucesso!', msg)
                
                selected_cnpj = None 
                limpar_e_resetar_form(window)
                atualizar_tabela(window, config, values['-BUSCA-']) 
            except Exception as e:
                sg.popup_error(f'Erro ao salvar no banco:\n{e}')

        if event == '-TABELA_EMPRESAS-':
            selected_indices = values['-TABELA_EMPRESAS-']
            if selected_indices:
                try:
                    selected_row_index = selected_indices[0]
                    table_data = window['-TABELA_EMPRESAS-'].Values 
                    selected_row = table_data[selected_row_index]
                    cnpj, razao = selected_row[0], selected_row[1]
                    
                    selected_cnpj = cnpj 
                    carregar_empresa_para_edicao(window, config, cnpj, razao)
                except IndexError:
                    print("Erro de índice ao selecionar linha. Tabela pode estar vazia ou atualizando.")
                    selected_cnpj = None
                    limpar_e_resetar_form(window)
                except Exception as e:
                     sg.popup_error(f"Erro ao carregar empresa: {e}")
                     selected_cnpj = None
                     limpar_e_resetar_form(window)

        if event == '-EXCLUIR-':
            if not selected_cnpj:
                sg.popup_error("Nenhuma empresa selecionada para exclusão.")
                continue
                
            if sg.popup_yes_no(f"Tem certeza que deseja EXCLUIR a empresa:\n\nCNPJ: {selected_cnpj}\n\nEsta ação não pode ser desfeita.", title="Confirmar Exclusão") == 'Yes':
                try:
                    empresa_logic.delete_empresa(config.db_empresas_path, selected_cnpj)
                    sg.popup_ok("Empresa excluída com sucesso.")
                    selected_cnpj = None
                    limpar_e_resetar_form(window)
                    atualizar_tabela(window, config, values['-BUSCA-']) 
                except Exception as e:
                    sg.popup_error(f"Erro ao excluir empresa:\n{e}")

        if event == '-BUSCAR-' or (event == '-BUSCA-' and values['-BUSCA-']): 
            search_term = values['-BUSCA-']
            atualizar_tabela(window, config, search_term)

        if event == '-LIMPAR_BUSCA-':
            window['-BUSCA-'].update('')
            atualizar_tabela(window, config) 

        if event == '-LIMPAR-':
            selected_cnpj = None 
            limpar_e_resetar_form(window)

        if event == '-ATUALIZAR-':
            atualizar_tabela(window, config, values['-BUSCA-']) 

    window.close()

