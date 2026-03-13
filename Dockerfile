FROM python:3.11-slim

RUN apt-get update && apt-get install -y wget gnupg2 \
    && wget -q -O /usr/share/keyrings/google-chrome.gpg https://dl.google.com/linux/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+') \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/$(google-chrome --version | grep -oP '[\d.]+')/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    || wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$(google-chrome --version | grep -oP '[\d.]+')/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    ; apt-get update && apt-get install -y unzip \
    && unzip -o /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver* /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "scrapping_v2.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
