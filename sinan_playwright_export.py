#!/usr/bin/env python3
"""
sinan_export.py

Automação Playwright para:
- login no SINAN
- solicitar exportação de um período
- consultar e baixar o arquivo DBF/ZIP gerado
- Extrair o arquivo para a pasta de saida.
"""

import os
import re
import time
import zipfile 
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

# Pasta local onde os downloads temporarios serão salvos
OUT_FOLDER_TEMP = "./downloads_temp"
os.makedirs(OUT_FOLDER_TEMP, exist_ok=True)

# Pasta FINAL onde o arquivo extraido será colocado para ser salvo como artefato
OUT_FOLDER_FINAL = "./saida_final"
os.makedirs(OUT_FOLDER_FINAL, exist_ok=True)


def run_automation() -> None:
    """Fluxo principal: login, solicitar exportação, consultar/baixar arquivo e extrair."""
    if not USERNAME or not PASSWORD:
        print("Erro: Defina as variáveis de ambiente SINAN_USER e SINAN_PASS.")
        return

    data_inicio = "01/01/2025"
    data_fim = datetime.now().strftime("%d/%m/%Y")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            if not login(page, USERNAME, PASSWORD):
                browser.close()
                return

            numero_solicitacao = solicitar_exportacao(page, data_inicio, data_fim)
            if not numero_solicitacao:
                browser.close()
                return

            arquivo_baixado_zip_path = consultar_e_baixar(page, numero_solicitacao, timeout_minutes=15)
            
            if arquivo_baixado_zip_path and os.path.exists(arquivo_baixado_zip_path):
                print(f"Download concluído: {arquivo_baixado_zip_path}")
                
                # --- NOVO PASSO: EXTRAIR ARQUIVO ---
                print(f"Extraindo arquivo para {OUT_FOLDER_FINAL}...")
                with zipfile.ZipFile(arquivo_baixado_zip_path, 'r') as z:
                    z.extractall(OUT_FOLDER_FINAL)
                
                print("Extração concluída. Arquivos prontos na pasta 'saida_final'.")
                
                # Limpeza: remove o arquivo zip temporário
                os.remove(arquivo_baixado_zip_path) 
                print("Arquivo zip temporário removido.")
            else:
                print("Falha ao baixar ou encontrar o arquivo ZIP.")

            browser.close()

    except PlaywrightError as e:
        print(f"Erro do Playwright: {e}")
    except Exception as e:
        print(f"Um erro inesperado ocorreu: {e}")


# --- FUNÇÕES DE LOGIN/CONSULTA/BAIXAR (Mantidas as originais) ---
# ... (manter as funções login, solicitar_exportacao, consultar_e_baixar sem alteração)

def login(page, username: str, password: str) -> bool:
   # Seu código de login original aqui
   pass 

def solicitar_exportacao(page, data_inicio: str, data_fim: str) -> Optional[str]:
   # Seu código de solicitar_exportacao original aqui
   pass

def consultar_e_baixar(page, numero_solicitacao: str, timeout_minutes: int = 15) -> Optional[str]:
   # Seu código de consultar_e_baixar original aqui
   
   # ATENÇÃO: Mude a variável OUT_FOLDER para OUT_FOLDER_TEMP nesta função
   # file_path = os.path.join(OUT_FOLDER, suggested) -> file_path = os.path.join(OUT_FOLDER_TEMP, suggested)
   pass

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    run_automation()
