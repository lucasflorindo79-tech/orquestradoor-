import os
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- CONFIG ---
BASE = "https://sinan.saude.gov.br"
LOGIN_URL = BASE + "/sinan/login/login.jsf"
EXPORT_SOLICITAR = BASE + "/sinan/secured/exportacao/solicitarExportacao.jsf"
EXPORT_CONSULTAR = BASE + "/sinan/secured/exportacao/consultarExportacoes.jsf"

# Lembre-se de definir estas variáveis de ambiente no seu GitHub Actions
USERNAME = os.environ.get("SINAN_USER")   
PASSWORD = os.environ.get("SINAN_PASS")
OUT_FOLDER = r"./downloads"
os.makedirs(OUT_FOLDER, exist_ok=True)

def run_automation():
    with sync_playwright() as p:
        # Use headless=True para rodar no GitHub Actions sem interface gráfica
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Login
        print("Tentando fazer login...")
        if not login(page, USERNAME, PASSWORD):
            print("Automação interrompida devido a falha no login.")
            browser.close()
            return

        # 2. Solicitar Exportação
        data_inicio = "01/01/2025"
        data_fim = datetime.now().strftime("%d/%m/%Y")
        print(f"Solicitando exportação de {data_inicio} até {data_fim}...")
        numero_solicitacao = solicitar_exportacao(page, data_inicio, data_fim)
        
        if not numero_solicitacao:
            print("Não foi possível obter o número da solicitação. Interrompendo.")
            browser.close()
            return

        # 3. Consultar e Baixar
        print(f"Aguardando e baixando arquivo para solicitação {numero_solicitacao}...")
        arquivo_baixado = consultar_e_baixar(page, numero_solicitacao)

        if arquivo_baixado:
        print(f"Processo finalizado. Arquivo salvo em: {arquivo_baixado}")
        
        # EXTRAIR ZIP
        extrair_zip(arquivo_baixado, OUT_FOLDER)
        
        # CONVERTER PARA EXCEL
        converter_dbf_para_excel(OUT_FOLDER)

        else:
        print("Falha ao baixar o arquivo.")

        browser.close()


def login(page, username, password):
    page.goto(LOGIN_URL)
    
    try:
        # Preenche os campos usando os seletores NAME que vimos antes
        page.fill('input[name="form:username"]', username)
        page.fill('input[name="form:password"]', password)
        
        # Clica no botão "Entrar" e espera a navegação/carregamento da página
        page.click('button:text("Entrar")') 
        # Aguarda a página carregar (pode demorar um pouco)
        page.wait_for_load_state('networkidle') 
        
        # Verifica se o login foi bem-sucedido checando a URL final
        if "/secured/" in page.url:
            print("Login OK!")
            return True
        else:
            print(f"Login falhou. URL atual: {page.url}")
            # O Playwright consegue ver a página, então podemos verificar a mensagem de erro
            error_message = page.locator('.ui-messages-error').all_inner_texts()
            if error_message:
                print(f"Mensagem de erro na tela: {error_message}")
            return False
            
    except PlaywrightTimeoutError:
        print("Timeout durante o login. Verifique a conexão ou seletor.")
        return False

def solicitar_exportacao(page, data_inicio, data_fim):
    page.goto(EXPORT_SOLICITAR)
    page.wait_for_load_state('domcontentloaded')

    # Preenche o formulário de solicitação
    page.select_option('select[name="form:consulta_tipoPeriodo"]', '0') # Data
    page.fill('input[name="form:consulta_dataInicialInputDate"]', data_inicio)
    page.fill('input[name="form:consulta_dataFinalInputDate"]', data_fim)
    page.select_option('select[name="form:tipoUf"]', '3') # Tipo UF (ajuste se necessário)

    # Clica no botão que aciona a solicitação (geralmente via AJAX)
    # O seletor "form:j_id128" é dinâmico, Playwright lida com isso se estiver visível/acessível
    # Vamos usar um seletor mais genérico se o nome mudar:
    page.click('button:has-text("Solicitar Exportação")') # Procure pelo texto do botão
    
    # Espera a resposta AJAX que contém o número da solicitação
    # O servidor responde com um número, que aparece na tela
    page.wait_for_selector('text=Solicitação efetuada com sucesso! Número:', timeout=30000)

    # Extrai o número da solicitação da página
    text_content = page.inner_text('body')
    m = re.search(r"Número:\s*([0-9\.]+)", text_content)
    if m:
        numero = m.group(1).replace(".", "")
        print("Número da solicitação:", numero)
        return numero
    else:
        print("Não foi possível extrair o número da solicitação da tela.")
        return None

def consultar_e_baixar(page, numero_solicitacao, timeout_minutes=15):
    page.goto(EXPORT_CONSULTAR)
    start_time = time.time()

    while time.time() - start_time < timeout_minutes * 60:
        page.wait_for_load_state('domcontentloaded')
        
        # Procura na tabela pelo número da solicitação e pelo link "Baixar arquivo DBF"
        # Usando seletores CSS mais avançados do Playwright
        download_link_selector = f'table.rich-table tbody tr:has-text("{numero_solicitacao}") a:has-text("Baixar arquivo DBF")'
        
        if page.locator(download_link_selector).count() > 0:
            print("Link de download encontrado!")
            
            # Clica no link e espera o download ocorrer
            with page.expect_download() as download_info:
                page.click(download_link_selector)
            
            download = download_info.value
            file_path = os.path.join(OUT_FOLDER, download.suggested_filename)
            download.save_as(file_path)
            print(f"Arquivo salvo: {file_path}")
            return file_path
        else:
            print(f"Arquivo {numero_solicitacao} não está pronto. Recarregando em 10s...")
            time.sleep(10)
            page.reload()

    raise TimeoutError("Tempo esgotado aguardando disponibilização do arquivo.")


if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Erro: Defina as variáveis de ambiente SINAN_USER e SINAN_PASS.")
        exit(1)
    
    run_automation()

import zipfile
import pandas as pd
from dbfread import DBF

def extrair_zip(zip_path, destino="./downloads"):
    print(f"Extraindo ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(destino)

    print("Arquivos extraídos.")
    return destino


def converter_dbf_para_excel(pasta_download="./downloads"):
    print("Procurando arquivos DBF...")

    # Procura o arquivo .dbf extraído
    for arquivo in os.listdir(pasta_download):
        if arquivo.lower().endswith(".dbf"):
            dbf_path = os.path.join(pasta_download, arquivo)
            print(f"Encontrado DBF: {dbf_path}")

            # Lê DBF
            table = DBF(dbf_path, load=True)
            df = pd.DataFrame(iter(table))

            # Gera Excel final
            excel_path = os.path.join(pasta_download, "dados_convertidos.xlsx")
            df.to_excel(excel_path, index=False)

            print(f"Excel gerado em: {excel_path}")
            return excel_path

    print("Nenhum arquivo DBF encontrado após extração.")
    return None
