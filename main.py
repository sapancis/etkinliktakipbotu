import time
import requests
import gspread
import os
import json
import random # Rastgelelik için eklendi
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from fake_useragent import UserAgent # Yeni eklendi

# ==========================================
# ⚙️ AYARLAR
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ADI = "EtkinlikTakip"

# ==========================================
# 🛠 YARDIMCI FONKSİYONLAR
# ==========================================
def rastgele_bekle(min_s=3, max_s=7):
    """İnsan gibi davranmak için rastgele bekleme süresi"""
    sure = random.uniform(min_s, max_s)
    print(f"   ⏳ {sure:.2f} saniye bekleniyor...")
    time.sleep(sure)

def get_stealth_driver():
    """Bot yakalanmasını engelleyen güçlendirilmiş sürücü"""
    ua = UserAgent()
    user_agent = ua.random  # Her seferinde farklı bir kimlik

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={user_agent}")
    
    # 🕵️‍♂️ BOT TESPİTİNİ ENGELLEYEN AYARLAR
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("--window-size=1920,1080") # Gerçek ekran boyutu simülasyonu

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    # Selenium olduğunu gizleyen JavaScript kodu
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

# ==========================================
# 📊 GOOGLE SHEETS & KULLANICI YÖNETİMİ
# ==========================================
def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    else:
        creds_json = json.loads(os.environ.get("G_SHEET_CREDS"))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def kullanicilari_guncelle(client):
    try:
        sheet = client.open(SHEET_ADI).worksheet("Kullanicilar")
        kayitli_id_listesi = sheet.col_values(1)
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        response = requests.get(url).json()
        
        yeni_eklenenler = []
        if "result" in response:
            for update in response["result"]:
                if "message" in update and "text" in update["message"]:
                    mesaj = update["message"]["text"]
                    chat_id = str(update["message"]["chat"]["id"])
                    kullanici_adi = update["message"]["from"].get("first_name", "Bilinmiyor")
                    
                    if mesaj == "/start" and chat_id not in kayitli_id_listesi:
                        sheet.append_row([chat_id, kullanici_adi, time.strftime("%Y-%m-%d")])
                        kayitli_id_listesi.append(chat_id)
                        yeni_eklenenler.append(chat_id)
                        print(f"   ➕ Yeni Abone: {kullanici_adi}")
        
        # Eğer yeni eklenen varsa listeyi güncel haliyle döndür, yoksa eskisi
        return kayitli_id_listesi
    except Exception as e:
        print(f"⚠️ Kullanıcı güncelleme hatası: {e}")
        return []

def link_kaydet(client, link, baslik, site):
    sheet = client.open(SHEET_ADI).worksheet("Etkinlikler")
    # Zaten var mı kontrolünü burada yapmak sheet isteğini azaltır ama 
    # biz main fonksiyonda liste kontrolü yapıyoruz.
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
    print(f"\n📨 [{site}] Bildirimi Gönderiliyor... ({len(abone_listesi)} Kişi)")
    
    caption = (
        f"🚀 <b>{site}</b>\n\n"
        f"📌 <b>{baslik}</b>\n"
        f"🗓 {tarih}\n\n"
        f"🔗 <a href='{link}'>HEMEN BAŞVUR</a>"
    )

    for ham_id in abone_listesi:
        try:
            chat_id = str(ham_id).strip().split(".")[0]
            if not chat_id.isdigit(): continue

            payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            
            # Telegram sunucusunu yormamak için görsel kontrolü
            if gorsel_url and len(gorsel_url) > 10:
                payload['photo'] = gorsel_url
                method = "sendPhoto"
            else:
                payload['text'] = caption
                method = "sendMessage"

            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", data=payload)
            time.sleep(0.05) # Telegram API limitine takılmamak için minik bekleme
        except: continue
    print("   ✅ Gönderim tamamlandı.")

# ==========================================
# 🕷️ GELİŞMİŞ SCRAPING MODÜLLERİ
# ==========================================

def scrape_anbean(driver, client, mevcut, aboneler):
    print("\n🔍 Anbean Taranıyor...")
    try:
        driver.get("https://anbeankampus.co/etkinlikler/")
        rastgele_bekle(4, 8) # Rastgele bekleme
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        kartlar = soup.find_all("div", class_="mini-eventCard")

        for kart in kartlar[:5]:
            link_tag = kart.find("a")
            if not link_tag: continue
            
            link = "https://anbeankampus.co" + link_tag['href']
            if link in mevcut: continue
            
            baslik = kart.find("h6").text.strip()
            img = kart.find("img", class_="mini-eventCard-HeaderImage")
            gorsel = "https://anbeankampus.co" + img['src'] if img else None
            
            # Tarih bulma (daha güvenli yöntem)
            tarih = "Sitede kontrol ediniz"
            date_items = kart.find_all("div", class_="mini-eventCard-dateItem")
            if date_items:
                tarih = " | ".join([d.text.strip() for d in date_items])

            herkese_gonder(aboneler, "Anbean", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Anbean")
            mevcut.append(link) # Aynı döngüde tekrar göndermemek için listeye ekle

    except Exception as e: print(f"⚠️ Anbean Hatası: {e}")

def scrape_toptalent(driver, client, mevcut, aboneler):
    print("\n🔍 Toptalent Taranıyor...")
    try:
        driver.get("https://toptalent.co/etkinlikler")
        rastgele_bekle(3, 6)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Seçici güncellendi: Genellikle section içindeki a tagleri
        kartlar = soup.select("div.section-list-item a")
        
        if not kartlar:
            # Alternatif yapı kontrolü
            kartlar = soup.find_all("a", class_="position")

        for kart in kartlar[:5]:
            link = kart.get('href', '')
            if not link: continue
            if not link.startswith("http"): link = "https://toptalent.co" + link
            
            if link in mevcut: continue
            
            baslik_tag = kart.find("h5") or kart.find("div", class_="title")
            baslik = baslik_tag.text.strip() if baslik_tag else "Başlık Bulunamadı"
            
            img = kart.find("img")
            gorsel = img['data-src'] if img and 'data-src' in img.attrs else (img['src'] if img else None)
            if gorsel and not gorsel.startswith("http"): gorsel = "https://toptalent.co" + gorsel

            tarih = "Detaylar Sitede"
            
            herkese_gonder(aboneler, "Toptalent", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Toptalent")
            mevcut.append(link)

    except Exception as e: print(f"⚠️ Toptalent Hatası: {e}")

def scrape_youthall(driver, client, mevcut, aboneler):
    print("\n🔍 Youthall Taranıyor...")
    try:
        driver.get("https://www.youthall.com/tr/events/")
        rastgele_bekle(5, 9) # Youthall daha hassas olabilir
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        kartlar = soup.find_all("div", class_="events")

        for kart in kartlar[:5]:
            link_tag = kart.find("a")
            if not link_tag: continue
            
            link = "https://www.youthall.com" + link_tag['href']
            if link in mevcut: continue
            
            baslik = kart.find("h2").text.strip()
            
            img_div = kart.find("div", class_="events__img")
            img = img_div.find("img") if img_div else None
            gorsel = "https://www.youthall.com" + img['src'] if img else None
            
            tarih_div = kart.find("div", class_="events__content__details")
            tarih = tarih_div.text.strip().replace("\n", " ") if tarih_div else "Tarih Yok"

            herkese_gonder(aboneler, "Youthall", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Youthall")
            mevcut.append(link)

    except Exception as e: print(f"⚠️ Youthall Hatası: {e}")

# 🆕 YENİ SİTE: CODERSPACE
def scrape_coderspace(driver, client, mevcut, aboneler):
    print("\n🔍 Coderspace Taranıyor...")
    try:
        driver.get("https://coderspace.io/etkinlikler")
        rastgele_bekle(5, 10)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Coderspace yapısı genellikle kart şeklindedir
        kartlar = soup.find_all("div", class_="event-card") 
        
        if not kartlar: # Yapı değişmişse alternatif class
            kartlar = soup.select("a[class*='event-card']")

        for kart in kartlar[:5]:
            # Kartın kendisi link olabilir veya içinde a tagi olabilir
            link_tag = kart if kart.name == 'a' else kart.find("a")
            if not link_tag: continue

            link = link_tag['href']
            if not link.startswith("http"): link = "https://coderspace.io" + link
            
            if link in mevcut: continue
            
            baslik_tag = kart.find("h3") or kart.find("h4") or kart.find("div", class_="title")
            baslik = baslik_tag.text.strip() if baslik_tag else "Coderspace Etkinliği"
            
            # Görsel
            img = kart.find("img")
            gorsel = img['src'] if img else None
            
            # Tarih
            tarih_tag = kart.find("div", class_="date") or kart.find("span", class_="date")
            tarih = tarih_tag.text.strip() if tarih_tag else "Web sitesine göz atın"

            herkese_gonder(aboneler, "Coderspace", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Coderspace")
            mevcut.append(link)
            
    except Exception as e: print(f"⚠️ Coderspace Hatası: {e}")

# 🆕 YENİ SİTE: TECHCAREER
def scrape_techcareer(driver, client, mevcut, aboneler):
    print("\n🔍 Techcareer Taranıyor...")
    try:
        # Bootcamp sayfasına bakıyoruz
        driver.get("https://www.techcareer.net/bootcamp")
        rastgele_bekle(5, 8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Techcareer React kullanır, class isimleri karışıktır (jss123 gibi).
        # Bu yüzden hiyerarşik veya attribute bazlı arama daha güvenlidir.
        
        # Linkleri topla (Bootcamp linkleri genellikle /bootcamp/ ile başlar)
        tum_linkler = soup.find_all("a", href=True)
        bootcamp_linkleri = [a for a in tum_linkler if "/bootcamp/" in a['href'] and len(a['href']) > 15]

        # Tekrarları temizle
        unique_links = []
        [unique_links.append(x) for x in bootcamp_linkleri if x['href'] not in [y['href'] for y in unique_links]]

        for tag in unique_links[:5]:
            link = "https://www.techcareer.net" + tag['href']
            
            if link in mevcut: continue

            # Başlığı linkin içinden veya çevresinden bulmaya çalış
            # Techcareer'de genellikle kartın içindeki H3 veya H4 başlık olur
            baslik = "Techcareer Bootcamp"
            parent_card = tag.find_parent("div")
            if parent_card:
                h_tags = parent_card.find_all(["h2", "h3", "h4"])
                if h_tags:
                    baslik = h_tags[0].text.strip()
            
            # Eğer başlık hala generic ise linkten üret
            if baslik == "Techcareer Bootcamp":
                 slug = tag['href'].split("/")[-1].replace("-", " ").title()
                 baslik = f"{slug} Bootcamp"

            tarih = "Başvurular Açık"
            gorsel = None # Techcareer görselleri genelde base64 veya karışık olabilir
            
            herkese_gonder(aboneler, "Techcareer", baslik, tarih, link, gorsel)
            link_kaydet(client, link, baslik, "Techcareer")
            mevcut.append(link)

    except Exception as e: print(f"⚠️ Techcareer Hatası: {e}")

# ==========================================
# 🏁 MAIN LOOP
# ==========================================
if __name__ == "__main__":
    print("🚀 GELİŞMİŞ BOT BAŞLATILIYOR...")
    
    try:
        # 1. Google Bağlantısı
        client = get_google_client()
        
        # 2. Kullanıcıları Güncelle
        aboneler = kullanicilari_guncelle(client)
        if not aboneler: 
            print("⚠️ Hiç abone yok veya okunamadı.")
        
        # 3. Mevcut Linkleri Çek
        mevcut_linkler = linkleri_getir(client)
        
        # 4. Stealth Driver'ı Başlat
        driver = get_stealth_driver()
        
        # 5. Taramaları Başlat
        scrape_anbean(driver, client, mevcut_linkler, aboneler)
        scrape_toptalent(driver, client, mevcut_linkler, aboneler)
        scrape_youthall(driver, client, mevcut_linkler, aboneler)
        
        # Yeni Siteler
        scrape_coderspace(driver, client, mevcut_linkler, aboneler)
        scrape_techcareer(driver, client, mevcut_linkler, aboneler)
        
        driver.quit()
        print("\n✅ TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI.")
        
    except Exception as e:
        print(f"\n🔥 KRİTİK HATA: {e}")
