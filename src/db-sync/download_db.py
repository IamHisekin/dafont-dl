import os
import requests
from requests.exceptions import ChunkedEncodingError
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from time import time
from rich import print

# Verifica e cria a pasta "Downloads" se não existir
downloads_folder = os.path.join(os.getcwd(), "Downloads")
if not os.path.exists(downloads_folder):
    os.makedirs(downloads_folder)

# Define as letras do alfabeto e o caractere #
letras = "abcdefghijklmnopqrstuvwxyz#"

# Função para baixar uma fonte
def download_font(font_info):
    nome = font_info["nome"]
    link_download = font_info["link_download"]

    # Verifica se a fonte já foi baixada
    font_file = nome.replace("-", "_") + ".zip"
    font_path = os.path.join(downloads_folder, nome[0].upper(), font_file)
    if os.path.exists(font_path):
        return

    try:
        # Realiza o download da fonte
        response = requests.get(link_download)
        with open(font_path, "wb") as file:
            file.write(response.content)
            print(f"[green]Fonte baixada:[/green] {font_path}")
    except ChunkedEncodingError as e:
        print(f"[bold red]Erro ao baixar fonte: {e}[/bold red]")

# Conecta-se ao banco de dados SQLite3
conn = sqlite3.connect("fontes.db")
cursor = conn.cursor()

# Função para verificar se uma fonte já foi baixada
def verify_font_downloaded(font_info):
    nome = font_info["nome"]
    font_file = nome.replace("-", "_") + ".zip"
    font_path = os.path.join(downloads_folder, nome[0].upper(), font_file)
    return os.path.exists(font_path)

# Percorre as letras em multithread
with ThreadPoolExecutor() as executor:
    for letra in letras:
        # Cria a pasta para a letra, se não existir
        letra_folder = os.path.join(downloads_folder, letra.upper())
        if not os.path.exists(letra_folder):
            os.makedirs(letra_folder)

        # Busca as fontes da letra no banco de dados
        cursor.execute("SELECT nome, link_download FROM fontes WHERE nome LIKE ?", [f"{letra}%"])
        fontes = [{"nome": nome, "link_download": link_download} for nome, link_download in cursor.fetchall()]

        # Filtra as fontes que ainda não foram baixadas
        fontes_nao_baixadas = [fonte for fonte in fontes if not verify_font_downloaded(fonte)]

        # Baixa as fontes em multithread
        results = executor.map(download_font, fontes_nao_baixadas)
        for _ in results:
            pass

# Fecha a conexão com o banco de dados
conn.close()

# Organiza a saída usando Rich
print("\n[bold green]Download de fontes concluído![/bold green]")
print(f"[bold]Pasta de downloads:[/bold] {downloads_folder}")
print(f"[bold]Total de fontes baixadas:[/bold] {sum([len(files) for _, _, files in os.walk(downloads_folder)])}")
