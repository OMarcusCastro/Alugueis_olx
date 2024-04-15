import time
import os

import pandas as pd
import streamlit as st

from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from driver.driver_init import create_undetected_driver, espera_elemento_presente
import json


# input("Press Enter to continue...")


def rs_to_float(text):
    number = text.split()[-1]
    number = number.replace(".", "")
    number = number.replace(",", ".")
    number = float(number)
    return number


def check_title(title):
    keywords = ['apartamento', 'aluga', 'aluguel', 'apto', 'apart', 'apartament', 'apartamento', 'apartamentos', 'casa',
                'kitnet', 'kit', 'loft', 'flat', 'cobertura', 'duplex', 'triplex', 'sobrado', 'condominio', 'residencial', 'residencia', 'residencias',]
    if not any(word in title.lower() for word in keywords):
        return False
    return True


def intereable_link(link, page=1):
    link = link.split("o=")[0]
    new_link = f"{link}o={page}"
    return new_link


def get_last_page_number(pagination_list):
    last_page_element = pagination_list.find_elements(
        By.TAG_NAME, "a")[-1]

    last_page_link = last_page_element.get_attribute("href")
    number = int(last_page_link.split("o=")[-1])
    return number


def scrapping(link, price_limit):
    # link = "https://www.olx.com.br/imoveis/aluguel/estado-ce/fortaleza-e-regiao/fortaleza?bas=1&ps=1000&q=apartamento&ros=1&sd=2695&sd=2726&sd=2715&sd=2740&sd=2708&sd=2744&sd=2690&sd=2705&sd=2724&sd=2755&sd=2725&sd=2747&sd=2752&sd=2692&sd=2679&sd=2681&ss=1&o=1"
    # link = "https://www.olx.com.br/imoveis/aluguel/estado-ce/fortaleza-e-regiao/fortaleza?bas=1&pe=3500&ps=1000&q=apartamento&ros=1&sd=2695&sd=2726&sd=2715&sd=2740&sd=2708&sd=2744&sd=2690&sd=2705&sd=2724&sd=2755&sd=2725&sd=2747&sd=2752&sd=2692&sd=2679&sd=2681&ss=1"
    driver = create_undetected_driver(headless=False)

    driver.get(link)
    # espera_elemento_presente(By.ID, "listing-pagination", driver, 10)
    pagination_list = driver.find_element(
        By.ID, "listing-pagination")
    last_page_number = get_last_page_number(pagination_list)
    print(f"Last page number: {last_page_number}")
    apartamentos = []

    for i in range(1, last_page_number+1):

        time.sleep(0.6)
        # try:
        driver.get(f"{link}&o={i}")

        time.sleep(5)
        print('Page:', i)

        dados = driver.find_element(By.ID, "__NEXT_DATA__")
        dados = dados.get_attribute("innerHTML")
        dados = json.loads(dados)
        dados = dados['props']['pageProps']['ads']

        for apartamento in dados:
            try:
                # print(apartamento.keys())
                total_cost = 0
                condominio = None
                iptu = None
                size = None
                quartos = None
                banheiros = None
                for elemento in apartamento['properties']:
                    if elemento["name"] == 'condominio':
                        condominio = elemento['value']
                    elif elemento["name"] == 'iptu':
                        iptu = elemento['value']
                    elif elemento["name"] == 'size':
                        size = elemento['value']
                    elif elemento["name"] == 'rooms':
                        quartos = elemento['value']
                    elif elemento["name"] == 'bathrooms':
                        banheiros = elemento['value']

                price = rs_to_float(apartamento['price'])
                # print(condominio)
                # print(iptu)
                # input("Press Enter to continue...")
                if condominio:
                    condominio = rs_to_float(condominio)
                    total_cost = price + condominio
                if iptu:
                    iptu = rs_to_float(iptu)
                    total_cost += iptu
                if total_cost > price_limit:
                    continue

                apartamentos.append({
                    "title": apartamento['title'],
                    "location": apartamento['location'],
                    "price": apartamento['price'],
                    "total_cost": total_cost,
                    "condominio": condominio,
                    "iptu": iptu,
                    "size": size,
                    "quartos": quartos,
                    "banheiros": banheiros,
                    "link": apartamento['url'],


                })
            except Exception as e:
                print(e)
                continue

    print(apartamentos)
    df = pd.DataFrame(apartamentos)
    return df
    # df.to_excel("apartamentos_2500.xlsx")


# link = input(
#     "Digite o link do site com todos os filtros que deseja menos valores maximos de IPTU e Aluguel: ")
# price_limit = float(input("Digite o preço total que deseja pagar: "))
st.title("Scrapping Imoveis com limite de preco")


st.header("Solucao:")
st.text("A olx infelizmente nao filtra apartamento pelo valor de aluguel+iptu+condominio")
st.text("Pensando nisso criei essa interface para facilitar sua pesquisa")
st.header("Instrucao:")
st.text("1. Entre la olx e filtre ao maximo todos os itens que deseja")
st.text("2. Coloque como valor maximo de aluguel como o valor maximo que pagaria no total(iptu,condominio e alguel)")
st.text("3. Copie o link completo aqui")
st.text("Obs: caso o link termine com: ol=1 apague esse termo")

link = st.text_input("Link:")
valor_maximo = float(st.number_input(
    "Digite o valor total que deseja pagar por mes:"))


if st.button("Confirmar"):
    data = scrapping(link, valor_maximo)
    st.dataframe(data)
