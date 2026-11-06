# DataDesk teknik inceleme

Bu belge, önceki uygulamanın incelenmesinde bulunan somut sorunları ve yeni yapının doğrulanmasında kullanılan senaryoları açıklar. Otomatik testlerin güncel sonucu, GitHub Actions çalışmasından veya yerel `pytest` çıktısından okunmalıdır; bu belge sabit bir test sayısı ya da performans garantisi vermez.

## 6 Kasım 2026 yerel doğrulaması

- macOS, Python 3.12.13, pandas 3.1.1 ve PySide6-Essentials 6.12.0 ile **224 otomatik test** başarılı oldu.
- Ek olarak, macOS'un gerçek pencere sistemi (`cocoa`) üzerinde **24 arayüz/model testi** başarılı oldu; örnek veriyle açılış, filtre oluşturma ve aktif filtre ekranları görsel olarak incelendi.
- `tools/benchmark.py`, geçici bir dizinde **100.000 satır × 8 sütun** CSV oluşturup bağımsız hesaplanan **1.412 kaydı** filtreledi, sıraladı ve seçilen 6 sütunu Excel'e aktardı. Yeniden okunan bütün hücreler ve sıra, bağımsız beklenen sonuçla karşılaştırıldı. Kimliklerdeki sıfırlar, uzun kodlar, Türkçe karakterler ve çok satırlı metinler korundu.
- Ruff ve `git diff --check` kontrolleri başarılı oldu. Bu sonuçlar yukarıdaki yerel ortam içindir; farklı işletim sistemleri için CI matrisi ayrıca çalışır.

Tekrarlama: `QT_QPA_PLATFORM=offscreen uv run --extra dev pytest -q`, `uv run python tools/benchmark.py`. Görselleri yeniden oluşturma: `uv run python tools/capture_screenshots.py`; bu araç yalnızca yapay örnek veri kullanır.

## Önceki sürümde bulunan sorunlar

| Sorun | Kullanıcıya etkisi | Yeni yaklaşım |
| --- | --- | --- |
| Herhangi bir `Unnamed` başlıkta ilk veri satırı başlığa taşınıyordu. | Başlığı eksik bir sütun, ilk kaydın kaybolmasına neden olabiliyordu. | Başlık satırı kullanıcı tarafından seçilir; eksik başlıklara benzersiz ad verilir. |
| Sayılar, filtrede ve düzenleyicide farklı `replace` zincirleriyle okunuyordu. | `1.234,56`, `1234.56` ve aralık sınırları farklı değerlere dönüşebiliyordu. | Tek sayı ayrıştırıcı; kaynak değerleri değiştirmeden karşılaştırma. |
| Sütun tipi yalnızca ilk birkaç satırdan ve genel tarih tahmininden çıkarılıyordu. | Sayılar tarih sanılabiliyor, sonraki bozuk değerler gözden kaçabiliyordu. | Temkinli tür algılama ve filtrede açık tür seçimi. |
| `ve`, `veya`, `ya da` tek düzenli ifadeyle bölünüp daima `all()` ile aranıyordu. | VEYA beklentisi VE olarak uygulanıyordu. | Tüm/herhangi bir koşul ve tüm/herhangi bir kelime seçenekleri. |
| Tarih için özel ayrıştırıcı bulunmasına rağmen filtrede tekrar varsayılan `to_datetime` çağrılıyordu. | Türkçe tarihlerin gün/ay anlamı veya geçerli değerler kaybolabiliyordu. | Görüntüleme, filtreleme ve sıralamada ortak tarih kuralları. |
| Filtreli düzenleyici yalnızca `df_filtered` kopyasını kaydediyordu. | Filtre temizlendiğinde kullanıcının düzenlemeleri kaybolabiliyordu. | Düzenlemeler, kaynaktaki satır kimliğine uygulanır; görünüm yeniden hesaplanır. |
| Sıralama düğmeleri tanımlı olmayan `_sutun_sirala` yöntemini çağırıyordu; tarihlerde sıralama kapalıydı. | Başlığa tıklamak hata verebiliyor; tarihler sıralanamıyordu. | Ortak tür duyarlı sıralama ve tablonun aynı sonuç sırasıyla dışa aktarımı. |
| CSV yalnızca UTF-8 ve varsayılan virgülle açılıyordu. | Türkçe Windows CSV dosyaları ya hata veriyor ya da tek sütun görünüyordu. | Kodlama/ayraç algılama ve elle seçim. |
| Eksik değerler pandas'ın varsayılan kurallarıyla okunuyordu. | `NA` ve `null` gibi gerçek metinler boş hücreye dönüşebiliyordu. | Gerçek boş hücreyi metin belirteçlerinden ayıran okuma. |
| Bir dosya içeri alınırken aynı adlı eski kopyanın üzerine yazılabiliyordu. | Kullanıcının önceki verisi sessizce değişebiliyordu. | Dosyayı yerinden açma; sonucu ayrı bir dosyaya kaydetme. |
| Dosya silme sonrası açık tablo ve filtre durumu temizlenmiyordu. | Ekranda artık var olmayan dosyanın verisi kalabiliyordu. | Kaynak dosyaları uygulama içinden silmeyen çalışma alanı. |
| Dışa aktarma boş sonuçları reddediyordu. | Sıfır eşleşmenin başlıklı bir rapor olarak kaydedilmesi mümkün değildi. | Sıfır satırlı çıktıda sütunları koruma. |
| Excel/CSV kayıtları doğrudan hedefe yazılıyordu. | Kayıt yarıda kesilirse mevcut çıktı bozulabiliyordu. | Aynı dizinde geçici dosya ve başarıdan sonra atomik değiştirme. |
| Tablonun her satırı bir GUI öğesi olarak oluşturuluyordu. | Büyük dosyalarda açılış ve görüntü yenileme arayüzü kilitliyordu. | Qt tablo modeli ve arka plan görevleri. |
| Bağımlılık dosyası, paket girişi ve test iş akışı yoktu. | Kurulum tekrarlanabilir değildi; hatalar kolayca geri gelebiliyordu. | `pyproject.toml`, tek uygulama girişi ve CI. |

## Otomatik doğrulama kapsamı

- **Ayrıştırma:** Türkçe/uluslararası sayılar, ondalık nokta, negatif ve geçersiz değerler; tarih olmayan sayılar; baştaki sıfırlar; karışık sütunlar; gerçek boş hücreler.
- **Filtreleme:** VE/VEYA, Türkçe büyük/küçük harf, aralık sınırları, bitiş günündeki saatler, boş/dolu, yanlış aralıklar ve geçersiz girdiler. Hatalı filtre sessizce uygulanmış görünmemelidir.
- **Sıralama:** Sayı/tarih/metin türleri, boş değerlerin konumu, kararlı sıra ve kaynak hücrelerin değişmemesi.
- **Dosyalar:** Gerçek `.xlsx`, `.xls`, `.csv` ve `.tsv` dosyaları; farklı kodlamalar ve ayraçlar; satır içi ayraç, tırnak ve yeni satırlar; yinelenen/boş başlıklar; sayfa/başlık seçimi; bozuk dosyalar.
- **Dışa aktarma:** Sütun seçimi/sırası, tam sonuç sayısı, sıfır satır, sayısal/tarih değerleri, metin kodları, formül gibi başlayan metinler ve mevcut dosyanın hata halinde korunması.
- **Arayüz:** Açma, filtreleme, sıralama, düzenleme ve geri alma; başarısız işlemden sonra çalışma belgesinin korunması ve bekleyen görevler sırasında tutarlı durum.

Bu listedeki her elle kontrolün otomatik kapsama dönüştüğünü varsaymayın; test kaynakları `tests/` dizinindedir.

## Elle kabul kontrolü

1. İki sayfalı bir Excel açın. İkinci sayfayı ve başlık olarak üçüncü satırı seçin; ilk veri satırının ve tüm sütunların yerinde olduğunu doğrulayın.
2. `00123`, `NA`, boş hücre, Türkçe ad, gerçek Excel tarihi ve `1.234,56` içeren dosyayı açın. Görünümü kaynağıyla karşılaştırın.
3. Noktalı virgüllü Windows Türkçe CSV açın. Otomatik sonuç doğru değilse kodlamayı `cp1254` seçin. Virgüllü ve sekmeli dosyalarda da sütun sayısını kontrol edin.
4. Tutar aralığı ve şehir eşitliği ekleyin. Tümü/herhangi biri seçeneklerinde bilinen kayıtlarla eşleşen satır sayılarını kontrol edin.
5. Tarih aralığında bitiş gününün 23:59 saatli kaydının dahil olduğunu kontrol edin. Tarih ve tutar başlıklarına tıklayarak artan/azalan sıralamayı deneyin.
6. Filtrelenmiş ve sıralanmış görünümde bir hücreyi değiştirin, bir satırı silin ve yeni satır ekleyin. Filtreyi kaldırın; doğru kaynak kayıtlarının değiştiğini doğrulayın. Geri al/yinele uygulayın.
7. Üç sütun seçerek Excel ve CSV dışa aktarın. Yeni dosyaları yeniden açıp satır sayısını, sütun sırasını, sıralamayı ve değerleri karşılaştırın. Sıfır sonuçta da başlıkları kontrol edin.
8. Bozuk bir dosya açmayı deneyin; önceki çalışma belgesinin kullanılabilir kaldığını kontrol edin. Kaydı yazılamayan bir konuma denediğinizde açık bir hata görünmelidir.
9. Büyük bir tablo açın. Kaydırma, yatay kaydırma ve uzun sütun adlarını kontrol edin; işlemler sırasında pencerenin yanıt verdiğini doğrulayın. Dosya boyutu/bellek ölçmeden hız iddiasında bulunmayın.
10. Düzenleme yaptıktan sonra başka dosya açma ve pencereyi kapatma davranışını kontrol edin; bekleyen arka plan görevleri uygulamayı çökertecek şekilde sonlandırılmamalıdır.

## Mimari

`core.py` yalnızca veri kurallarını, `io.py` dosya biçimlerini, `ui.py` ise kullanıcı etkileşimlerini yönetir. Bu ayrım aynı filtre ve ayrıştırma mantığının ana tablo, sıralama ve çıktı arasında farklılaşmasını engeller. `app.py`, uygulamanın tüm giriş yollarının ulaştığı başlangıç noktasıdır.

Veriler yerelde ve bellekte işlenir. Qt'nin sanal tablo görünümü, bütün dosyanın diskte akış halinde işlendiği anlamına gelmez. Excel formül hesaplama, makro çalıştırma ve özgün çalışma kitabını tüm özellikleriyle yeniden oluşturma bu uygulamanın kapsamında değildir.
