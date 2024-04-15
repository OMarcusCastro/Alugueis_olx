import time
import os

import pandas as pd

from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from driver.driver_init import create_undetected_driver, espera_elemento_presente
import json
link = input(
    "Digite o link do site com todos os filtros que deseja menos valores maximos de IPTU e Aluguel: ")
price_limit = float(input("Digite o preço total que deseja pagar: "))


current_page = 1
# link = "https://www.olx.com.br/imoveis/aluguel/estado-ce/fortaleza-e-regiao/fortaleza?bas=1&ps=1000&q=apartamento&ros=1&sd=2695&sd=2726&sd=2715&sd=2740&sd=2708&sd=2744&sd=2690&sd=2705&sd=2724&sd=2755&sd=2725&sd=2747&sd=2752&sd=2692&sd=2679&sd=2681&ss=1&o=1"
# link = "https://www.olx.com.br/imoveis/aluguel/estado-ce/fortaleza-e-regiao/fortaleza?bas=1&pe=3500&ps=1000&q=apartamento&ros=1&sd=2695&sd=2726&sd=2715&sd=2740&sd=2708&sd=2744&sd=2690&sd=2705&sd=2724&sd=2755&sd=2725&sd=2747&sd=2752&sd=2692&sd=2679&sd=2681&ss=1"
driver = create_undetected_driver()
driver.get(link)
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
df.to_excel("apartamentos_2500.xlsx")


# def intereable_link(link, page=1):
#     link = link.split("o=")[0]
#     new_link = f"{link}o={page}"
#     return new_link


# def check_title(title):
#     keywords = ['apartamento', 'aluga', 'aluguel', 'apto', 'apart', 'apartament', 'apartamento', 'apartamentos', 'casa',
#                 'kitnet', 'kit', 'loft', 'flat', 'cobertura', 'duplex', 'triplex', 'sobrado', 'condominio', 'residencial', 'residencia', 'residencias',]
#     if not any(word in title.lower() for word in keywords):
#         return False
#     return True


# def get_price(text):
#     price = text.split()[-1]
#     price = price.replace(".", "")
#     price = price.replace(",", ".")
#     price = float(price)

#     return price


# def get_last_page_number(pagination_list):
#     last_page_element = pagination_list.find_elements(
#         By.TAG_NAME, "a")[-1]

#     last_page_link = last_page_element.get_attribute("href")
#     number = int(last_page_link.split("o=")[-1])
#     return number


# espera_elemento_presente(
#     By.CSS_SELECTOR, "section[class='olx-ad-card olx-ad-card--horizontal']", driver, 10)

# apartments_list = driver.find_elements(
#     By.CSS_SELECTOR, "section[class='olx-ad-card olx-ad-card--horizontal']")

# # input("Press Enter to continue...")
# pagination_list = driver.find_element(
#     By.ID, "listing-pagination")
# last_page_number = get_last_page_number(pagination_list)
# print(f"Last page number: {last_page_number}")


# # input("Press Enter to continue...")

# id_product = 1

# body = driver.find_element(By.TAG_NAME, "body")
# apartment_data = {}
# for i in range(1, last_page_number+1):
#     time.sleep(0.6)
#     # try:
#     driver.get(intereable_link(link, i))

#     espera_elemento_presente(
#         By.CSS_SELECTOR, "section[class='olx-ad-card olx-ad-card--horizontal']", driver, 10)
#     apartments_list = driver.find_elements(
#         By.CSS_SELECTOR, "section[class='olx-ad-card olx-ad-card--horizontal']")
#     print(f"Page: {i}")

#     for apartment in apartments_list:
#         while True:
#             body.send_keys(Keys.ARROW_DOWN)
#             a = input("Press Enter to continue...")
#             if a == "q":
#                 break

#         time.sleep(0.6)
#         # try:
#         price = apartment.find_element(
#             By.CSS_SELECTOR, "h3[class='olx-text olx-text--body-large olx-text--block olx-text--semibold olx-ad-card__price']")

#         price = get_price(price.text)

#         try:
#             details_price = apartment.find_element(
#                 By.CSS_SELECTOR, "div[class='olx-ad-card__priceinfo olx-ad-card__priceinfo--horizontal']")

#             details_price_list = details_price.text.split("\n")
#             condominium_price = get_price(
#                 list(filter(lambda x: "Condomínio" in x, details_price_list))[0])

#             iptu_price = get_price(
#                 list(filter(lambda x: "IPTU" in x, details_price_list))[0])
#             total_cost = price + condominium_price+iptu_price
#         except:
#             condominium_price = None
#             iptu_price = None
#             total_cost = price

#         if total_cost > price_limit:
#             continue

#         link_element = apartment.find_element(
#             By.CSS_SELECTOR, "a[data-ds-component='DS-NewAdCard-Link']")
#         link_text = link_element.get_attribute("href")
#         titile = apartment.find_element(
#             By.CSS_SELECTOR, "h2[data-ds-component='DS-Text']").text

#         if not check_title(titile):
#             print("Title not accepted", titile, "\n\n")
#             continue
#         apartment_data[id_product] = {
#             "link": link_text,
#             "title": titile,
#             "price": price,
#             "condominium": condominium_price,
#             "iptu": iptu_price
#         }
#         # input("Press Enter to continue...")
#         print(apartment_data[id_product])
#         id_product += 1
#         print(f"Link: {link_text}")
#         print(f"Title: {titile}")
#         print(f"Price: {price}")
#         print(f"Condominium: {condominium_price}")
#         print(f"IPTU: {iptu_price}")
#         print("\n\n")
#         time.sleep(0.4)
#         # input("Press Enter to continue...")
#         # except Exception as e:
#         #     print(e, "product")
#         #     continue
#     # except Exception as e:
#     #     print(e, "pagination")
#     #     continue
