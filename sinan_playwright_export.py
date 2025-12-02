from playwright.sync_api import sync_playwright, TimeoutError
import time
import os

LOGIN_URL = "https://sinan.saude.gov.br/sinan/login/login.jsf"

def main():
    user = os.getenv("SINAN_USER")
    password = os.getenv("SINAN_PASS")

    if not user or not password:
        print("❌ ERRO: Variáveis de ambiente SINAN_USER e SINAN_PASS não estão configuradas!")
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        print("➡️ Acessando página de login...")
        page.goto(LOGIN_URL, timeout=60000)

        print("🌐 URL antes do login:", page.url)

        try:
            # Preencher usuário
            page.fill("input[name='j_idt29:login']", user)

            # Preencher senha
            page.fill("input[name='j_idt29:senha']", password)

            # Clicar no botão Entrar
            page.click("input[value='Entrar']")

        except Exception as e:
            print("❌ Erro ao interagir com os campos de login:", e)
            browser.close()
            return

        # Esperar a página carregar
        time.sleep(5)

        print("🌐 URL após login:", page.url)

        # Extra opcional: salvar print para debug
        page.screenshot(path="login_result.png")
        print("📸 Screenshot salvo (login_result.png)")

        browser.close()

if __name__ == "__main__":
    main()
