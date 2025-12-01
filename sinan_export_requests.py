import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import os

# --- CONFIG ---
BASE = "https://sinan.saude.gov.br"
LOGIN_URL = BASE + "/sinan/login/login.jsf"
EXPORT_SOLICITAR = BASE + "/sinan/secured/exportacao/solicitarExportacao.jsf"
EXPORT_CONSULTAR = BASE + "/sinan/secured/exportacao/consultarExportacoes.jsf"
DOWNLOAD_BASE = BASE  # normalmente o link é relativo

USERNAME = os.environ.get("SINAN_USER")   # setar como variavel de ambiente
PASSWORD = os.environ.get("SINAN_PASS")
OUT_FOLDER = r"./downloads"
os.makedirs(OUT_FOLDER, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/142.0.0.0"
})

def get_viewstate(html):
    soup = BeautifulSoup(html, "html.parser")
    vs = soup.find("input", {"name": lambda n: n and "ViewState" in n})
    if not vs:
        # alternativa para jsf: javax.faces.ViewState
        vs = soup.find("input", {"name":"javax.faces.ViewState"})
    return vs["value"] if vs else None

def login(username, password):
    # 1) GET login page
    r = session.get(LOGIN_URL, timeout=30)
    r.raise_for_status()
    viewstate = get_viewstate(r.text)

    # 2) Prepare payload. OS nomes dos campos dependem do form da página; ajustar se diferente
    payload = {
        "form:username": username,
        "form:password": password,
        "form": "form",
        "form:j_idt??": "",   # se a página tiver campos ocultos extras
        "javax.faces.ViewState": viewstate,
        "form:loginButton": "Entrar"  # nome do botão pode variar
    }
    # Muitas vezes o botão é apenas um input; experimente sem o botão também
    # Enviar POST
    r2 = session.post(LOGIN_URL, data=payload, headers={"Referer": LOGIN_URL}, timeout=30)
    r2.raise_for_status()
    # verificar se login ok (ex.: presença de texto "logout" ou usuário no topo)
    if "Sair" in r2.text or "logout" in r2.text.lower() or username.split('@')[0] in r2.text:
        print("Login OK")
        return True
    else:
        print("Login possivelmente falhou; verifique credenciais ou formulário.")
        return False

def solicitar_exportacao(data_inicio, data_fim):
    # 1) load solicitarExportacao page to get viewstate (pode ser necessário carregar consultarExportacoes)
    r = session.get(EXPORT_SOLICITAR, timeout=30)
    r.raise_for_status()
    viewstate = get_viewstate(r.text)

    # Prepare payload baseado no curl que você achou. Ajuste nomes se necessário.
    data_payload = {
        "AJAXREQUEST": "_viewRoot",
        "form": "form",
        "form:consulta_tipoPeriodo": "0",  # Data por exemplo
        "form:consulta_dataInicialInputDate": data_inicio,
        "form:consulta_dataInicialInputCurrentDate": data_inicio.split('/')[-1], # placeholder
        "form:consulta_dataFinalInputDate": data_fim,
        "form:consulta_dataFinalInputCurrentDate": data_fim.split('/')[-1],
        "form:j_id102": "10",
        "form:tipoUf": "3",  # Notificação ou Residência (valor conforme select)
        "form:regionalcomboboxField": "",
        "form:regional": "",
        "form:municipiocomboboxField": "",
        "form:municipio": "",
        "form:j_id120": "0",
        "form:j_id124": "on",  # exportar dados de id paciente?
        "javax.faces.ViewState": viewstate,
        "form:j_id128": "form:j_id128",  # o botão acionado via AJAX no curl
        "AJAX:EVENTS_COUNT": "1"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": EXPORT_SOLICITAR,
        "Origin": BASE
    }

    r2 = session.post(EXPORT_SOLICITAR, data=data_payload, headers=headers, timeout=60)
    r2.raise_for_status()
    # Resposta deve conter info com "Número:" ou algo similar (é HTML parcial)
    txt = r2.text
    # tentar extrair "Número: 12345"
    import re
    m = re.search(r"Número:\s*([0-9\.]+)", txt)
    if m:
        numero = m.group(1).replace(".", "")
        print("Número da solicitação:", numero)
        return numero
    else:
        print("Não consegui extrair número da resposta. Resposta curta:")
        print(txt[:800])
        return None

def consultar_e_baixar(numero_solicitacao, timeout_minutes=15):
    deadline = time.time() + timeout_minutes*60
    while time.time() < deadline:
        r = session.get(EXPORT_CONSULTAR, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # procurar a tabela com linhas <tr> e coluna 1 texto igual ao número
        linhas = soup.select("table.rich-table tbody tr")
        for tr in linhas:
            tds = tr.find_all("td")
            if not tds:
                continue
            numero = tds[0].get_text(strip=True)
            if numero.replace(".", "") == numero_solicitacao:
                print("Encontrado número na tabela! Tentando localizar link de download...")
                # procurar link com texto "Baixar arquivo DBF" dentro deste TR
                link = tr.find("a", string=lambda s: s and "Baixar arquivo DBF" in s)
                if link and link.has_attr("href"):
                    href = link["href"]
                    # se href for relativo, montar absoluto
                    if href.startswith("/"):
                        href = BASE + href
                    print("Link de download:", href)
                    # GET o conteúdo
                    out_name = os.path.join(OUT_FOLDER, f"export_{numero_solicitacao}.zip")
                    dl = session.get(href, stream=True, timeout=120)
                    dl.raise_for_status()
                    with open(out_name, "wb") as f:
                        for chunk in dl.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print("Arquivo salvo:", out_name)
                    return out_name
                else:
                    # talvez exista um botão que aciona JS — então buscar <a> com class 'download' ou input
                    link2 = tr.find("a")
                    if link2 and link2.has_attr("onclick"):
                        # pode ser necessário construir URL do onclick — difícil generalizar
                        print("Link com onclick. Conteúdo onclick:", link2["onclick"][:200])
                        # tentar extrair URL do onclick...
                    print("Link não encontrado ainda. Vamos aguardar e tentar de novo.")
        print("Não achou ainda. Vou aguardar 10s e tentar novamente...")
        time.sleep(10)
    raise TimeoutError("Tempo esgotado aguardando disponibilização do arquivo.")

if __name__ == "__main__":
    # Garante que as variáveis USERNAME e PASSWORD foram preenchidas por os.environ.get()
    
    if not USERNAME:
        print("Erro: Defina as variáveis de ambiente SINAN_USER e SINAN_PASS.")
        exit(1)
        
    if not PASSWORD:
        print("Erro: Defina as variáveis de ambiente SINAN_USER e SINAN_PASS.")
        exit(1)

    ok = login(USER, PASS)
    if not ok:
        raise SystemExit("Login falhou.")

    # datas exemplo
    data_inicio = "01/01/2025"
    data_fim = datetime.now().strftime("%d/%m/%Y")
    numero = solicitar_exportacao(data_inicio, data_fim)
    if not numero:
        raise SystemExit("Não foi possível solicitar exportação.")

    arquivo = consultar_e_baixar(numero, timeout_minutes=20)

    print("Processo finalizado. Arquivo:", arquivo)
