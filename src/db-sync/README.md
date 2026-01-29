# DaFont-dl
Script para download de todas as fontes disponíveis no dafont.com

## Dependências
As seguintes dependências abaixo são necessárias.

- rich
- requests
- BeautifulSoup

Você pode instalar eles usando o seguinte comando.
```sh
pip install rich requests BeautifulSoup
```

## O que ele faz?

- Analisa todo o site dafont.com e constrói um banco de dados em sqlite3 armazenando dados da fonte.
- Efetua o download de todas as fontes em .zip na pasta Downloads e organiza por ordem alfabetica.
- Extrai apenas arquivos do tipo .otf e .ttf

O motivo do banco de dados, é que o processo de consulta é lento. Já possuindo ele construído, o download das fontes é quase instantâneo.

## Como usar?

Execute o main.py
```ssh
python main.py
```

O código baixado do Github já possui um banco de dados atualizado no dia 20/06/2023. Se preferir, você pode escolher a opção e atualizar ele novamente para acrescentar todas as fontes novas adicionadas ao site.

Após atualizar, use a opção 2 para efetuar o download de todas as fontes. Lembre-se que o tempo vária de computador para computador já que o mesmo faz uso de threads e depende da velocidade da internet. (Caso você feche o programa por engano, ao abrir novamente e executar a opção 2 ele vai continuar de onde parou. Ele efetua uma verificação dos arquivos com o banco de dados.).

Após finalizar o download. Utilize a opção 3 para extraír todos os arquivos de fontes se preferir. É opcional. 


## Considerações finais

O código disponibilizado foi escrito em poucas horas e por esse motivo pode conter muitos erros internamente, como também pode não estar otimizado. 

Esse código é livre para uso e para reprodução. Peço apenas que dêem os créditos. 
