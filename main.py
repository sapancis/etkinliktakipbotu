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
    print(f"\n📨 GÖNDERİM BAŞLIYOR... Toplam Aday: {len(abone_listesi)}")
    
    # Mesaj metni
    caption = (
        f"📢 <b>{site} - Yeni Etkinlik!</b>\n\n"
        f"🎯 <b>{baslik}</b>\n"
        f"📅 {tarih}\n\n"
        f"🔗 <a href='{link}'>Başvuru ve Detaylar</a>"
    )

    gonderim_basarili = 0
    
    for ham_id in abone_listesi:
        # --- ID TEMİZLEME VE KONTROL ---
        try:
            # Gelen veriyi string'e çevir ve boşlukları temizle
            chat_id = str(ham_id).strip()
            
            # Başlık satırı veya boş satırsa atla
            if chat_id.lower() in ["chat id", "id", "", "none"]:
                continue
            
            # Eğer Google Sheet "12345.0" gibi nokta koyduysa temizle
            if "." in chat_id:
                chat_id = chat_id.split(".")[0]
                
            # Hala sayısal değilse hata ver ve geç
            if not chat_id.isdigit():
                print(f"   ⚠️ GEÇERSİZ ID FORMATI: '{ham_id}' -> Atlanıyor.")
                continue
                
        except Exception as e:
            print(f"   ❌ ID Okuma Hatası ({ham_id}): {e}")
            continue

        # --- GÖNDERİM ---
        print(f"   ➡️ Gönderiliyor: {chat_id} ...", end="")
        
        payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
        
        try:
            # Önce fotoğraflı dene
            if gorsel_url and gorsel_url.startswith("http"):
                payload['photo'] = gorsel_url
                r = requests.post(api_url + "sendPhoto", data=payload)
            else:
                # Fotoğraf yoksa metin dene
                payload.pop('photo', None) # Varsa photo anahtarını sil
                payload['text'] = caption
                r = requests.post(api_url + "sendMessage", data=payload)

            # --- SONUÇ KONTROLÜ ---
            if r.status_code == 200:
                print(" ✅ BAŞARILI")
                gonderim_basarili += 1
            else:
                # Telegram hata verdiyse (Örn: Bot engellenmiş, ID yanlış)
                print(f" ❌ HATA (Kod: {r.status_code})")
                print(f"      Telegram Cevabı: {r.text}")
                
        except Exception as e:
            print(f" 💥 BAĞLANTI HATASI: {e}")
            
        time.sleep(0.1) # Spam olmasın diye bekleme

    print(f"🏁 Gönderim Tamamlandı. Başarılı: {gonderim_basarili}/{len(abone_listesi)}")

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
    print("\n" + "="*30)
    print("🔍 Anbean Taranıyor (Detaylı Mod)...")
    url = "https://anbeankampus.co/etkinlikler/"
    
    try:
        driver.get(url)
        time.sleep(7) # Bekleme süresini artırdık
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Kartları bul
        kartlar = soup.find_all("div", class_="mini-eventCard")
        print(f"   ℹ️ Sayfada {len(kartlar)} adet etkinlik kartı bulundu.")
        
        if len(kartlar) == 0:
            print("   ⚠️ Kart bulunamadı! HTML yapısı değişmiş veya site yüklenmemiş olabilir.")
            print("   İpucu: Sayfa kaynağını kontrol et.")
            return

        gonderilen_sayisi = 0
        for i, kart in enumerate(kartlar[:5]):
            try:
                link_tag = kart.find("a")
                if not link_tag:
                    print(f"   ⚠️ {i+1}. kartta link etiketi yok.")
                    continue
                    
                link = "https://anbeankampus.co" + link_tag['href']
                
                # Link kontrolü
                if link in mevcut:
                    print(f"   ⏭️ {i+1}. Etkinlik pas geçildi (Zaten veritabanında var).")
                    continue
                
                # Başlık çekme
                baslik_div = kart.find("div", class_="mini-eventCard-titleDescription")
                baslik = baslik_div.find("h6").text.strip() if baslik_div else "Başlık Yok"
                
                # Görsel çekme
                img = kart.find("img", class_="mini-eventCard-HeaderImage")
                gorsel = "https://anbeankampus.co" + img['src'] if img else None
                
                # Tarih çekme
                tarih = "Belirtilmemiş"
                for d in kart.find_all("div", class_="mini-eventCard-dateItem"):
                    if "Son" in d.text: tarih = d.text.strip()

                print(f"   ✅ Yeni etkinlik bulundu: {baslik}")
                herkese_gonder(aboneler, "Anbean", baslik, tarih, link, gorsel)
                link_kaydet(client, link, baslik, "Anbean")
                gonderilen_sayisi += 1
                
            except Exception as e:
                print(f"   ❌ Kart işlenirken hata: {e}")
                
        print(f"   🏁 Anbean tamamlandı. {gonderilen_sayisi} yeni gönderildi.")

    except Exception as e: 
        print(f"🔥 Anbean Genel Hata: {e}")

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
    print("\n" + "="*30)
    print("🔍 Youthall Taranıyor (Detaylı Mod)...")
    url = "https://www.youthall.com/tr/events/"
    
    try:
        driver.get(url)
        time.sleep(7) # Bekleme süresi arttı
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        kartlar = soup.find_all("div", class_="events")
        print(f"   ℹ️ Sayfada {len(kartlar)} adet etkinlik kartı bulundu.")

        if len(kartlar) == 0:
            print("   ⚠️ Kart bulunamadı! HTML class isimleri değişmiş olabilir.")
            return

        gonderilen_sayisi = 0
        for i, kart in enumerate(kartlar[:5]):
            try:
                link_tag = kart.find("a")
                if not link_tag: continue
                
                link = "https://www.youthall.com" + link_tag['href']
                
                if link in mevcut:
                    print(f"   ⏭️ {i+1}. Etkinlik pas geçildi (Zaten veritabanında var).")
                    continue
                
                baslik_tag = kart.find("h2")
                if not baslik_tag:
                     print(f"   ⚠️ {i+1}. kartta başlık (h2) yok.")
                     continue
                baslik = baslik_tag.text.strip()
                
                img_div = kart.find("div", class_="events__img")
                img = img_div.find("img") if img_div else None
                gorsel = "https://www.youthall.com" + img['src'] if img else None
                
                detay_div = kart.find("div", class_="events__content__details")
                tarih = detay_div.text.strip() if detay_div else "Detaylar Sitede"

                print(f"   ✅ Yeni etkinlik bulundu: {baslik}")
                herkese_gonder(aboneler, "Youthall", baslik, tarih, link, gorsel)
                link_kaydet(client, link, baslik, "Youthall")
                gonderilen_sayisi += 1

            except Exception as e: 
                print(f"   ❌ Youthall Kart Hatası: {e}")
                
        print(f"   🏁 Youthall tamamlandı. {gonderilen_sayisi} yeni gönderildi.")

    except Exception as e: 
        print(f"🔥 Youthall Genel Hata: {e}")

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

