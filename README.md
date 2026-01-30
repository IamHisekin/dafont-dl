# 🎨 DaFont Downloader

Um gerenciador moderno de fontes do **DaFont** com banco de dados offline, preview local, downloads em lote e interface multiplataforma.

Este projeto elimina scraping direto do site e trabalha com uma base SQLite sincronizada automaticamente a partir do GitHub, garantindo **performance**, **estabilidade** e uso offline.

---

## 📸 Interface

![Preview](https://i.imgur.com/9ZHyt1f.png)

---

## 🚀 Recursos

- ✅ Sincronização automática do banco de fontes via GitHub
- ✅ Organização alfabética (A–Z)
- ✅ Paginação (100 fontes por página)
- ✅ Busca por nome / slug
- ✅ Preview das fontes
- ✅ Cache local de previews
- ✅ Download individual ou em lote
- ✅ Download direto via link `.font`
- ✅ Seleção múltipla de fontes
- ✅ Console embutido com logs
- ✅ Temas:
  - Claro
  - Escuro
  - Seguir o Sistema
- ✅ Compatível com:
  - Windows
  - Linux
  - macOS

---

## 📂 Estrutura

```
dafont_app/
 ├── ui/
 ├── services/
 ├── db/
 ├── utils/
 ├── logs/
 ├── cache/
 └── downloads/
```

---

## 🗄️ Banco de Dados

O aplicativo sincroniza automaticamente com:

https://raw.githubusercontent.com/IamHisekin/dafont-dl/main/src/db-sync/fontes.db

---

## 🖼️ Preview

O preview funciona **sem acessar o site**:

1. A fonte é baixada como ZIP
2. Arquivos `.ttf/.otf` são extraídos temporariamente
3. Renderização local usando Qt
4. Cache armazenado
5. Cache limpo automaticamente ao fechar o programa

---

## 📥 Download

Links devem terminar com `.font`.

---

## 🛠️ Instalação

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m dafont_app
```

---

## 📜 Licença

Projeto educacional. Não me responsábilizo pelo uso indevido do projeto.
