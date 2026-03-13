import os
import time
import json
import re
import base64
import random
from datetime import datetime, date
import pandas as pd
import streamlit as st
from selenium.webdriver.common.by import By
from driver.driver_init import create_undetected_driver, _is_docker


def _encode_state(state: dict) -> str:
    """Codifica estado dos filtros em base64 compacto para URL."""
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_state(encoded: str) -> dict:
    """Decodifica estado dos filtros da URL."""
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    raw = base64.urlsafe_b64decode(encoded).decode()
    return json.loads(raw)



def parse_date(value):
    """Converte data da OLX para datetime. Aceita string ISO, timestamp Unix (s ou ms)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:
            return datetime.fromtimestamp(value / 1000)
        elif value > 1e9:
            return datetime.fromtimestamp(value)
    if isinstance(value, str):
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S.%fZ"]:
            try:
                return datetime.strptime(value.split("+")[0].split(".")[0], fmt.split(".")[0])
            except ValueError:
                continue
        try:
            return pd.to_datetime(value)
        except Exception:
            pass
    return None


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


_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_IMPERSONATE_PROFILES = ["chrome110", "chrome116", "chrome120", "chrome124"]


def _fetch_page_curl(url):
    """Busca dados da pagina OLX via curl_cffi (bypassa Cloudflare)."""
    from curl_cffi import requests as curl_requests
    profile = random.choice(_IMPERSONATE_PROFILES)
    resp = curl_requests.get(url, impersonate=profile, headers=_BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text)
    if not match:
        raise Exception("Nao foi possivel extrair dados da pagina OLX")
    return json.loads(match.group(1))


def _wait_for_element(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )


def _scrapping_curl(link, price_limit, progress_callback=None):
    """Scrapping via curl_cffi (para Docker/servidor)."""
    # Limpar ol=1 do link se presente
    link = re.sub(r'[&?]ol=\d+', '', link)

    first_page = _fetch_page_curl(link)
    ads_data = first_page['props']['pageProps']['ads']
    total_ads = first_page['props']['pageProps'].get('totalAds', 0)
    last_page_number = max(1, min((total_ads + 49) // 50, 100))
    apartamentos = []
    erros = 0
    log_msgs = []

    log_msgs.append(f"totalAds={total_ads}, paginas={last_page_number}, ads_pag1={len(ads_data)}")

    for i in range(1, last_page_number + 1):
        if progress_callback:
            progress_callback(i, last_page_number, info=f"totalAds={total_ads} | {len(apartamentos)} coletados")

        if i == 1:
            dados = ads_data
        else:
            time.sleep(random.uniform(2.0, 4.0))
            try:
                page_url = f"{link}&o={i}" if "?" in link else f"{link}?o={i}"
                page_data = _fetch_page_curl(page_url)
                dados = page_data['props']['pageProps']['ads']
                log_msgs.append(f"pag {i}: {len(dados)} ads OK")
            except Exception as e:
                log_msgs.append(f"pag {i}: erro1 - {e}")
                # Retry com backoff
                time.sleep(random.uniform(5.0, 8.0))
                try:
                    page_data = _fetch_page_curl(page_url)
                    dados = page_data['props']['pageProps']['ads']
                    log_msgs.append(f"pag {i}: retry OK, {len(dados)} ads")
                except Exception as e2:
                    erros += 1
                    log_msgs.append(f"pag {i}: retry falhou - {e2}")
                    continue

        for apartamento in dados:
            _parse_apartamento(apartamento, price_limit, apartamentos)

    log_msgs.append(f"TOTAL: {len(apartamentos)} apartamentos, {erros} paginas falharam")
    return pd.DataFrame(apartamentos), log_msgs


def _scrapping_driver(link, price_limit, progress_callback=None):
    """Scrapping via Selenium/undetected-chromedriver (para uso local)."""
    link = re.sub(r'[&?]ol=\d+', '', link)
    driver = create_undetected_driver(headless=False)
    driver.get(link)
    pagination_list = driver.find_element(By.ID, "listing-pagination")
    last_page_number = get_last_page_number(pagination_list)
    apartamentos = []

    for i in range(1, last_page_number + 1):
        if progress_callback:
            progress_callback(i, last_page_number)

        time.sleep(0.6)
        driver.get(f"{link}&o={i}")
        time.sleep(5)
        dados = json.loads(driver.find_element(
            By.ID, "__NEXT_DATA__").get_attribute("innerHTML"))
        dados = dados['props']['pageProps']['ads']

        for apartamento in dados:
            _parse_apartamento(apartamento, price_limit, apartamentos)

    driver.quit()
    return pd.DataFrame(apartamentos), [f"driver: {last_page_number} paginas, {len(apartamentos)} apartamentos"]


def _parse_apartamento(apartamento, price_limit, apartamentos):
    try:
        condominio, size, quartos, banheiros, vagas = None, None, None, None, None
        for elemento in apartamento['properties']:
            if elemento["name"] == 'condominio':
                condominio = rs_to_float(elemento['value'])
            elif elemento["name"] == 'size':
                size = elemento['value']
            elif elemento["name"] == 'rooms':
                quartos = elemento['value']
            elif elemento["name"] == 'bathrooms':
                banheiros = elemento['value']
            elif elemento["name"] == 'garage_spaces':
                vagas = elemento['value']

        price = rs_to_float(apartamento['price'])
        total_cost = price
        if condominio:
            total_cost += condominio
        if total_cost > price_limit:
            return

        image = None
        images = apartamento.get('images') or []
        if isinstance(images, list) and len(images) > 0:
            image = images[0].get('original')

        data_update = apartamento.get('date')
        data_criacao = apartamento.get('origListTime')
        profissional = apartamento.get('professionalAd', False)
        preco_reduzido = bool(apartamento.get('priceReductionBadge'))

        apartamentos.append({
            "title": apartamento['title'],
            "location": apartamento['location'],
            "price": price,
            "total_cost": total_cost,
            "condominio": condominio,
            "size": size,
            "quartos": quartos,
            "banheiros": banheiros,
            "vagas": vagas,
            "ultimo_update": parse_date(data_update),
            "criado_em": parse_date(data_criacao),
            "tipo_anunciante": "Imobiliaria" if profissional else "Particular",
            "preco_reduzido": preco_reduzido,
            "link": apartamento['url'],
            "image": image,
        })
    except Exception as e:
        print(e)


def scrapping(link, price_limit, progress_callback=None):
    if _is_docker():
        return _scrapping_curl(link, price_limit, progress_callback)
    return _scrapping_driver(link, price_limit, progress_callback)


# --- Page config ---
st.set_page_config(
    page_title="Busca de Imoveis OLX",
    page_icon="🏠",
    layout="wide",
)

# --- CSS para alinhar cards da galeria ---
st.markdown("""
<style>
/* Forca colunas da galeria a terem mesma altura */
div[data-testid="stHorizontalBlock"] {
    align-items: stretch;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    height: 100%;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
    height: 100%;
    display: flex;
    flex-direction: column;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
}
/* Botao "Ver anuncio" sempre no rodape do card */
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] > div[data-testid="stLinkButton"] {
    margin-top: auto;
}
</style>
""", unsafe_allow_html=True)

# --- Session state ---
if "dados" not in st.session_state:
    st.session_state.dados = None
if "bairros_version" not in st.session_state:
    st.session_state.bairros_version = 0
if "shared_filters" not in st.session_state:
    st.session_state.shared_filters = None
    # Decodificar estado compartilhado da URL (apenas 1 vez)
    try:
        _raw_s = dict(st.query_params).get("s")
        if _raw_s:
            st.session_state.shared_filters = _decode_state(_raw_s)
    except Exception as e:
        st.warning(f"Erro ao carregar link compartilhado: {e}")

def _get_base_url():
    """Obtem URL base do app server-side."""
    # Railway define RAILWAY_PUBLIC_DOMAIN automaticamente
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        return f"https://{domain}"
    # Outras plataformas podem usar RENDER_EXTERNAL_URL, HEROKU_APP_NAME, etc.
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url
    return "http://localhost:8501"

# --- Header e busca (sempre visivel) ---
st.title("Busca de Imoveis OLX")
st.markdown("A OLX nao filtra pelo valor total (aluguel + condominio). Essa ferramenta resolve isso.")

# --- Tutorial (sempre visivel, colapsavel) ---
expanded = st.session_state.dados is None
with st.expander("Como usar", expanded=expanded):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**1. Pesquise na OLX**")
        st.markdown(
            "Acesse [olx.com.br](https://www.olx.com.br) e busque imoveis para alugar. "
            "Filtre por **regiao/cidade**, **tipo do imovel**, **metragem minima** e "
            "coloque o **valor maximo de aluguel** como o total que voce pagaria (aluguel + condominio)."
        )
    with col2:
        st.markdown("**2. Copie o link**")
        st.markdown(
            "Depois de aplicar todos os filtros desejados na OLX, copie o **link completo** "
            "da barra de enderecos do seu navegador."
        )
    with col3:
        st.markdown("**3. Cole aqui e busque**")
        st.markdown(
            "Cole o link abaixo, defina o valor maximo mensal que aceita pagar e clique em **Buscar**. "
            "Nos calculamos o custo real (aluguel + condominio) de cada imovel para voce."
        )

st.markdown("---")

_sf = st.session_state.shared_filters or {}

link = st.text_input("Link da busca na OLX:", value=_sf.get("link", ""), placeholder="Cole o link da OLX aqui...")
col_val, col_btn = st.columns([3, 1])
with col_val:
    valor_maximo = st.number_input(
        "Valor maximo mensal (R$):",
        min_value=0.0,
        value=float(_sf.get("vm", 3000.0)),
        step=100.0,
        format="%.2f",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    buscar = st.button("Buscar", use_container_width=True, type="primary")

if _sf and st.session_state.dados is None:
    st.info("Link compartilhado carregado! Clique em **Buscar** para ver os resultados.")
elif st.session_state.dados is None and not buscar:
    st.info("**Dica:** caso o link termine com `ol=1`, apague esse trecho antes de colar.")

# --- Scraping ---
if buscar:
    if not link:
        st.error("Por favor, cole o link da busca da OLX.")
    else:
        with st.status("Buscando imoveis...", expanded=True) as status:
            progress_bar = st.progress(0)
            progress_text = st.empty()

            def update_progress(current, total, info=None):
                progress_bar.progress(current / total)
                msg = f"Buscando pagina {current} de {total}..."
                if info:
                    msg += f" ({info})"
                progress_text.text(msg)

            try:
                data, log_msgs = scrapping(link, valor_maximo, progress_callback=update_progress)
                st.session_state.dados = data
                status.update(label="Busca finalizada!", state="complete", expanded=False)
                with st.expander("Log do scraping", expanded=False):
                    for msg in log_msgs:
                        st.text(msg)
            except Exception as e:
                status.update(label="Erro durante a busca", state="error", expanded=True)
                st.error(f"Ocorreu um erro: {e}")
                st.session_state.dados = None

# --- Results ---
if st.session_state.dados is not None:
    df = st.session_state.dados

    if df.empty:
        st.warning("Nenhum imovel encontrado com os filtros informados.")
    else:
        # --- Converter datas para datetime (ja sao datetime, mas garantir pd.Timestamp) ---
        df["update_dt"] = pd.to_datetime(df["ultimo_update"], errors="coerce")
        df["criacao_dt"] = pd.to_datetime(df["criado_em"], errors="coerce")

        # --- Metricas ---
        st.subheader("Resumo")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total encontrados", len(df))
        with col2:
            st.metric("Menor custo total", f"R$ {df['total_cost'].min():,.2f}")
        with col3:
            st.metric("Custo medio", f"R$ {df['total_cost'].mean():,.2f}")
        with col4:
            sizes = pd.to_numeric(df["size"], errors="coerce")
            if sizes.notna().any():
                st.metric("Maior area", f"{sizes.max():.0f} m²")
            else:
                st.metric("Maior area", "N/A")
        with col5:
            vagas_num = pd.to_numeric(df["vagas"], errors="coerce")
            if vagas_num.notna().any():
                st.metric("Media de vagas", f"{vagas_num.mean():.1f}")
            else:
                st.metric("Media de vagas", "N/A")

        st.divider()

        # --- Filtros interativos ---
        st.subheader("Filtros")

        # Linha 1: Custo total e Aluguel
        fcol1, fcol2 = st.columns(2)

        def _clamp_range(sf_key, data_min, data_max):
            """Retorna valor do shared_filters clampado ao range dos dados."""
            if sf_key in _sf:
                v = _sf[sf_key]
                return (max(v[0], data_min), min(v[1], data_max))
            return (data_min, data_max)

        def _shared_multiselect(sf_key, options):
            """Retorna default para multiselect: shared se existir, senao todos."""
            if sf_key in _sf:
                return [o for o in options if o in _sf[sf_key]]
            return options

        with fcol1:
            min_cost = float(df["total_cost"].min())
            max_cost = float(df["total_cost"].max())
            if min_cost < max_cost:
                faixa_custo = st.slider(
                    "Custo total (R$)",
                    min_value=min_cost,
                    max_value=max_cost,
                    value=_clamp_range("ct", min_cost, max_cost),
                    step=50.0,
                )
            else:
                faixa_custo = (min_cost, max_cost)

        with fcol2:
            min_price = float(df["price"].min())
            max_price = float(df["price"].max())
            if min_price < max_price:
                faixa_aluguel = st.slider(
                    "Aluguel (R$)",
                    min_value=min_price,
                    max_value=max_price,
                    value=_clamp_range("al", min_price, max_price),
                    step=50.0,
                )
            else:
                faixa_aluguel = (min_price, max_price)

        # Linha 2: Condominio e Area
        fcol3, fcol4 = st.columns(2)

        with fcol3:
            cond_values = df["condominio"].dropna()
            if len(cond_values) > 0:
                min_cond = float(cond_values.min())
                max_cond = float(cond_values.max())
                if min_cond < max_cond:
                    faixa_cond = st.slider(
                        "Condominio (R$)",
                        min_value=min_cond,
                        max_value=max_cond,
                        value=_clamp_range("cd", min_cond, max_cond),
                        step=50.0,
                    )
                else:
                    faixa_cond = (min_cond, max_cond)
            else:
                faixa_cond = None

        with fcol4:
            sizes = pd.to_numeric(df["size"], errors="coerce")
            if sizes.notna().any():
                min_size = float(sizes.min())
                max_size = float(sizes.max())
                if min_size < max_size:
                    faixa_area = st.slider(
                        "Area (m²)",
                        min_value=min_size,
                        max_value=max_size,
                        value=_clamp_range("ar", min_size, max_size),
                        step=5.0,
                    )
                else:
                    faixa_area = (min_size, max_size)
            else:
                faixa_area = None

        # Linha 3: Quartos, Banheiros, Vagas e Localizacao
        fcol5, fcol6, fcol7, fcol8 = st.columns(4)

        with fcol5:
            quartos_opcoes = sorted(df["quartos"].dropna().unique().tolist())
            if quartos_opcoes:
                quartos_sel = st.multiselect("Quartos", options=quartos_opcoes, default=_shared_multiselect("q", quartos_opcoes))
            else:
                quartos_sel = []

        with fcol6:
            banheiros_opcoes = sorted(df["banheiros"].dropna().unique().tolist())
            if banheiros_opcoes:
                banheiros_sel = st.multiselect("Banheiros", options=banheiros_opcoes, default=_shared_multiselect("b", banheiros_opcoes))
            else:
                banheiros_sel = []

        with fcol7:
            vagas_opcoes = sorted(df["vagas"].dropna().unique().tolist())
            if vagas_opcoes:
                vagas_sel = st.multiselect("Vagas", options=vagas_opcoes, default=_shared_multiselect("v", vagas_opcoes))
            else:
                vagas_sel = []

        with fcol8:
            locais = sorted(df["location"].dropna().unique().tolist())
            if locais:
                # Carregar bairros salvos do localStorage
                from streamlit_js_eval import streamlit_js_eval
                bv = st.session_state.bairros_version

                # Shared filters tem prioridade sobre localStorage
                if "loc" in _sf:
                    default_locais = [l for l in locais if l in _sf["loc"]]
                    locais_sel = st.multiselect("Localizacao", options=locais, default=default_locais, key="locais_shared")
                else:
                    bairros_salvos_json = streamlit_js_eval(js_expressions="localStorage.getItem('bairros_salvos')", key=f"load_bairros_{bv}")

                    usar_salvos = st.checkbox("Usar bairros salvos")
                    if usar_salvos and bairros_salvos_json:
                        salvos = json.loads(bairros_salvos_json)
                        default_locais = [l for l in locais if l in salvos]
                    else:
                        default_locais = locais

                    multiselect_key = f"locais_{'salvos' if usar_salvos else 'todos'}"
                    locais_sel = st.multiselect("Localizacao", options=locais, default=default_locais, key=multiselect_key)

                if st.button("Salvar bairros"):
                    bairros_json = json.dumps(locais_sel)
                    st.session_state.bairros_version += 1
                    streamlit_js_eval(js_expressions=f"localStorage.setItem('bairros_salvos', '{bairros_json}')", key=f"save_bairros_{st.session_state.bairros_version}")
                    st.success(f"Salvos {len(locais_sel)} bairros no navegador!")
                    st.rerun()
            else:
                locais_sel = []

        # Linha 4: Ultimo update, Data criacao, Tipo anunciante, Preco reduzido
        fcol9, fcol9b, fcol10, fcol11 = st.columns(4)

        with fcol9:
            updates_validos = df["update_dt"].dropna()
            if len(updates_validos) > 0:
                min_upd = updates_validos.min().date()
                upd_val = min_upd
                if "upd" in _sf:
                    try:
                        upd_val = date.fromisoformat(_sf["upd"])
                    except Exception:
                        pass
                data_update_filtro = st.date_input(
                    "Ultimo update a partir de",
                    value=upd_val,
                )
            else:
                data_update_filtro = None

        with fcol9b:
            criacao_validas = df["criacao_dt"].dropna()
            if len(criacao_validas) > 0:
                min_cri = criacao_validas.min().date()
                cri_val = min_cri
                if "cri" in _sf:
                    try:
                        cri_val = date.fromisoformat(_sf["cri"])
                    except Exception:
                        pass
                data_criacao_filtro = st.date_input(
                    "Criado a partir de",
                    value=cri_val,
                )
            else:
                data_criacao_filtro = None

        with fcol10:
            tipos_anunciante = sorted(df["tipo_anunciante"].dropna().unique().tolist())
            if tipos_anunciante:
                tipo_sel = st.multiselect("Tipo de anunciante", options=tipos_anunciante, default=_shared_multiselect("tipo", tipos_anunciante))
            else:
                tipo_sel = []

        with fcol11:
            filtro_reduzido = st.checkbox("Somente com preco reduzido", value=_sf.get("red", False))
            remover_duplicatas = st.checkbox("Remover duplicatas (mesmo titulo)", value=_sf.get("dup", False))

        # --- Ordenacao ---
        st.subheader("Ordenacao")
        ocol1, ocol2 = st.columns(2)
        _sort_options = ["Custo Total", "Aluguel", "Condominio", "Area", "Ultimo Update", "Data de Criacao"]
        _sort_default = _sf.get("sort", "Custo Total")
        _sort_idx = _sort_options.index(_sort_default) if _sort_default in _sort_options else 0
        _ord_options = ["Crescente", "Decrescente"]
        _ord_default = _sf.get("ord", "Crescente")
        _ord_idx = _ord_options.index(_ord_default) if _ord_default in _ord_options else 0
        with ocol1:
            ordenar_por = st.selectbox("Ordenar por", _sort_options, index=_sort_idx)
        with ocol2:
            ordem = st.radio("Ordem", _ord_options, index=_ord_idx, horizontal=True)

        col_map = {
            "Custo Total": "total_cost",
            "Aluguel": "price",
            "Condominio": "condominio",
            "Area": "size",
            "Ultimo Update": "update_dt",
            "Data de Criacao": "criacao_dt",
        }
        ascending = ordem == "Crescente"

        # --- Aplicar filtros ---
        df_filtrado = df[
            (df["total_cost"] >= faixa_custo[0]) &
            (df["total_cost"] <= faixa_custo[1]) &
            (df["price"] >= faixa_aluguel[0]) &
            (df["price"] <= faixa_aluguel[1])
        ]

        if faixa_cond is not None:
            df_filtrado = df_filtrado[
                (df_filtrado["condominio"].isna()) |
                ((df_filtrado["condominio"] >= faixa_cond[0]) &
                 (df_filtrado["condominio"] <= faixa_cond[1]))
            ]

        if faixa_area is not None:
            sizes_filtrado = pd.to_numeric(df_filtrado["size"], errors="coerce")
            df_filtrado = df_filtrado[
                (sizes_filtrado.isna()) |
                ((sizes_filtrado >= faixa_area[0]) &
                 (sizes_filtrado <= faixa_area[1]))
            ]

        if quartos_sel:
            df_filtrado = df_filtrado[df_filtrado["quartos"].isin(quartos_sel)]
        if banheiros_sel:
            df_filtrado = df_filtrado[df_filtrado["banheiros"].isin(banheiros_sel)]
        if vagas_sel:
            df_filtrado = df_filtrado[
                df_filtrado["vagas"].isna() | df_filtrado["vagas"].isin(vagas_sel)
            ]
        if locais_sel:
            df_filtrado = df_filtrado[df_filtrado["location"].isin(locais_sel)]

        if data_update_filtro is not None:
            upd_inicio = pd.Timestamp(data_update_filtro)
            df_filtrado = df_filtrado[
                (df_filtrado["update_dt"].isna()) |
                (df_filtrado["update_dt"] >= upd_inicio)
            ]

        if data_criacao_filtro is not None:
            cri_inicio = pd.Timestamp(data_criacao_filtro)
            df_filtrado = df_filtrado[
                (df_filtrado["criacao_dt"].isna()) |
                (df_filtrado["criacao_dt"] >= cri_inicio)
            ]

        if tipo_sel:
            df_filtrado = df_filtrado[df_filtrado["tipo_anunciante"].isin(tipo_sel)]

        if filtro_reduzido:
            df_filtrado = df_filtrado[df_filtrado["preco_reduzido"] == True]

        if remover_duplicatas:
            df_filtrado = df_filtrado.sort_values("total_cost", ascending=True, na_position="last")
            df_filtrado = df_filtrado.drop_duplicates(subset="title", keep="first")

        # --- Aplicar ordenacao ---
        sort_col = col_map[ordenar_por]
        if sort_col == "size":
            df_filtrado = df_filtrado.copy()
            df_filtrado["_size_num"] = pd.to_numeric(df_filtrado["size"], errors="coerce")
            df_filtrado = df_filtrado.sort_values("_size_num", ascending=ascending, na_position="last")
            df_filtrado = df_filtrado.drop(columns=["_size_num"])
        else:
            df_filtrado = df_filtrado.sort_values(sort_col, ascending=ascending, na_position="last")

        st.caption(f"Exibindo {len(df_filtrado)} de {len(df)} imoveis")

        # --- Compartilhar ---
        current_state = {
            "link": link,
            "vm": valor_maximo,
            "ct": list(faixa_custo),
            "al": list(faixa_aluguel),
            "q": quartos_sel,
            "b": banheiros_sel,
            "v": vagas_sel,
            "loc": locais_sel,
            "tipo": tipo_sel,
            "red": filtro_reduzido,
            "dup": remover_duplicatas,
            "sort": ordenar_por,
            "ord": ordem,
        }
        if faixa_cond is not None:
            current_state["cd"] = list(faixa_cond)
        if faixa_area is not None:
            current_state["ar"] = list(faixa_area)
        if data_update_filtro is not None:
            current_state["upd"] = data_update_filtro.isoformat()
        if data_criacao_filtro is not None:
            current_state["cri"] = data_criacao_filtro.isoformat()

        encoded = _encode_state(current_state)

        # --- Download planilha + Compartilhar ---
        colunas_ocultas = ["image", "update_dt", "criacao_dt"]
        colunas_tabela = [c for c in df_filtrado.columns if c not in colunas_ocultas]
        csv_data = df_filtrado[colunas_tabela].to_csv(index=False).encode("utf-8")

        dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 3])
        with dl_col1:
            st.download_button(
                label="Baixar planilha (CSV)",
                data=csv_data,
                file_name="imoveis_olx.csv",
                mime="text/csv",
            )
        with dl_col2:
            compartilhar = st.button("Compartilhar busca", type="secondary")
        with dl_col3:
            ver_tabela = st.checkbox("Ver como tabela")

        if compartilhar:
            share_url = f"{_get_base_url()}?s={encoded}"
            st.success("Compartilhe este link com seus amigos:")
            st.code(share_url, language=None)

        if ver_tabela:
            st.dataframe(
                df_filtrado[colunas_tabela],
                column_config={
                    "title": st.column_config.TextColumn("Titulo", width="large"),
                    "location": st.column_config.TextColumn("Localizacao", width="medium"),
                    "price": st.column_config.NumberColumn("Aluguel (R$)", format="R$ %.2f"),
                    "total_cost": st.column_config.NumberColumn("Custo Total (R$)", format="R$ %.2f"),
                    "condominio": st.column_config.NumberColumn("Condominio (R$)", format="R$ %.2f"),
                    "size": st.column_config.TextColumn("Area (m²)"),
                    "quartos": st.column_config.TextColumn("Quartos"),
                    "banheiros": st.column_config.TextColumn("Banheiros"),
                    "vagas": st.column_config.TextColumn("Vagas"),
                    "ultimo_update": st.column_config.TextColumn("Ultimo Update"),
                    "criado_em": st.column_config.TextColumn("Criado em"),
                    "tipo_anunciante": st.column_config.TextColumn("Anunciante"),
                    "preco_reduzido": st.column_config.CheckboxColumn("Preco Reduzido"),
                    "link": st.column_config.LinkColumn("Link", display_text="Ver anuncio"),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            # --- Galeria ---
            cols_per_row = 3
            rows = [df_filtrado.iloc[i:i+cols_per_row] for i in range(0, len(df_filtrado), cols_per_row)]
            for row_data in rows:
                cols = st.columns(cols_per_row)
                for idx, (_, item) in enumerate(row_data.iterrows()):
                    with cols[idx]:
                        with st.container(border=True):
                            img_url = item.get("image")
                            if img_url:
                                st.image(img_url, use_column_width=True)
                            else:
                                st.markdown("*Sem imagem disponivel*")

                            titulo = item['title']
                            if item.get("preco_reduzido"):
                                titulo = f"🔻 {titulo}"
                            st.markdown(f"**{titulo}**")
                            st.caption(f"{item['location']} | {item.get('tipo_anunciante', '')}")

                            mc1, mc2 = st.columns(2)
                            with mc1:
                                st.metric("Custo Total", f"R$ {item['total_cost']:,.2f}")
                            with mc2:
                                st.metric("Aluguel", f"R$ {item['price']:,.2f}")

                            detalhes = []
                            if item.get("quartos"):
                                detalhes.append(f"{item['quartos']} quarto(s)")
                            if item.get("banheiros"):
                                detalhes.append(f"{item['banheiros']} banheiro(s)")
                            if item.get("vagas"):
                                detalhes.append(f"{item['vagas']} vaga(s)")
                            if item.get("size"):
                                detalhes.append(f"{item['size']} m²")
                            if item.get("condominio"):
                                detalhes.append(f"Cond: R$ {item['condominio']:,.2f}")
                            if detalhes:
                                st.caption(" | ".join(detalhes))

                            datas_info = []
                            if item.get("criado_em"):
                                datas_info.append(f"Criado: {item['criado_em']}")
                            if item.get("ultimo_update"):
                                datas_info.append(f"Update: {item['ultimo_update']}")
                            if datas_info:
                                st.caption(" | ".join(datas_info))

                            st.link_button("Ver anuncio", item["link"], use_container_width=True)
