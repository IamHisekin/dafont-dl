import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def update_database():
    console.print("[bold]Atualizando o banco de dados...[/bold]")
    os.system("python update_db.py")
    console.print("[bold green]Banco de dados atualizado![/bold green]")

def download_database():
    console.print("[bold]Baixando fontes...[/bold]")
    os.system("python download_db.py")
    console.print("[bold green]Processo concluído![/bold green]")
    
def extract_fonts():
    console.print("[bold]Extraindo fontes...[/bold]")
    os.system("python extract_db.py")
    console.print("[bold green]Processo concluído![/bold green]")

def main_menu():
    console.print(r"""
####       ##     ######    ####    ##  ##   ######            ####     ##
## ##     ####    ##       ##  ##   ### ##     ##              ## ##    ##
##  ##   ##  ##   ##       ##  ##   ######     ##              ##  ##   ##
##  ##   ######   ####     ##  ##   ######     ##     ######   ##  ##   ##
##  ##   ##  ##   ##       ##  ##   ## ###     ##              ##  ##   ##
## ##    ##  ##   ##       ##  ##   ##  ##     ##              ## ##    ##
####     ##  ##   ##        ####    ##  ##     ##              ####     ######                               
    """)

    while True:
        console.print("[bold cyan]Menu Principal[/bold cyan]")

        panel_options = Panel(
            Text("1. Atualizar Banco de Dados\n"
                 "2. Baixar fontes do DB\n"
                 "3. Extrair fontes baixadas\n"
                 "4. Sair"),
            title="[bold]Selecione uma opção[/bold]",
            padding=(1, 2)
        )
        console.print(panel_options)

        option = console.input("\nDigite o número da opção desejada: ")

        if option == "1":
            with console.status("[bold cyan]Atualizando...[/bold cyan]\n"):
                update_database()
        elif option == "2":
            with console.status("[bold cyan]Processando...[/bold cyan]\n"):
                download_database()
        elif option == "3":
            with console.status("[bold cyan]Processando...[/bold cyan]\n"):
                extract_fonts()
        elif option == "4":
            console.print("\n[bold yellow]Programa encerrado![/bold yellow]")
            break
        else:
            console.print("\n[bold red]Opção inválida! Por favor, selecione uma opção válida.[/bold red]")

if __name__ == "__main__":
    main_menu()
