import logging
import time
import os
import shutil
import traceback
import json
import requests  # <-- Biblioteca nova!
import locale
from pathlib import Path
from datetime import date
from typing import Tuple, List, Callable, Dict, Optional, Any

# Importações do Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys # <-- IMPORTADO
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains 

# ==============================================================================
# --- CONSTANTES GLOBAIS (SELÉNIO) ---
# ==============================================================================
URL_LOGIN = "https://notafiscal.linhares.es.gov.br/#/login"
URL_SELECAO_CONTRIBUINTE = "https://notafiscal.linhares.es.gov.br/#/selecaoEmpresa"
URL_CONSULTA_NFSE = "https://notafiscal.linhares.es.gov.br/#/consultaNfse"
TIMEOUT_PRINCIPAL = 25 
TIMEOUT_DOWNLOAD_API = 180
TIMEOUT_CURTO = 10 

LOC_CONSULTA_HEADER = (By.XPATH, "//*[contains(text(), 'Consulta e gerenciamento')]")
LOC_DATA_INI_INPUT = (By.XPATH, "//input[@placeholder='Data Inicial']")
LOC_DATA_FIM_INPUT = (By.XPATH, "//input[@placeholder='Data Final']")
LOC_PESQUISAR_BUTTON = (By.XPATH, "//button/span[text()='Pesquisar']/..") 
LOC_LOADING_SPINNER = (By.CSS_SELECTOR, "div.p-datatable-loading-overlay")
LOC_SEM_RESULTADO = (By.XPATH, "//td[contains(text(), 'Nenhum resultado encontrado')]")


# ==============================================================================
# --- CONSTANTES GLOBAIS (API - NOSSAS DESCOBERTAS) ---
# ==============================================================================
API_BASE_URL = "https://notafiscal.linhares.es.gov.br/producao/api"
API_URL_PDF = f"{API_BASE_URL}/relatorio/export"
API_URL_XML = f"{API_BASE_URL}/report/exportarNfCompleto"
API_URL_FIND_CONTRIBUINTES = f"{API_BASE_URL}/contribuinte/findAllContribuintes"
API_URL_SELECIONAR_CONTRIBUINTE = f"{API_BASE_URL}/contribuinte/selecionarContribuinte"


# ==============================================================================
# --- [FUNÇÕES DO SELENIUM (SETUP INICIAL COMPLETO - V4.3)] ---
# ==============================================================================

def setup_driver(download_path: str) -> webdriver.Chrome:
    """Configura e inicia o driver do Chrome."""
    logging.info(">>> Configurando o driver do Chrome (apenas para login)...")
    options = webdriver.ChromeOptions()
    prefs = {"download.default_directory": download_path} 
    options.add_experimental_option("prefs", prefs)
    # options.add_argument("--headless") 

    try:
        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logging.error(f"Falha ao instalar/iniciar o ChromeDriver: {e}")
        raise
    driver.maximize_window()
    return driver

def login_selenium(driver: webdriver.Chrome, wait: WebDriverWait, user: str, password: str) -> bool:
    """(DO SEU CÓDIGO ANTIGO) Executa o login no portal."""
    logging.info("1. Realizando login (via Selenium)...")
    try:
        driver.get(URL_LOGIN)
        wait.until(EC.visibility_of_element_located((By.ID, "usuario"))).send_keys(user)
        
        logging.info("       - Digitindo senha...")
        pass_element = driver.find_element(By.ID, "senha")
        pass_element.click()
        pass_element.clear()
        
        for char in password:
            pass_element.send_keys(char)
            time.sleep(0.1) 
        
        logging.info("       - Senha digitada.")
        driver.find_element(By.XPATH, "//button[normalize-space()='Entrar']").click()

        failure_locator = (By.CLASS_NAME, "p-toast-message-content")    
        
        WebDriverWait(driver, TIMEOUT_PRINCIPAL).until(EC.any_of(
            EC.url_to_be(URL_SELECAO_CONTRIBUINTE),
            EC.visibility_of_element_located(failure_locator)
        ))

        if not driver.current_url.endswith(URL_SELECAO_CONTRIBUINTE):
            try:
                error_message = driver.find_element(*failure_locator).text
            except:
                error_message = "Erro de login desconhecido"
            logging.error(f"       - ERRO DE LOGIN: {error_message}")
            raise Exception(f"Login falhou: {error_message}")

        logging.info("       - Login realizado com sucesso!")
        return True
        
    except Exception as e:
        logging.error(f"       - ERRO CRÍTICO no login: {e}")
        driver.save_screenshot("ERRO_CRITICO_LOGIN.png")
        raise 

# [FUNÇÃO CORRIGIDA V4.3 - USANDO A SUA LÓGICA DE 'ENTER']
def selecionar_contribuinte_selenium(driver: webdriver.Chrome, wait: WebDriverWait, cnpj_numeros: str, cnpj_formatado: str) -> bool:
    """
    (V4.3 - Baseado no seu código antigo + imagens + CORREÇÃO DO 'ENTER')
    Busca e seleciona o contribuinte na lista.
    """
    logging.info(f"2. Selecionando 1º contribuinte (via Selenium) para gerar token: {cnpj_formatado}")

    if not driver.current_url.endswith(URL_SELECAO_CONTRIBUINTE):
        logging.info("     - Navegando de volta para a Seleção de Empresa...")
        driver.get(URL_SELECAO_CONTRIBUINTE)
        wait.until(EC.url_to_be(URL_SELECAO_CONTRIBUINTE)) 

    loader_locator = (By.CSS_SELECTOR, "div.p-datatable-loading-overlay")
    pesquisar_button_locator = (By.XPATH, "//button[.//span[text()='Pesquisar']]")
    campo_busca_locator = (By.XPATH, "//input[@placeholder='Filtro']")
    campo_busca = None

    try:
        wait.until(EC.visibility_of_element_located((By.XPATH, "//div[contains(text(), 'Lista de Contribuintes')]")))
        time.sleep(1) 

        logging.info("     - Localizando campo 'Filtro'...")
        campo_busca = wait.until(EC.element_to_be_clickable(campo_busca_locator))

        campo_busca.clear()
        campo_busca.send_keys(cnpj_formatado)
        logging.info(f"     - CNPJ {cnpj_formatado} digitado.")
        time.sleep(0.5) 

        # [--- A CORREÇÃO (V4.3) - FAZENDO COMO O SEU CÓDIGO ANTIGO ---]
        logging.info("     - Enviando 'ENTER' para filtrar...")
        campo_busca.send_keys(Keys.RETURN)
        logging.info("     - Acionando a pesquisa (clique)...")
        # [--- FIM DA CORREÇÃO ---]
        
        pesquisar_button = wait.until(EC.element_to_be_clickable(pesquisar_button_locator))
        pesquisar_button.click()
        logging.info("     - Clique de pesquisa enviado.")

        try:
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located(loader_locator))
            logging.info("     - Loader detectado. Aguardando busca finalizar...")
        except TimeoutException:
            logging.warning("     - Aviso: Loader não foi detectado rapidamente.")

        wait.until(EC.invisibility_of_element_located(loader_locator))
        logging.info("     - Busca finalizada (loader desapareceu).")
        time.sleep(0.5)

        selecionar_button_xpath = (
            f"//tr[.//td[contains(., '{cnpj_formatado}')]]" 
            f"//button[contains(@class, 'p-button-icon-only') and .//span[contains(@class, 'pi-check')]]"
        )

        logging.info("     - Tentando clicar no botão 'Selecionar' (check)...")
        try:
            botao_selecionar = wait.until(EC.element_to_be_clickable((By.XPATH, selecionar_button_xpath)))
            botao_selecionar.click()
        except Exception as e:
            logging.warning(f"     - Clique normal falhou ({e}). Tentando clique forçado via JS...")
            botao_selecionar = wait.until(EC.presence_of_element_located((By.XPATH, selecionar_button_xpath)))
            driver.execute_script("arguments[0].click();", botao_selecionar)

        logging.info("     - Comando de clique enviado.")
        
        wait.until(lambda d: d.current_url != URL_SELECAO_CONTRIBUINTE)
        
        logging.info(f"     - Navegação detectada (URL: {driver.current_url}). Seleção concluída.")
        return True

    except Exception as e:
        logging.error(f"     - ERRO CRÍTICO ao tentar selecionar o CNPJ {cnpj_formatado}: {e}")
        logging.error(traceback.format_exc()) 
        driver.save_screenshot(f"ERRO_CRITICO_SELECAO_{cnpj_numeros}.png")
        return False

def navegar_para_consulta_selenium(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """Navega pelos menus até a tela de consulta de notas."""
    logging.info("3. Forçando navegação para a tela de consulta...")
    try:
        menu_nota_fiscal = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'nav-link') and normalize-space(.)='Nota Fiscal']")))
        driver.execute_script("arguments[0].click();", menu_nota_fiscal)
        time.sleep(0.5)
        
        submenu_consulta = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'dropdown-item') and @href='#/consultaNfse']")))
        driver.execute_script("arguments[0].click();", submenu_consulta)
        
        wait.until(EC.visibility_of_element_located(LOC_CONSULTA_HEADER))
        wait.until(EC.url_contains(URL_CONSULTA_NFSE))
        logging.info("     - Navegação para Consulta concluída.")
        return True
    except TimeoutException:
        logging.error("     - ERRO: Não foi possível encontrar o link para a página de Consulta.")
        return False

def force_set_date_selenium(driver: webdriver.Chrome, locator: Tuple[str, str], date_value: str) -> None:
    """Força a inserção de data em campos de calendário usando JavaScript."""
    try:
        date_element = WebDriverWait(driver, TIMEOUT_PRINCIPAL).until(EC.presence_of_element_located(locator))
        driver.execute_script(
            "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'));",
            date_element, date_value
        )
    except TimeoutException:
        logging.error(f"     - ERRO: Não foi possível encontrar o campo de data: {locator}")
        raise

def fill_dates_and_search_selenium(driver: webdriver.Chrome, wait: WebDriverWait, data_inicio_gui: str, data_fim_gui: str) -> bool:
    """Preenche as datas e pesquisa (apenas para o setup)."""
    logging.info("4. Preenchendo período (para gerar token)...")
    try:
        wait.until(EC.visibility_of_element_located(LOC_CONSULTA_HEADER))
        
        force_set_date_selenium(driver, LOC_DATA_INI_INPUT, data_inicio_gui)
        force_set_date_selenium(driver, LOC_DATA_FIM_INPUT, data_fim_gui)
        time.sleep(0.5) 

        logging.info("     - Clicando em Pesquisar...")
        # [V4.3] - Corrigido para o seletor de botão de pesquisa da página de consulta (span)
        pesquisar_button_locator = (By.XPATH, "//button/span[text()='Pesquisar']")
        pesquisar_button = wait.until(EC.element_to_be_clickable(pesquisar_button_locator))
        driver.execute_script("arguments[0].click();", pesquisar_button)

        logging.info("     - Aguardando a atualização da tabela de resultados...")
        try:
            WebDriverWait(driver, TIMEOUT_CURTO).until(EC.visibility_of_element_located(LOC_LOADING_SPINNER))
        except TimeoutException:
            logging.warning("     - AVISO: Animação de 'loading' não foi detectada.")
            
        wait.until(EC.invisibility_of_element_located(LOC_LOADING_SPINNER))
        
        wait.until(EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//td[contains(@class, 'p-element')]")), 
            EC.presence_of_element_located(LOC_SEM_RESULTADO)
        ))
        logging.info("     - Pesquisa concluída. Tokens agora devem estar 100% gerados.")
        return True
    except Exception as e:
        logging.error(f"     - ERRO ao preencher datas e pesquisar (setup): {e}")
        return False

# --- Funções de Extração ---
def _extrair_token_bearer(driver: WebDriver) -> Optional[str]:
    """ Vasculha o Local Storage em busca do Token Bearer. """
    logging.info("     - Procurando Token 'Bearer' no Local Storage (aguardando até 5s)...")
    try:
        for _ in range(5): 
            storage = driver.execute_script("return window.localStorage;")
            for key, value in storage.items():
                if value and isinstance(value, str) and value.startswith("ey"):
                    logging.info(f"     - Token encontrado na chave: '{key}'")
                    return value
            time.sleep(1) 
    except Exception as e:
        logging.error(f"     - Erro ao tentar ler o Local Storage: {e}")
    
    logging.error("     - ERRO: Token Bearer (iniciado com 'ey') não encontrado no Local Storage.")
    return None

def _extrair_id_cliente(driver: WebDriver) -> Optional[str]:
    """ Vasculha o Session Storage em busca do 'idCliente'. """
    logging.info("     - Procurando idCliente no Session Storage (aguardando até 5s)...")
    try:
        for _ in range(5): 
            storage = driver.execute_script("return window.sessionStorage;")
            if "currentUser" in storage:
                try:
                    user_data = json.loads(storage["currentUser"])
                    id_cliente = user_data.get("usuario", {}).get("idCliente")
                    if id_cliente:
                        logging.info(f"     - idCliente encontrado: {id_cliente}")
                        return id_cliente
                except Exception as e:
                    logging.warning(f"     - Falha ao ler 'currentUser' (JSON): {e}")
            time.sleep(1) 
    except Exception as e:
        logging.error(f"     - Erro ao tentar ler o Session Storage: {e}")
    
    logging.error("     - ERRO: idCliente não encontrado no Session Storage.")
    return None


# ==============================================================================
# --- [FUNÇÕES 100% API (NOVAS)] ---
# ==============================================================================

def _get_contribuinte_id_map(session: requests.Session, lista_de_cnpjs_formatados: List[str]) -> Dict[str, str]:
    """
    [NOVO] Busca o ID interno de cada CNPJ usando a API.
    """
    logging.info(f"     - [API] Buscando IDs internos para {len(lista_de_cnpjs_formatados)} CNPJ(s)...")
    mapa_cnpj_id = {}
    
    cnpjs_apenas_numeros = {}
    for cnpj_fmt in lista_de_cnpjs_formatados:
        numeros = "".join(filter(str.isdigit, cnpj_fmt))
        cnpjs_apenas_numeros[numeros] = cnpj_fmt

    try:
        response = session.get(API_URL_FIND_CONTRIBUINTES, params={"filtro": "null"}, timeout=30)
        response.raise_for_status()
        contribuintes = response.json() 
        
        if not isinstance(contribuintes, list):
            logging.error(f"     - ERRO: API de contribuintes não retornou uma lista. Retornou: {type(contribuintes)}")
            return {}

        for cont in contribuintes:
            doc = cont.get("cpfCnpj")
            id_cont = cont.get("id")
            if doc and id_cont:
                if doc in cnpjs_apenas_numeros:
                    cnpj_formatado = cnpjs_apenas_numeros[doc]
                    mapa_cnpj_id[cnpj_formatado] = str(id_cont)
        
        logging.info(f"     - [API] Mapeamento concluído. {len(mapa_cnpj_id)} IDs encontrados.")
        
        for cnpj_fmt in lista_de_cnpjs_formatados:
            if cnpj_fmt not in mapa_cnpj_id:
                logging.warning(f"     - AVISO: O CNPJ {cnpj_fmt} não foi encontrado na lista de contribuintes da API.")

        return mapa_cnpj_id

    except requests.exceptions.RequestException as e:
        logging.error(f"     - ERRO CRÍTICO ao buscar lista de contribuintes: {e}")
        if e.response:
            logging.error(f"     - Resposta: {e.response.text[:200]}")
        raise Exception("Falha ao buscar lista de contribuintes da API.") from e


def _api_selecionar_contribuinte(session: requests.Session, id_cliente: str, id_contribuinte: str) -> bool:
    """
    [NOVO] Avisa o servidor qual contribuinte estamos "olhando" via API.
    """
    logging.info(f"     - [API] Selecionando contribuinte ID: {id_contribuinte}")
    try:
        params = {
            "sUsuario": id_cliente,
            "sIdContribuinte": id_contribuinte
        }
        response = session.post(API_URL_SELECIONAR_CONTRIBUINTE, params=params, timeout=30)
        response.raise_for_status()
        logging.info("     - [API] Contribuinte selecionado no servidor.")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"     - ERRO API (selecionarContribuinte): {e}")
        if e.response:
            logging.error(f"     - Resposta: {e.response.text[:200]}")
        return False


def _baixar_arquivos_via_api_v3(
    session: requests.Session,
    pasta_destino_cnpj: Path,
    cnpj_numeros: str,
    ids: Dict[str, Any],
    data_inicial_url: str,
    data_final_url: str
) -> bool:
    """
    (VERSÃO V3 - 100% API)
    Usa a sessão 'requests' para baixar os dois arquivos.
    """
    
    # 1. BAIXAR LIVRO FISCAL (PDF)
    try:
        logging.info("     - [API] Baixando Livro Fiscal (PDF)...")
        
        payload_pdf = {
            "rel": "livrofiscal",
            "tipo": "pdf",
            "parametros": f"string: '{ids['idContribuinte']}'",
            "dataIni": data_inicial_url,
            "dataFim": data_final_url
        }
        
        response_pdf = session.post(
            API_URL_PDF, 
            json=payload_pdf, 
            timeout=TIMEOUT_DOWNLOAD_API
        )
        response_pdf.raise_for_status() 

        caminho_pdf = pasta_destino_cnpj / f"{cnpj_numeros}_Livro_Fiscal.pdf"
        with open(caminho_pdf, 'wb') as f:
            f.write(response_pdf.content)
        logging.info("     - SUCESSO: Livro Fiscal (PDF) salvo.")

    except requests.exceptions.RequestException as e:
        logging.error(f"     - ERRO API (PDF): {e}")
        if e.response is not None:
             logging.error(f"     - Resposta do Servidor: {e.response.text[:200]}...")
        # Continua para o XML mesmo se o PDF falhar

    # 2. BAIXAR NOTAS (XML)
    try:
        logging.info("     - [API] Baixando Notas Fiscais (XML)...")
        
        params_xml = {
            "sIdCliente": ids['idCliente'],
            "idContribuinte": ids['idContribuinte'],
            "dataIni": data_inicial_url, # Formato complexo
            "dataFim": data_final_url,   # Formato complexo
            "docTomador": None,
            "idServicoItem": None,
            "situacao": "null",
            "tipo": "null"
        }

        response_xml = session.get(
            API_URL_XML, 
            params=params_xml, 
            timeout=TIMEOUT_DOWNLOAD_API
        )
        response_xml.raise_for_status()

        caminho_xml = pasta_destino_cnpj / f"{cnpj_numeros}_XML_Notas.zip"
        with open(caminho_xml, 'wb') as f:
            f.write(response_xml.content)
        logging.info("     - SUCESSO: Notas (XML) salvas.")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"     - ERRO API (XML): {e}")
        if e.response is not None:
             logging.error(f"     - Resposta do Servidor: {e.response.text[:200]}...")
        return False
        
    return True

# ==============================================================================
# --- [FUNÇÃO "MÃE" HÍBRIDA (V4.3 - "O CONSERTO FINAL")] ---
# ==============================================================================

def processar_automacao_hibrida_em_lote(
    # --- Argumentos ---
    portal_user: str,
    portal_pass: str,
    lista_de_cnpjs: List[str], # <-- Recebe uma LISTA
    start_date: date,
    end_date: date,
    base_download_path: Path,
    progress_callback: Callable
):
    """
    Função "MÃE" HÍBRIDA (V4.3 - "O Conserto Final"):
    Usa a lógica do "cód antigo" para o setup do Selenium (Login + Seleção + Navegação + Datas) 1 VEZ.
    Extrai o token e IDs.
    Fecha o Selenium.
    Loop 100% API para TODOS os CNPJs.
    """
    
    logging.info(f"--- INICIANDO AUTOMAÇÃO HÍBRIDA V4.3 (Setup Selenium 'Cód Antigo') ---")
    progress_callback(0, 100, "Iniciando...") 

    # Seta o locale para Inglês (C) para garantir %a e %b (Mon, Sep)
    try:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'C')
        except:
             logging.warning("Não foi possível setar o locale 'en_US' ou 'C'. Nomes de meses/dias podem falhar.")

    # Formato para a API (URL complexa)
    fuso_str = "GMT-0300 (Horário Padrão de Brasília)" 
    data_inicial_url = start_date.strftime(f"%a %b %d %Y 00:00:00 {fuso_str}")
    data_final_url = end_date.strftime(f"%a %b %d %Y 23:59:59 {fuso_str}")
    logging.info(f"Formato de data gerado para API (Início): {data_inicial_url}")
    
    # Formato para o Selenium (GUI)
    data_inicial_gui = start_date.strftime("%d/%m/%Y")
    data_final_gui = end_date.strftime("%d/%m/%Y")


    driver: WebDriver | None = None 
    token = None
    session = None
    id_cliente = None
    total_cnpjs = len(lista_de_cnpjs)
    
    if total_cnpjs == 0:
        logging.warning("Lista de CNPJs está vazia. Nada para processar.")
        progress_callback(100, 100, "Lista vazia.")
        return

    try:
        # ==================================================================
        # ETAPA 1: SETUP COMPLETO COM SELENIUM (FEITO 1 VEZ)
        # ==================================================================
        logging.info("ETAPA 1: Abrindo navegador e fazendo setup completo...")
        temp_dir = base_download_path / "temp_selenium" 
        driver = setup_driver(str(temp_dir)) 
        wait = WebDriverWait(driver, TIMEOUT_PRINCIPAL)
        
        progress_callback(5, 100, "Navegador aberto. Logando...")
        if not login_selenium(driver, wait, portal_user, portal_pass):
            raise Exception("Falha no Login (Selenium).")
        
        progress_callback(10, 100, "Login efetuado. Selecionando 1º CNPJ...")
        primeiro_cnpj = lista_de_cnpjs[0]
        cnpj_num_primeiro = "".join(filter(str.isdigit, primeiro_cnpj))
        
        # [V4.3] Usa a lógica de seleção CORRIGIDA (com ENTER + Clique)
        if not selecionar_contribuinte_selenium(driver, wait, cnpj_num_primeiro, primeiro_cnpj):
            raise Exception(f"Falha ao selecionar o primeiro CNPJ ({primeiro_cnpj}) com Selenium. Abortando.")
            
        progress_callback(15, 100, "Navegando para Consulta (Selenium)...")
        
        # [--- A CORREÇÃO V4.2 (QUE ESTAVA FALTANDO ANTES) ---]
        
        # Força a navegação para a página de consulta (para SAIR da "aba nada a ver")
        if not navegar_para_consulta_selenium(driver, wait):
            raise Exception("Falha ao navegar para a página de consulta (Selenium).")

        # Preenche as datas (para "acordar" o back-end)
        if not fill_dates_and_search_selenium(driver, wait, data_inicial_gui, data_final_gui):
            raise Exception("Falha ao preencher datas e pesquisar (Selenium).")
        
        # [--- FIM DA CORREÇÃO ---]

        progress_callback(20, 100, "Extraindo Token e IDs...")
        
        # 4. "Roubar" o Token e o idCliente (AGORA ELES DEVEM EXISTIR)
        time.sleep(2) # Garante que o JS escreveu tudo no storage
        token = _extrair_token_bearer(driver)
        id_cliente = _extrair_id_cliente(driver)
        
        if not token or not id_cliente:
            raise Exception("Falha fatal ao extrair Token ou idCliente do navegador (mesmo após setup completo).")
        
        logging.info("     - Credenciais de API extraídas com sucesso!")
        progress_callback(25, 100, "Credenciais extraídas.")

    except Exception as e_geral:
        logging.error(f"Erro CRÍTICO na automação (fase de setup com Selenium): {e_geral}")
        logging.error(traceback.format_exc())
        if driver:
            driver.save_screenshot(f"ERRO_CRITICO_GERAL.png")
        raise e_geral # Relança o erro para a GUI
    
    finally:
        # ==================================================================
        # ETAPA 2: FECHAR O SELENIUM (NÃO PRECISAMOS MAIS DELE)
        # ==================================================================
        if driver:
            driver.quit()
            logging.info("--- NAVEGADOR FECHADO ---")
            progress_callback(30, 100, "Navegador fechado. Iniciando API...")
    
    try:
        # ==================================================================
        # ETAPA 3: SETUP DA API (1 VEZ)
        # ==================================================================
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        })
        logging.info("     - Sessão de API (Requests) configurada.")
        
        # Mapeia todos os CNPJs para IDs de uma vez
        mapa_cnpj_para_id = _get_contribuinte_id_map(session, lista_de_cnpjs)
        
        # ==================================================================
        # ETAPA 4: O LOOP 100% API (RÁPIDO)
        # ==================================================================
        logging.info(f"--- INICIANDO LOOP 100% API PARA {total_cnpjs} CNPJs ---")
        
        for i, cnpj_doc in enumerate(lista_de_cnpjs):
            
            progresso_atual = int(35 + (i / total_cnpjs) * 60) # Progresso de 35% a 95%
            prog_msg = f"({i+1}/{total_cnpjs}) {cnpj_doc}"
            logging.info(f"\n--- Processando (API): {prog_msg} ---")
            
            cnpj_numeros = "".join(filter(str.isdigit, cnpj_doc))
            pasta_destino_cnpj = base_download_path / cnpj_numeros
            pasta_destino_cnpj.mkdir(parents=True, exist_ok=True)
            
            id_contribuinte = mapa_cnpj_para_id.get(cnpj_doc)
            
            if not id_contribuinte:
                logging.error(f"     - ERRO: ID para o CNPJ {cnpj_doc} não foi encontrado no mapa. Pulando.")
                continue
                
            try:
                # 9. [API] MUDAR O CONTEXTO DO CONTRIBUINTE
                progress_callback(progresso_atual, 100, f"Selecionando (API): {prog_msg}")
                if not _api_selecionar_contribuinte(session, id_cliente, id_contribuinte):
                    logging.warning(f"     - FALHA: API de seleção falhou para {cnpj_doc}. Pulando.")
                    continue
                
                # 10. [API] BAIXAR ARQUIVOS
                progress_callback(progresso_atual + 5, 100, f"Baixando (API): {prog_msg}")
                
                ids_atuais = {
                    "idCliente": id_cliente,
                    "idContribuinte": id_contribuinte
                }
                
                _baixar_arquivos_via_api_v3(
                    session=session,
                    pasta_destino_cnpj=pasta_destino_cnpj,
                    cnpj_numeros=cnpj_numeros,
                    ids=ids_atuais,
                    data_inicial_url=data_inicial_url, 
                    data_final_url=data_final_url      
                )
            
            except Exception as e_cnpj:
                logging.error(f"     - ERRO CRÍTICO no CNPJ {cnpj_doc} (Loop API): {e_cnpj}")
                logging.error(traceback.format_exc())

    except Exception as e_api_setup:
        logging.error(f"Erro CRÍTICO na automação (fase de setup API): {e_api_setup}")
        logging.error(traceback.format_exc())
        raise e_api_setup # Relança o erro para a GUI
    
    
    logging.info("--- PROCESSAMENTO HÍBRIDO V4.3 (Setup Completo) CONCLUÍDO ---")
    progress_callback(100, 100, "Processo finalizado")


# ==============================================================================
# --- EXEMPLO DE COMO USAR (SE EXECUTAR ESTE ARQUIVO DIRETAMENTE) ---
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler('automacao_hibrida.log')])

    USER = "seu_usuario"
    PASS = "sua_senha"
    
    LISTA_CNPJS_PARA_PROCESSAR = [
        "12.345.678/0001-99",
        "98.765.432/0001-00",
    ]
    
    DATA_INICIO = date(2025, 10, 1)
    DATA_FIM = date(2025, 10, 31)
    
    PASTA_DOWNLOADS = Path("./DOWNLOADS_AUTOMACAO")
    PASTA_DOWNLOADS.mkdir(exist_ok=True)

    def print_progress(value, max_val, message):
        logging.info(f"PROGresso: [{value}/{max_val}] - {message}")

    try:
        processar_automacao_hibrida_em_lote(
            portal_user=USER,
            portal_pass=PASS,
            lista_de_cnpjs=LISTA_CNPJS_PARA_PROCESSAR,
            start_date=DATA_INICIO,
            end_date=DATA_FIM,
            base_download_path=PASTA_DOWNLOADS,
            progress_callback=print_progress
        )
    except Exception as e:
        logging.error(f"A AUTOMACAO FALHOU TOTALMENTE: {e}")