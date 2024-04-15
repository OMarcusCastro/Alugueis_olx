import time
import json
import pandas as pd
import streamlit as st
from selenium.webdriver.common.by import By
from driver.driver_init import create_undetected_driver


def rs_to_float(text):
    number = text.split()[-1]
    number = number.replace(".", "").replace(",", ".")
    return float(number)


def check_title(title):
    keywords = ['apartamento', 'aluga', 'aluguel', 'apto', 'apart', 'apartament', 'apartamento', 'apartamentos', 'casa',
                'kitnet', 'kit', 'loft', 'flat', 'cobertura', 'duplex', 'triplex', 'sobrado', 'condominio', 'residencial', 'residencia', 'residencias']
    return any(word in title.lower() for word in keywords)


def intereable_link(link, page=1):
    return f"{link.split('o=')[0]}o={page}"


def get_last_page_number(pagination_list):
    last_page_element = pagination_list.find_elements(By.TAG_NAME, "a")[-1]
    last_page_link = last_page_element.get_attribute("href")
    return int(last_page_link.split("o=")[-1])


def scrapping(link, price_limit):
    driver = create_undetected_driver(headless=False)
    driver.get(link)
    pagination_list = driver.find_element(By.ID, "listing-pagination")
    last_page_number = get_last_page_number(pagination_list)
    apartamentos = []

    for i in range(1, last_page_number+1):
        time.sleep(0.6)
        driver.get(intereable_link(link, i))
        time.sleep(5)
        dados = json.loads(driver.find_element(
            By.ID, "__NEXT_DATA__").get_attribute("innerHTML"))
        dados = dados['props']['pageProps']['ads']

        for apartamento in dados:
            try:
                total_cost = 0
                condominio, iptu, size, quartos, banheiros = None, None, None, None, None
                for elemento in apartamento['properties']:
                    if elemento["name"] == 'condominio':
                        condominio = rs_to_float(elemento['value'])
                    elif elemento["name"] == 'iptu':
                        iptu = rs_to_float(elemento['value'])
                    elif elemento["name"] == 'size':
                        size = elemento['value']
                    elif elemento["name"] == 'rooms':
                        quartos = elemento['value']
                    elif elemento["name"] == 'bathrooms':
                        banheiros = elemento['value']

                price = rs_to_float(apartamento['price'])
                if condominio:
                    total_cost += condominio
                if iptu:
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

    df = pd.DataFrame(apartamentos)
    return df


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
