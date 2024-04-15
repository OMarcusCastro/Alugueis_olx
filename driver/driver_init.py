import os
import time

import pandas as pd

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import undetected_chromedriver as uc

def create_undetected_driver():
    driver = uc.Chrome(headless=False)
    return driver

def create_driver():
# Create ChromeOptions instance
    ROOT_FOLDER = os.path.dirname(os.path.abspath(__file__))
    CHROMEDRIVE_EXEC = Path(ROOT_FOLDER)/"chromedriver.exe"
    print('path driver: ',CHROMEDRIVE_EXEC ,"#"*30)
    options = webdriver.ChromeOptions()


    # Adding argument to disable the AutomationControlled flag
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Exclude the collection of enable-automation switches
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Turn-off userAutomationExtension
    options.add_experimental_option("useAutomationExtension", False)

    chrome_service = Service(executable_path=CHROMEDRIVE_EXEC)
    # Setting the driver path and requesting a page
    driver = webdriver.Chrome(service=chrome_service,options=options)

    # Changing the property of the navigator value for webdriver to undefined
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def espera_elemento_presente(by, value,driver,TIME_TO_WAIT=10):

    return WebDriverWait(driver,TIME_TO_WAIT).until(
        EC.presence_of_element_located((by, value))
    )


if __name__ == '__main__':
    driver=create_driver()
    driver.get('https://www.google.com')
    time.sleep(1)
    espera_elemento_presente(By.ID,'teste',driver)
    print('teste')
    driver.driver.quit()
    print('teste')
