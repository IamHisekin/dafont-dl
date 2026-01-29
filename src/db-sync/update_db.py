import os
import requests
from bs4 import BeautifulSoup
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from time import time
from rich import print

# Defina o URL base e as letras que deseja percorrer
base_url = "https://www.dafont.com/pt/alpha.php?lettre="
letras = "abcdefghijklmnopqrstuvwxyz#"

# Nome do arquivo .journey temporário
temp_file = "fontes.journey"

# Conecte-se ao banco de dados SQLite3
conn = sqlite3.connect("fontes.db")
cursor = conn.cursor()

# Crie a tabela para armazenar as fontes, se ela não existir
cursor.execute("""CREATE TABLE IF NOT EXISTS fontes (
                    nome TEXT,
                    link TEXT,
                    link_download TEXT
                )""")

# Define o cabeçalho User-Agent
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
}

# Função para coletar informações das fontes em uma página
def collect_font_info(url):
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    divs_fontes = soup.find_all("div", class_="lv1left dfbg")
    fontes = []
    for div_fonte in divs_fontes:
        link = "https://www.dafont.com" + div_fonte.find("a")["href"]
        nome = link.split("/")[-1].replace(".font", "").replace("www.dafont.com", "")
        link = f"https://www.dafont.com/pt/{nome}.font"
        link_download = f"https://dl.dafont.com/dl/?f={nome.replace('-', '_')}"
        fontes.append({"nome": nome, "link": link, "link_download": link_download})
    return fontes

# Função para verificar se as fontes já existem no banco de dados
def verify_font_exists(fontes):
    cursor.execute("SELECT nome FROM fontes WHERE nome IN (" + ",".join(["?"] * len(fontes)) + ")", [fonte["nome"] for fonte in fontes])
    resultados = cursor.fetchall()
    fontes_existentes = [resultado[0] for resultado in resultados]
    return fontes_existentes

# Função para inserir as fontes no banco de dados
def insert_fontes(fontes):
    for fonte in fontes:
        cursor.execute("INSERT INTO fontes VALUES (?, ?, ?)", (fonte["nome"], fonte["link"], fonte["link_download"]))

# Percorra as letras
for letra in letras:      
    
    try: 
        os.remove(temp_file)  # Deleta o arquivo temporário
    except:
        pass
    
      
    url = base_url + letra
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    div_noindex = soup.find("div", class_="noindex")
    last_page = int(div_noindex.find_all("a")[-2]["href"].split("=")[-1])
    
    print(f"[bold]Letra {letra.upper()}: {last_page} páginas disponíveis[/bold]")
    
    fontes_coletadas = []
    start_time = time()
    
    with ThreadPoolExecutor() as executor:
        urls = [f"{url}&page={page}" for page in range(1, last_page + 1)]
        results = executor.map(collect_font_info, urls)
        for result in results:
            fontes_coletadas.extend(result)
    
    end_time = time()
    print(f"[bold]Tempo decorrido na coleta de fontes: {end_time - start_time} segundos[/bold]")
    
    fontes_existentes = verify_font_exists(fontes_coletadas)
    
    fontes_novas = [fonte for fonte in fontes_coletadas if fonte["nome"] not in fontes_existentes]
    
    if fontes_novas:
        insert_fontes(fontes_novas)
        print("[bold green]Fontes novas adicionadas ao banco de dados[/bold green]")
    else:
        print("[bold blue]Nenhuma fonte nova encontrada[/bold blue]")

    # Faça commit das alterações no banco de dados
    conn.commit()

    # Limpe o arquivo .journey para receber o novo alfabeto
    open(temp_file, "w").close()

# Feche a conexão com o banco de dados
conn.close()

# Exclua os arquivos temporários
os.remove(temp_file)
