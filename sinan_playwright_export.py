#!/usr/bin/env python3
"""
sinan_export.py

Automação Playwright para:
- login no SINAN
- solicitar exportação de um período
- consultar e baixar o arquivo DBF gerado

Como usar:
1) Defina as variáveis de ambiente SINAN_USER e SINAN_PASS (ex.: no GitHub Actions).
2) Rode: python sinan_export.py

Dependências:
- playwright
  (instalar localmente: pip install playwright && playwright install)
"""

import os
import re
import time
from datetime import datetime
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

# --- CONFIG ---
BASE = "https://sinan.saude.gov.br"
LOGIN_URL = BASE + "/sinan/login/login.jsf"
EXPORT_SOLICITAR = BASE + "/sinan/secured/exportacao/solicitarExportacao.jsf"
EXPORT_CONSULTAR = BASE + "/sinan/secured/exportacao/consultarExportacoes.jsf"

# Variáveis de ambiente (defina no GitHub Actions ou no seu ambiente local)
USERNAME = os.environ.get("SINAN_USER")
PASSWORD = os.environ.get("SINAN_PASS")

# Pasta local onde os downloads serão salvos
OUT_FOLDER = os.environ.get("SINAN_OUT_FOLDER", "./downloads")
os.makedirs(OUT_FOLDER, exist_ok=True)


def run_automation() -> None:
    """Fluxo principal: login, solicitar exportação, consultar/baixar arquivo."""
    if not USERNAME or not PASSWORD:
        print("Erro: Defina as variáveis de ambiente SINAN_USER e SINAN_PASS.")
        return

    # Período de exemplo (ajuste conforme desejar)
    data_inicio = "01/01/2025"
    data_fim = datetime.now().strftime("%d/%m/%Y")

    try:
        with sync_playwright() as p:
            # Usar headless=True para execução em CI/GitHub Actions
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("Tentando fazer login...")
            if not login(page, USERNAME, PASSWORD):
                print("Automação interrompida devido a falha no login.")
                browser.close()
                return

            print(f"Solicitando exportação de {data_inicio} até {data_fim}...")
            numero_solicitacao = solicitar_exportacao(page, data_inicio, data_fim)
            if not numero_solicitacao:
                print("Não foi possível obter o número da solicitação. Interrompendo.")
                browser.close()
                return

            print(f"Aguardando e baixando arquivo para solicitação {numero_solicitacao}...")
            arquivo_baixado = consultar_e_baixar(page, numero_solicitacao, timeout_minutes=15)
            if arquivo_baixado:
                print(f"Processo finalizado. Arquivo salvo em: {arquivo_baixado}")
            else:
                print("Falha ao baixar o arquivo.")

            browser.close()

    except PlaywrightError as e:
        print(f"Erro do Playwright: {e}")


def login(page, username: str, password: str) -> bool:
    """Realiza login e retorna True se bem-sucedido."""
    try:
        page.goto(LOGIN_URL)
        page.wait_for_load_state("domcontentloaded")

        # Preenche campos (ajuste seletores se necessário)
        page.fill('input[name="form:username"]', username)
        page.fill('input[name="form:password"]', password)

        # Clica no botão "Entrar" e aguarda carregamento
        try:
            page.click('button:has-text("Entrar")')
        except PlaywrightTimeoutError:
            # Tentar outro seletor caso o primeiro não funcione
            page.click('input[type="submit"]')

        page.wait_for_load_state("networkidle", timeout=15000)

        # Verifica se a URL final indica login bem sucedido
        if "/secured/" in page.url:
            print("Login OK!")
            return True

        # Se não, tenta capturar mensagem de erro exibida na página
        try:
            errors = page.locator(".ui-messages-error, .ui-message-error").all_inner_texts()
            if errors:
                print("Mensagens de erro durante login:", errors)
        except Exception:
            pass

        print(f"Login possivelmente falhou. URL atual: {page.url}")
        return False

    except PlaywrightTimeoutError:
        print("Timeout durante o login. Verifique a conexão ou os seletores.")
        return False
    except Exception as e:
        print(f"Exceção ao tentar logar: {e}")
        return False


def solicitar_exportacao(page, data_inicio: str, data_fim: str) -> Optional[str]:
    """
    Solicita a exportação do SINAN.
    Retorna o número da solicitação (string) ou None se falhar.
    """
    try:
        page.goto(EXPORT_SOLICITAR)
        page.wait_for_load_state("domcontentloaded")

        # Ajuste os selects/inputs conforme a página (estes nomes vêm do código original)
        page.select_option('select[name="form:consulta_tipoPeriodo"]', value="0")
        page.fill('input[name="form:consulta_dataInicialInputDate"]', data_inicio)
        page.fill('input[name="form:consulta_dataFinalInputDate"]', data_fim)

        # Exemplo de seleção de UF: ajustar se necessário
        # O valor '3' veio do seu script; confirme caso precise.
        try:
            page.select_option('select[name="form:tipoUf"]', value="3")
        except Exception:
            # se o select tiver outro nome, seguimos em frente (não crítico)
            pass

        # Clica no botão de solicitar exportação (tenta texto "Solicitar Exportação")
        try:
            page.click('button:has-text("Solicitar Exportação")', timeout=5000)
        except PlaywrightTimeoutError:
            # fallback: tenta clicar em qualquer botão que contenha "Solicitar"
            page.click('button:has-text("Solicitar")')

        # Aguarda alguma indicação na página de que a solicitação ocorreu
        # Timeout maior porque a operação pode demorar
        try:
            page.wait_for_selector("text=Solicitação efetuada", timeout=30000)
        except PlaywrightTimeoutError:
            # Continua mesmo sem o seletor - vamos tentar extrair o número do corpo
            pass

        # Tenta extrair o número da requisição do conteúdo da página
        body = page.inner_text("body")
        # Padrão comum: "Número: 1.234" ou "Número: 1234"
        m = re.search(r"N[uú]mero[:\s]*([\d\.]+)", body)
        if m:
            numero = m.group(1).replace(".", "")
            print("Número da solicitação extraído:", numero)
            return numero

        # Outra tentativa: procurar apenas por dígitos longos que apareçam após palavras-chave
        m2 = re.search(r"Solicita.*?([0-9]{4,})", body)
        if m2:
            numero = m2.group(1)
            print("Número da solicitação (via fallback):", numero)
            return numero

        print("Não foi possível extrair o número da solicitação da tela.")
        return None

    except Exception as e:
        print(f"Erro ao solicitar exportação: {e}")
        return None


def consultar_e_baixar(page, numero_solicitacao: str, timeout_minutes: int = 15) -> Optional[str]:
    """
    Consulta as exportações e tenta baixar o arquivo DBF relacionado ao número fornecido.
    Retorna o caminho do arquivo salvo ou None se houver falha/timeout.
    """
    try:
        page.goto(EXPORT_CONSULTAR)
        start_time = time.time()

        while time.time() - start_time < timeout_minutes * 60:
            page.wait_for_load_state("domcontentloaded")

            # Monta um seletor robusto que procura na tabela pela linha com o número
            download_link_selector = (
                f'table.rich-table tbody tr:has-text("{numero_solicitacao}") a:has-text("Baixar arquivo DBF")'
            )

            locator = page.locator(download_link_selector)
            if locator.count() > 0:
                print("Link de download encontrado! Iniciando download...")
                with page.expect_download() as download_info:
                    locator.first.click()
                download = download_info.value
                suggested = download.suggested_filename or f"{numero_solicitacao}.zip"
                file_path = os.path.join(OUT_FOLDER, suggested)
                download.save_as(file_path)
                print(f"Arquivo salvo: {file_path}")
                return file_path

            # Se não encontrou, espera e recarrega a lista
            print(f"Arquivo {numero_solicitacao} ainda não disponível. Aguardando 10s...")
            time.sleep(10)
            page.reload()

        # Timeout
        print("Tempo esgotado aguardando disponibilização do arquivo.")
        return None

    except PlaywrightTimeoutError:
        print("Timeout ao consultar exportações.")
        return None
    except Exception as e:
        print(f"Erro ao consultar e baixar: {e}")
        return None


if __name__ == "__main__":
    run_automation()
