🚀 Etkinlik Takip Botu
Dijital platformlardaki (Coderspace, Youthall, Techcareer, Anbean) kariyer etkinliklerini, bootcamp'leri ve hackathon'ları tek tek kontrol etme zahmetini ortadan kaldıran, Python tabanlı bir otomasyon sistemidir.

Sistem, belirlenen siteleri düzenli olarak tarar, yeni etkinlikleri Google Sheets veritabanına kaydeder ve Telegram üzerinden anlık bildirim gönderir.

✨ Özellikler
Çok Kanallı Tarama: Coderspace, Anbean, Youthall ve Techcareer platformlarını eş zamanlı tarar.

Anti-Bot Mekanizması: Selenium Stealth ve dinamik User-Agent kullanımı ile engellenmelere takılmaz.

Bulut Veritabanı: Google Sheets API entegrasyonu sayesinde verileri kalıcı ve erişilebilir tutar.

Akıllı Bildirim: Telegram üzerinden görselli, HTML formatlı ve doğrudan başvuru linki içeren mesajlar gönderir.

Mükerrer Kontrolü: Daha önce gönderilen ilanları tekrar paylaşmaz.

🛠 Teknik Altyapı
Dil: Python 3.x

Otomasyon: Selenium, BeautifulSoup4

Veri Yönetimi: gspread (Google Sheets API)

Bildirim: python-requests (Telegram Bot API)

Gizlilik: selenium-stealth, fake-useragent

🚀 Kurulum ve Kullanım
1. Gereksinimler
Bash
pip install -r requirements.txt
2. Ortam Değişkenleri (Environment Variables)
Projenin çalışması için aşağıdaki bilgileri .env dosyasına veya sistem değişkenlerine eklemelisiniz:

TELEGRAM_BOT_TOKEN: Telegram botunuzun tokenı.

G_SHEET_CREDS: Google Cloud Console'dan alınan JSON anahtar içeriği.

3. Çalıştırma
Bash
python main.py
📊 Veritabanı Yapısı
Bot, Google Sheets üzerinde iki temel sayfa kullanır:

Etkinlikler: Gönderilen ilanların linklerini ve tarihlerini tutar.

Kullanicilar: Botu /start ile başlatan abonelerin ID listesini tutar.

🤝 Katkıda Bulunma
Her türlü iyileştirme önerisine ve Pull Request'e açığım. Bir hata bulursanız lütfen "Issue" açmaktan çekinmeyin.

Geliştiren: sapancis

Telegram: @etkinliktakippbot
<img width="572" height="952" alt="image" src="https://github.com/user-attachments/assets/a6668bf0-4ede-42d2-99bd-23bee27c5b40" />
