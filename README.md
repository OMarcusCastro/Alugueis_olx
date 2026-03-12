# Alugueis_olx

Automacao de cunho educativo e de uso pessoal.
A OLX infelizmente nao filtra apartamentos pelo valor total de aluguel + condominio,
entao criei essa ferramenta com interface interativa para facilitar a busca.

## Funcionalidades

- Scraping automatico dos anuncios da OLX via Selenium
- Calculo do custo total (aluguel + condominio)
- Filtro por valor maximo mensal
- Filtros interativos: custo total, aluguel, condominio, area, quartos, banheiros, vagas de garagem e localizacao
- Ordenacao por custo total, aluguel, condominio, area ou data do anuncio
- Visualizacao em **tabela** ou **galeria** com imagens dos anuncios
- Metricas resumidas: total encontrados, menor custo, custo medio, maior area e media de vagas

## Pre-requisitos

### 1. Instalar o Python

- Acesse [python.org/downloads](https://www.python.org/downloads/) e baixe a versao **3.10 ou superior**
- Durante a instalacao no Windows, **marque a opcao "Add Python to PATH"**
- Para verificar se instalou corretamente, abra o terminal e execute:

    ```bash
    python --version
    ```

### 2. Instalar o Google Chrome

- A aplicacao usa o Chrome para fazer o scraping. Baixe em [google.com/chrome](https://www.google.com/intl/pt-BR/chrome/)

### 3. Instalar o Git (opcional, para clonar o repositorio)

- Baixe em [git-scm.com](https://git-scm.com/downloads)

## Instalacao

1. Clonar o repositorio (ou baixar o ZIP pelo GitHub)

    ```bash
    git clone https://github.com/seu-usuario/Alugueis_olx.git
    cd Alugueis_olx
    ```

2. Criar ambiente virtual Python

    ```bash
    python -m venv venv
    ```

3. Ativar ambiente virtual

    - MacOS/Linux:
        ```bash
        source venv/bin/activate
        ```
    - Windows (CMD):
        ```bash
        venv\Scripts\activate
        ```
    - Windows (PowerShell):
        ```bash
        venv\Scripts\Activate.ps1
        ```

4. Instalar dependencias

    ```bash
    pip install -r requirements.txt
    ```

## Execucao

```bash
streamlit run scrapping_v2.py
```

A aplicacao vai abrir automaticamente no navegador em `http://localhost:8501`.

## Como usar

1. Entre na OLX e filtre ao maximo os itens que deseja
2. Coloque o valor maximo de aluguel como o valor total que pagaria (aluguel + condominio)
3. Copie o link completo e cole na sidebar da aplicacao
4. Clique em **Buscar**

> **Obs:** caso o link termine com `ol=1`, apague esse termo antes de colar.

## Exemplo

![Exemplo](./img1.png)
![Exemplo](./img2.png)

by: [Marcus Castro](https://www.linkedin.com/in/marcus-castroo/)
