import time
import requests
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ==========================================
# ⚙️ AYARLAR
# ==========================================
TELEGRAM_BOT_TOKEN = "8442781722:AAFLT1kqp_0Wgao0Foav6GCCE0Rrf_X0CZ8"
SHEET_ADI = "EtkinlikTakip"

# ==========================================
# 📊 GOOGLE SHEETS & KULLANICI YÖNETİMİ
# ==========================================
def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # GitHub'da mı çalışıyoruz Localde mi? Kontrolü
    if os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    else:
        # GitHub Secret'tan okuma (Birazdan ayarlayacağız)
        creds_json = json.loads(os.environ.get("G_SHEET_CREDS"))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        
    client = gspread.authorize(creds)
    return client

def kullanicilari_guncelle(client):
    """Telegram'dan /start diyenleri kaydeder"""
    print("👥 Yeni kullanıcılar kontrol ediliyor...")
    try:
        sheet = client.open(SHEET_ADI).worksheet("Kullanicilar")
        kayitli_id_listesi = sheet.col_values(1) # A sütununu çek
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        response = requests.get(url).json()
        
        if "result" in response:
            for update in response["result"]:
                if "message" in update and "text" in update["message"]:
                    mesaj = update["message"]["text"]
                    chat_id = str(update["message"]["chat"]["id"])
                    kullanici_adi = update["message"]["from"].get("first_name", "Bilinmiyor")
                    
                    if mesaj == "/start" and chat_id not in kayitli_id_listesi:
                        sheet.append_row([chat_id, kullanici_adi, time.strftime("%Y-%m-%d")])
                        kayitli_id_listesi.append(chat_id)
                        print(f"   ➕ Yeni Abone: {kullanici_adi}")
        return kayitli_id_listesi
    except Exception as e:
        print(f"⚠️ Kullanıcı güncelleme hatası: {e}")
        return []

def link_kaydet(client, link, baslik, site):
    sheet = client.open(SHEET_ADI).worksheet("Etkinlikler")
    sheet.append_row([link, baslik, site, time.strftime("%Y-%m-%d %H:%M")])

def linkleri_getir(client):
    try:
        sheet = client.open(SHEET_ADI).worksheet("Etkinlikler")
        return sheet.col_values(1)
    except: return []

# ==========================================
# 📨 TOPLU GÖNDERİM
# ==========================================
def herkese_gonder(abone_listesi, site, baslik, tarih, link, gorsel_url):
    print(f"📤 {len(abone_listesi)} kişiye gönderiliyor: {baslik[:30]}...")
    
    caption = (
        f"📢 <b>{site} - Yeni Etkinlik!</b>\n\n"
        f"🎯 <b>{baslik}</b>\n"
        f"📅 {tarih}\n\n"
        f"🔗 <a href='{link}'>Başvuru ve Detaylar</a>"
    )
    
    for chat_id in abone_listesi:
        if not chat_id.isdigit(): continue 
        payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
        try:
            if gorsel_url and gorsel_url.startswith("http"):
                payload['photo'] = gorsel_url
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto", data=payload)
            else:
                payload['text'] = caption
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=payload)
            time.sleep(0.2) 
        except: pass

# ==========================================
# 🕷️ TARAYICI & SCRAPING
# ==========================================
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

# --- SCRAPING FONKSİYONLARI ---
def scrape_anbean(driver, client, mevcut, aboneler):
    print("\n🔍 Anbean Taranıyor...")
    try:
        driver.get("https://anbeankampus.co/etkinlikler/")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for kart in soup.find_all("div", class_="mini-eventCard")[:5]:
            link = "https://anbeankampus.co" + kart.find("a")['href']
            if link in mevcut: continue
            
            baslik = kart.find("h6").text.strip()
            img = kart.find("img", class_="mini-eventCard-HeaderImage")
            gorsel = "https://anbeankampus.co" + img['src'] if img else None
            
            tarih = "Belirtilmemiş"
            for d in kart.find_all("div", class_="mini-eventCard-dateItem"):
                if "Son" in d.text: tarih = d.text.strip()
                
            herkese_gonder(aboneler, "Anbean", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Anbean")
    except Exception as e: print(f"Anbean Hata: {e}")

def scrape_toptalent(driver, client, mevcut, aboneler):
    print("\n🔍 Toptalent Taranıyor...")
    try:
        driver.get("https://toptalent.co/etkinlikler")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for kart in soup.find_all("a", class_="position")[:5]:
            link = kart['href']
            if not link.startswith("http"): link = "https://toptalent.co" + link
            if link in mevcut: continue
            
            baslik = kart.find("h5").text.strip()
            img = kart.find("img")
            gorsel = "https://toptalent.co" + img['src'] if img else None
            
            badge = kart.find("span", class_="badge-circle-green")
            tarih = f"Kalan: {badge.text.strip()}" if badge else "Sitede"
            
            herkese_gonder(aboneler, "Toptalent", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Toptalent")
    except Exception as e: print(f"Toptalent Hata: {e}")

def scrape_youthall(driver, client, mevcut, aboneler):
    print("\n🔍 Youthall Taranıyor...")
    try:
        driver.get("https://www.youthall.com/tr/events/")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for kart in soup.find_all("div", class_="events")[:5]:
            link = "https://www.youthall.com" + kart.find("a")['href']
            if link in mevcut: continue
            
            baslik = kart.find("h2").text.strip()
            img_div = kart.find("div", class_="events__img")
            img = img_div.find("img") if img_div else None
            gorsel = "https://www.youthall.com" + img['src'] if img else None
            tarih = kart.find("div", class_="events__content__details").text.strip() if kart.find("div", class_="events__content__details") else "Detaylar Sitede"

            herkese_gonder(aboneler, "Youthall", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Youthall")
    except Exception as e: print(f"Youthall Hata: {e}")

# ==========================================
# 🏁 MAIN
# ==========================================
if __name__ == "__main__":
    print("🚀 Bot Başladı...")
    try:
        client = get_google_client()
        aboneler = kullanicilari_guncelle(client)
        if not aboneler: print("⚠️ Abone bulunamadı.")
        
        mevcut = linkleri_getir(client)
        driver = get_driver()
        
        scrape_anbean(driver, client, mevcut, aboneler)
        scrape_toptalent(driver, client, mevcut, aboneler)
        scrape_youthall(driver, client, mevcut, aboneler)
        
        driver.quit()
        print("✅ İşlem Bitti.")
    except Exception as e:
        print(f"🔥 Kritik Hata: {e}")