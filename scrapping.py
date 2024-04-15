import requests


r = requests.get("https://www.olx.com.br/imoveis/aluguel/estado-ce/fortaleza-e-regiao/fortaleza?bas=1&ps=1000&q=apartamento&ros=1&sd=2695&sd=2726&sd=2715&sd=2740&sd=2708&sd=2744&sd=2690&sd=2705&sd=2724&sd=2755&sd=2725&sd=2747&sd=2752&sd=2692&sd=2679&sd=2681&ss=1")

print(r.text)
