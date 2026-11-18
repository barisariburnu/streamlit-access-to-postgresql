# GlitchTip uygulama doğrulaması — 18 Kasım 2026

Kaynak kapsamı: streamlit-access-to-postgresql. SDK: resmi `sentry-sdk==2.75.0`, Python 3.10.19.

- RED: izleme modülü olmadan 7/7 gereksinim testi başarısız.
- RED→GREEN: yakalanan gerçek upload/chart hata sınırı veya her shell işinin EXIT kancası.
- Gerçek SDK transport zarfı: yalnız temizlenmiş event; nested exception mesajı,
  dirty scope, kullanıcı, context, breadcrumb, attachment ve canary wire'da yok.
- İzleme kapalı/geçersiz release/arızalı transport: uygulama sonucu korunur.
- Aynı exception tek olay; rerun/stop ve beklenen validation sessiz.
- Build: tam 40 küçük hex yoksa Docker çağrısı yok; quoted SOURCE_COMMIT okunur,
  diğer env alanı çalıştırılmaz; release ve OCI metadata pahalı katmanlardan sonra.
- Tam yerel komut: `python3 -m unittest discover -s tests -v`.

Son koşu: 36 test, 31 PASS ve 5 mevcut PostgreSQL-only SKIP. SQLite kullanan
mevcut veri testleri ayrı sentetik fixture içindir; üretim PG kanıtı değildir.
Pinned requirements.txt bağımlılıklarıyla ayrı environment kullanıldı.

Docker image build, gerçek DB/Oracle/WFS/SSH işlemi, production olay teslimi,
push ve deploy bu doğrulamada çalıştırılmadı. Production kontrolleri ayrı yürütülür.
