# Access Verilerinin PostgreSQL Ortamına Aktarılması

Microsoft Access `.mdb` dosyalarındaki tabloları PostgreSQL ortamına aktarmak için geliştirilmiş Streamlit uygulamasıdır. Mevcut kayıtların eşleştirilmesi, güncellenmesi ve yükleme sonuçlarının kaydedilmesi aynı iş akışında yürütülür.

## Yapılandırma

Veritabanı bağlantısı `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` ve `DB_PASSWORD` ortam değişkenlerinden sağlanır. Gerçek bağlantı değerleri kaynak kod deposunda tutulmamalıdır. Başlangıç betiği gerekli Streamlit yapılandırmasını çalışma sırasında oluşturur.

## Yerel çalıştırma

`.env.example` dosyasından yerel bir `.env` oluşturup bağlantı değerlerini tanımlayın. Ardından `docker compose up -d --build` komutunu çalıştırın. Uygulama varsayılan olarak 8501 portunda sunulur.

## Coolify üzerinden yayın

GitHub `main` branch’i, Docker Compose Application olarak bağlanır. Deployment ayarları ve kalıcı yükleme dizini için [.coolify/README.md](.coolify/README.md) belgesini inceleyin. Kaynak kod image içinde bulunur; yüklenen dosyalar ayrı ve kalıcı bir veri alanında tutulmalıdır.

## Doğrulama

`python -m unittest discover -s tests -v` komutu veri eşleştirme ve yükleme denetimi testlerini çalıştırır. PostgreSQL entegrasyon testleri yalnız ayrı bir test sunucusuna bağlanacak şekilde yapılandırılmalıdır; üretim veritabanı test hedefi olarak kullanılmamalıdır.

## GlitchTip hata izleme

Gizlilik sınırı, runtime değişkenleri ve sentetik kontrol komutu için
[operasyon notlarını](.coolify/README.md#glitchtip) inceleyin.
