import os
import zipfile
from rich import print

# Verifica e cria a pasta "Fonts" se não existir
fonts_folder = os.path.join(os.getcwd(), "Fonts")
if not os.path.exists(fonts_folder):
    os.makedirs(fonts_folder)

# Função para extrair as fontes de um arquivo .zip
def extract_fonts(zip_file, target_folder):
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            for member in zf.infolist():
                if member.filename.lower().endswith((".otf", ".ttf")):
                    member.filename = os.path.basename(member.filename)
                    zf.extract(member, target_folder)
        print(f"[green]Fontes extraídas:[/green] {os.path.basename(zip_file)}")
    except zipfile.BadZipFile:
        print(f"[red]Erro ao extrair fontes: Arquivo ZIP inválido ou corrompido: {os.path.basename(zip_file)}[/red]")

# Percorre os arquivos .zip em "Downloads"
extracted_fonts = 0
for root, dirs, files in os.walk("Downloads"):
    for file in files:
        if file.lower().endswith(".zip"):
            zip_file = os.path.join(root, file)

            # Extrai as fontes do arquivo .zip
            target_folder = os.path.join(fonts_folder, file[0].upper())
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            extract_fonts(zip_file, target_folder)
            extracted_fonts += 1

# Organiza a saída usando Rich
print("\n[bold green]Extração de fontes concluída![/bold green]")
print(f"[bold]Pasta de fontes:[/bold] {fonts_folder}")
print(f"[bold]Total de fontes extraídas:[/bold] {extracted_fonts}")
