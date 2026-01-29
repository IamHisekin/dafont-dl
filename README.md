# DaFont Downloader (GUI)

App desktop (Windows/Linux/macOS) para **cachear** fontes do DaFont em um banco SQLite e baixar por **busca/categoria** ou **link direto**.

## Recursos

- **Atualizar Banco de Dados**: varre as categorias (Fantasia, Estrangeiras, Tecno, Gótica, Básica, Escrita, Dingbats, Festas) e salva/atualiza no SQLite.
- **Filtro por nome** + **filtro por categoria** (tudo rodando no banco — sem precisar pesquisar no site).
- **Download da fonte selecionada**.
- **Baixar através de link** (página `.font` ou link `dl.dafont.com/dl/?f=...`).
- **Prévia**: usa o endpoint `preview.php` do DaFont (imagem) e permite editar o texto da prévia.

## Instalação

Requisitos: Python 3.12+ (compatível com 3.14).

```bash
pip install -r requirements.txt
pip install -e .
```

Rodar:

```bash
dafont-gui
# ou
python -m dafont_app
```

## Onde o app guarda os arquivos

Por padrão:

- Banco: `~/.dafont_gui/dafont.sqlite3`
- Downloads: `~/.dafont_gui/Downloads/`

Você pode mudar a pasta de download no botão **Pasta de Download…**.
