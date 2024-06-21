import sys
import requests
import time
import json
import datetime
import hashlib
import psutil

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon

def close_chrome():
    for proc in psutil.process_iter(['pid', 'name']):
        # Check if the process name is 'chrome'
        if 'chrome' in proc.info['name']:
            p = psutil.Process(proc.info['pid'])
            # Terminate the process
            p.terminate()
            
# Load the configuration from the JSON file
with open('config.json') as json_file:
    config = json.load(json_file)

user_path = config['user_path']
phone_number = config['phone_number']
min_price = config['min_price']
max_price = config['max_price']
min_discount = config['min_discount']

def send_to_discord(webhook_url, name, price_value, discount_value, old_price_value, image_url):
    profit = round(old_price_value - price_value, 1)
    profit_skinport = round(profit - (profit * 0.12), 1)  # calculate with Skinport's 12% fee
    
    data = {
        "content": "roleidfromdiscordserver",
        "embeds": [{
            "title": f"**{name}**",
            "color": 9109759,  
            "fields": [{
                "name": "",
                "value": f"```\nCurrent Price:      {price_value}€\nSuggested Price: {old_price_value}€\n\nDiscount:        {discount_value}%\nProfit:          {profit}€\nProfit on Skinport:  {profit_skinport}€\n```",
                "inline": True
            }],
            "thumbnail": {"url": image_url},
            "footer": {
                "text": "SniperBot by Ent0x",
                "icon_url": "iconimagelink"
            },
            "timestamp": str(datetime.datetime.now())
        }]
    }

    response = requests.post(
        webhook_url, data=json.dumps(data),
        headers={'Content-Type': 'application/json'}
    )

    if response.status_code != 204:
        raise ValueError(
            f'Request to Discord returned an error {response.status_code}, the response is:\n{response.text}'
        )


class GUI(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SkinSniper by ent0x")
        self.setFixedSize(233, 200)  
        self.price_max_input = QLineEdit(self)
        self.price_min_input = QLineEdit(self)
        self.discount_input = QLineEdit(self)
        self.start_button = QPushButton('Start', self)

        self.price_min_input.setText(str(min_price))
        self.price_max_input.setText(str(max_price))
        self.discount_input.setText(str(min_discount))
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel('Min Price:'))
        layout.addWidget(self.price_min_input)
        layout.addWidget(QLabel('Max Price:'))  
        layout.addWidget(self.price_max_input)
        layout.addWidget(QLabel('Min Discount:'))
        layout.addWidget(self.discount_input)
        layout.addWidget(self.start_button)

        self.setLayout(layout)

        self.start_button.clicked.connect(self.start_search)

    def start_search(self):
        min_price = float(self.price_min_input.text())
        max_price = float(self.price_max_input.text())  
        min_discount = float(self.discount_input.text())
        main(min_price, max_price, min_discount)

def safe_find_elements(driver, by, value):
    try:
        return driver.find_elements(by, value)
    except StaleElementReferenceException:
        return safe_find_elements(driver, by, value)

# Message indicating that the item has changed price or has already been sold!
def is_message_active(driver):
    try:
        driver.find_element(By.CSS_SELECTOR, ".MessageContainer.MessageContainer--isActive")
        return True
    except NoSuchElementException:
        return False
    
def get_element_hash(name_text, image_url):
    # Use attributes that you believe are unique to each element
    hash_input = name_text + image_url
    return hashlib.sha1(hash_input.encode()).hexdigest()


def main(min_price, max_price, min_discount):
    service = Service(executable_path='chromedriver.exe')
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--disable-infobars')
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-data-dir={user_path}")
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1080, 800)
    driver.get("https://skinport.com/en/market?sort=date&order=desc")
  
    time.sleep(5)

    # Click on the "Live" button
    live_button = driver.find_element(By.CSS_SELECTOR, "div.CatalogHeader-tooltipLive > button.LiveBtn")
    live_button.click()
    time.sleep(0.5)
    driver.set_window_size(1030, 920)
    time.sleep(2)

    webhook_url = 'webhooklink'

    processed_elements_hashes = set()
    
    while True:  # Infinite Loop
        try:
            all_items = safe_find_elements(driver, By.CSS_SELECTOR, "div.CatalogPage-item.CatalogPage-item--grid")
            old_prices = safe_find_elements(driver, By.CSS_SELECTOR, "div.ItemPreview-oldPrice")
            prices = safe_find_elements(driver, By.CSS_SELECTOR, "div.ItemPreview-priceValue")
            buttons = safe_find_elements(driver, By.CSS_SELECTOR, "button.ItemPreview-mainAction")
            names = safe_find_elements(driver, By.CSS_SELECTOR, "div.ItemPreview-itemName")
            image_elements = safe_find_elements(driver, By.CSS_SELECTOR, "div.ItemPreview-itemImage > img")
            titles = safe_find_elements(driver, By.CSS_SELECTOR, "div.ItemPreview-itemTitle")
            item_ids = safe_find_elements(driver, By.CSS_SELECTOR, "div.CatalogPage-item.CatalogPage-item--grid")
        except Exception as e:
            print(f"Error trying to find elements: {e}")
            continue
        elements = list(zip(old_prices, prices, buttons, names, image_elements, titles, all_items))
        elements = [element for element in elements if get_element_hash(element[3].text, element[4].get_attribute('src')) not in processed_elements_hashes]

        for old_price, price, button, name, image_element, title, _ in elements:
            price_value = price.text.split()[0].replace('€', '').replace(',', '.')  # Extract only the price value
            old_price_value = old_price.text.replace('Suggested Price ', '').replace(',', '.').replace('€', '').replace('\xa0', '')  # Extract the old price value
            image_url = image_element.get_attribute('src')
            name_text = f"{title.text} - {name.text}"  # name in text, if not, won't show in webhook.

            elements = elements[:15]

            try:
                price_value = float(price_value)
                old_price_value = float(old_price_value)
                discount_value = round(((old_price_value - price_value) / old_price_value) * 100, 1)
            except ValueError:
                continue  # If it fails, ignore this item and move on to the next one
                        
            if min_price < price_value < max_price and discount_value > min_discount:
                button.click()  
                if is_message_active(driver):
                    continue  # Ignore this item and move on to the next one in the loop if the message appears
                else:
                    driver.get("https://skinport.com/en/cart")  # Go to the cart if the message does not appear
                    break  # Exit the loop
            else:
                processed_elements_hashes.add(get_element_hash(name.text, image_url))  # if not found, add and loop back
                        
        else:
            time.sleep(2)
            continue

        break

    time.sleep(0.9)
    # Set to not throw an error if not found
    tradelock_checkbox = None  
    cancellation_checkbox = None  
    try:  
        tradelock_checkbox = driver.find_element(By.NAME, "tradelock")
        tradelock_checkbox.click()
    except NoSuchElementException:
        pass
    cancellation_checkbox = driver.find_element(By.NAME, "cancellation")
    cancellation_checkbox.click()

    if tradelock_checkbox is not None and tradelock_checkbox.is_selected() and cancellation_checkbox is not None and cancellation_checkbox.is_selected():
        # Click on the "Proceed to Checkout" button
        checkout_button = driver.find_element(By.CSS_SELECTOR, "button.SubmitButton.CartSummary-checkoutBtn.SubmitButton--isFull")
        time.sleep(0.2)
        checkout_button.click()
        time.sleep(0.7)

        phone_input = driver.find_element(By.CSS_SELECTOR, ".adyen-checkout__input.adyen-checkout-input.adyen-checkout-input--phone-number")
        phone_input.send_keys(phone_number)
        confirm_button = driver.find_element(By.CSS_SELECTOR, "button.adyen-checkout__button.adyen-checkout__button--pay")
        time.sleep(0.1)
        confirm_button.click()
        send_to_discord(webhook_url, name_text, price_value, discount_value, old_price_value, image_url)
        time.sleep(55)

app = QApplication([])
app.setWindowIcon(QIcon('pngegg.png'))  # App icon
close_chrome()
gui = GUI()
gui.show()
sys.exit(app.exec_())
