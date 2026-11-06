# DataDesk teknik notları

Bu belge DataDesk 1.1.0'ın dosya, kayıt ve doğrulama davranışını açıklar. Güncel test sonucu için [Tests](https://github.com/KrAlmano/DataDesk/actions/workflows/tests.yml) ve [Desktop packages](https://github.com/KrAlmano/DataDesk/actions/workflows/desktop-packages.yml) çalışmalarını inceleyin. Bir hedefte alınan sonuç başka bir işletim sisteminin doğrulaması olarak sunulmaz.

## 1.1.0: dosya ve klasörlerle çalışma

Ana ekran bir dosya görünümüdür. Çalışma klasörünün altındaki gerçek klasörler ve desteklenen tablo dosyaları listelenir. Açık tablo ayrı bir sekmede tutulur; **Dosyalar** sekmesine geçmek belgeyi kapatmaz. Filtreler düğmeyle açılır. Dekoratif özet kartları yerine tabloya ve dosya listesine alan ayrılır.

Çalışma klasörü varsayılan olarak Qt'nin sistem belgeler klasöründeki `DataDesk` dizinidir. Kullanıcı başka bir klasör seçebilir. Konum ve gezinilen alt klasör uygulama ayarlarında tutulur; çalışma alanı sanal bir dosya sistemi değildir.

### Dosya işlemleri

- Yeni klasör ve `.xlsx`, `.csv`, `.tsv` dosyaları gerçek diskte oluşturulur. Boş tablonun sütunları kullanıcı tarafından belirlenir; oluşturulan dosya aynı okuma motoruyla yeniden açılabilir.
- **İçe aktar**, mevcut dosyanın kopyasını ekler. Asıl dosyayı taşımaz veya yeniden yazmaz. İsim çakışmalarında numaralı ad seçilir.
- Yeniden adlandırma ve taşıma çalışma klasörü içinde kalır. Yol geçişleri, bağlantıyla alan dışına çıkma, Windows'un ayrılmış adları ve aynı isimle var olan dosyayı değiştirme reddedilir.
- Yeni dosya ve kopyalama işlemleri geçici dosyada hazırlanır; işletim sisteminin üzerine yazmayan taşıma işlemiyle yayımlanır. Hedefin kontrolden sonra başka süreççe oluşturulması da üzerine yazma nedeni değildir.
- Dosya uzantısı yeniden adlandırmayla değiştirilemez. Çalışma kökü taşınamaz; klasör kendi altına taşınamaz. Uygulama içinden dosya silme sunulmaz.

### Kaydetme ve veri kaybını önleme

**Kaydet**, filtre sonucunu değil çalışma belgesinin bütün satırlarını ve sütunlarını yazar. **Dışa aktar** ise arama/filtre/sıralama sonucunu ve seçilen sütunları yazar. Bu iki işlem ayrı kullanıcı akışlarıdır.

CSV/TSV çalışma dosyasını kaydetme ham metinleri korur; formül güvenliği öneki eklemez. Önek ekleme, dışa aktarımın açıkça seçilebilir davranışıdır. CSV tip bilgisi taşımadığı için Excel açılışındaki tür/formül tahmini DataDesk'in kayıt davranışından ayrıdır.

Doğrudan kayıt, DataDesk'te oluşturulmuş ve hâlâ aynı dosya olarak tanınan tek tabloluk dosyalara uygulanır. Dışarıdan açılan/kopyalanan tablolar için **Farklı kaydet** gerekir. Çok sayfalı bir kaynak Excel çalışma kitabı tek tabloluk çıktı ile değiştirilmez.

Çalışma kökündeki `.datadesk.json`, DataDesk'in oluşturduğu tabloların göreli yollarını ve son kayıt kimliklerini tutar. Dosyanın aygıt, dosya kimliği, boyut veya değişiklik zamanı farklıysa doğrudan kayıt hakkı kullanılmaz. Başka bir uygulamanın değiştirdiği dosyayı korumak için yeni dosya seçilir. Bu kayıt bozuk, okunamaz veya yazılamaz durumdaysa dosyalara erişim korunur; doğrudan kayıt yerine **Farklı kaydet** kullanılır. Bu dosya güvenlik yetkilendirmesi veya yedekleme sistemi değildir.

Tablo yazma işlemleri aynı hedef dizininde geçici dosya kullanır. Başarılı yazmadan sonra atomik değiştirme yapılır; başarısız işlem açık çalışma belgesini veya mevcut çıktıyı bozmaz. Dosya oluşturma/aktarma/taşıma işlemleri ise var olan hedefi değiştirmez.

## Veri motorunda korunan kurallar

| Alan | Davranış |
| --- | --- |
| Başlıklar | Kullanıcı başlık satırını seçer; boş ve tekrarlı başlıklara benzersiz ad verilir. Başlığın eksik olması ilk veri kaydını silmez. |
| Kimlikler | Metin olarak saklanan baştaki sıfırlar ve `NA`/`null` gibi metinler korunur. |
| Sayılar | Tek sayı ayrıştırıcı; otomatik, Türkçe ve İngilizce biçim seçimi. Karşılaştırma kaynak hücreyi yeniden yazmaz. |
| Tarihler | Görüntüleme, filtreleme ve sıralamada ortak kurallar; aralık bitiş gününün tamamını içerir. |
| Koşullar | Birden fazla filtre için VE/VEYA; kelime aramasında tüm/herhangi bir kelime seçimi. |
| Düzenleme | Görünen satırın konumu yerine kaynak satır kimliğine uygulanır. Filtre temizlenince düzenleme kaybolmaz. |
| Sıralama | Veri türüne duyarlı ve kararlı; çıktı aynı sonuç sırasını kullanır. |
| Çıktı | Tüm sonuç satırları, seçilen sütun sırası; sıfır satırda da sütun başlıkları. |
| CSV | Kodlama/ayraç algılama ve elle seçim; dışa aktarımda seçilebilir formül güvenliği. |

Formül hesaplama, makro çalıştırma veya kaynak Excel'in tüm biçimlerini yeniden oluşturma kapsam dışındadır. Formüllerde kayıtlı hesaplanmış sonuç kullanılır; sonuç yoksa formül uyarıyla metin olarak gösterilir. Yeni dosya veri tablosudur.

## Arayüz ve platformlar

PySide6, ortak Fusion teması ve gömülü Inter yazı tipi kullanılır. Açık gri uygulama alanı, beyaz tablo/dosya listesi ve tek mavi vurgu iki sistemde aynıdır. `platforms.py`, Cmd/Ctrl kısayol adlarını, macOS dosya açma olaylarını ve Windows görev çubuğu kimliğini yönetir. Sistem klasörleri Qt'den alınır; Windows'ta `~/Documents` veya `~/Desktop` yolu varsayılmaz.

Dar pencerede kenar çubuğu gizlenir; dosya görünümünden gezinme sürer. Filtreler, tabloyu kullanılmaz hale getirmek yerine ayrı görünümde açılır. Geniş pencerede tablo ve filtre paneli yan yana kullanılabilir. Kullanıcı büyüklüğü %75–150 aralığındadır; cihaz DPI ölçeği Qt tarafından ayrıca işlenir. Uzun dosya/sütun adları ve formlar için kısaltma, kaydırma ve sabit son işlem düğmeleri kullanılır.

Veriler belleğe yüklenir. Qt'nin sanal tablo modeli yalnızca görünen hücreleri çizse de bütün tablonun diskten akış halinde işlendiği anlamına gelmez. İşlenebilecek boyut, kullanılabilir belleğe ve dosya biçimine bağlıdır.

## Otomatik doğrulama

Testler gerçek dosyaları geçici klasörlerde üretir ve yeniden okur. Kaynaklar `tests/` altındadır; kapsamın ayrıntısı test kodundan ve çalışmanın raporundan okunmalıdır.

- **Çalışma alanı:** Türkçe/Unicode adlar, kalıcı dosyalar, boş tabloların yeniden okunması, isim çakışması, kopyalanan aslın korunması, taşıma/ad değiştirme ve alan dışındaki yolların reddi.
- **Kayıt:** DataDesk tablosunun yeniden tanınması, dış değişiklik sonrası doğrudan kaydın engellenmesi, tam tablo kaydı ile filtre çıktısının ayrılması.
- **Ayrıştırma:** Türkçe/uluslararası sayılar, büyük kimlikler, geçersiz tarihler, baştaki sıfırlar, karışık sütunlar ve gerçek boş hücreler.
- **Filtre/sıralama:** VE/VEYA, Türkçe büyük/küçük harf, aralık sınırları, bitiş günündeki saatler, boş/dolu ve hatalı girişte önceki sonucun korunması.
- **Dosya biçimleri:** Gerçek Excel/CSV/TSV, kodlamalar, ayraçlar, tırnak/yeni satır içeren hücreler, başlık/sayfa seçimi ve bozuk dosyalar.
- **Çıktı:** Sütun seçimi/sırası, tüm sonuçlar, sıfır satır, yerel sayı/tarih tipleri, formül gibi başlayan metinler ve hata halinde mevcut hedefin korunması.
- **Qt arayüzü:** Dosya gezinme, tablo işlemleri, bekleyen arama ve görevler, değişikliklerin geri alınması, dar/geniş pencere ve büyüklükte erişilebilir kontroller.

Yerel çalıştırma:

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
QT_QPA_PLATFORM=offscreen uv run --extra dev pytest -q
```

PowerShell'de önce `$env:QT_QPA_PLATFORM = "offscreen"` ayarlayın. Gerçek masaüstü pencere sistemiyle çalıştırmak için bu değişkeni kaldırın. `tools/benchmark.py`, 100.000 satır × 8 sütun CSV üzerinde bağımsız beklenen filtre sonucunu Excel'e aktarıp yeniden okuyarak kontrol eder; işlem süresi bir performans garantisi değildir.

Ekran görüntüleri `uv run python tools/capture_screenshots.py` ile yeniden oluşturulur. Araç gerçek Qt pencerelerini, geçici bir çalışma alanını ve yapay örnek verileri kullanır. Geçici INI ayarları gerçek kullanıcı tercihleri ve son dosyaların görüntülere karışmasını önler. Alternatif çıktı dizini: `--output-dir <klasör>`. Görseller [kullanım kılavuzundadır](KULLANIM.md).

## Yerel kurulum paketlerinin doğrulanması

PyInstaller Python/Qt ve dosya motorlarını uygulamaya gömer. macOS Apple Silicon ve Intel için ayrı `.app`/DMG; Windows x64 için kullanıcıya özel Inno Setup kurucusu üretilir. Kilitli Qt ikilileri macOS 14+ gerektirir; Windows kurucusu Windows 10 1809+ ister.

`Desktop packages`, her hedefte kaynak testlerini ve yerel derlemeyi çalıştırır. macOS testi DMG'yi bağlar, uygulamayı boşluk içeren geçici konuma kopyalar, paket bütünlüğünü ve gömülü uygulamayı denetler. Windows testi gerçek kurulum, Başlat kısayolu, kurulu uygulama testi ve kaldırmayı kapsar. Kurulu uygulama testi çok sayfalı Excel, baştaki sıfırlar, filtre/sıralama, XLSX/CSV/TSV/Word çıktısı, yeniden okuma, SVG/yazı tipi ve kaynağın değişmemesi senaryolarını kullanır.

Sürüm için iş akışı mevcut taslak sürümün etiketiyle `release_tag` verilerek çalıştırılır. Paketler ilgili hedefin testleri geçtikten sonra taslağa yüklenir. Yayımlamadan önce üç hedefin durumu ve SHA-256 dosyaları kontrol edilir. Normal dal/PR çalışmaları yayımlanmış kurucuları değiştirmez.

macOS paketleri ad hoc imzalıdır; Apple Developer ID ve noter onayı sağlanmamıştır. Windows'ta yayıncı sertifikası bulunmaz. macOS betiği uygun sertifika/hesap sağlandığında dağıtım imzası ve noter onayı için seçenekler içerir.

## Elle kabul senaryosu

1. Yeni çalışma klasörü seçin, Türkçe adlı alt klasör açın. Her üç biçimde sütun adları belirlenmiş boş dosya oluşturun; uygulamayı yeniden açıp klasör ve dosyaların kaldığını görün.
2. Aynı adlı dosyayı iki kez içe aktarın. Kopyaları ve asıl dosyanın değişmediğini kontrol edin. Klasör/dosyayı yeniden adlandırıp başka alt klasöre taşıyın; çakışan adların reddedildiğini görün.
3. Yeni tabloya satır ve sütun ekleyin, hücre değiştirin. Bir filtreyle bazı satırları gizleyin; **Kaydet** sonrası dosyayı yeniden açıp gizlenmiş kayıtların da korunduğunu doğrulayın.
4. DataDesk tablosunu Excel'de dışarıdan değiştirip kaydedin. DataDesk'in dosyanın üzerine kaydetmek yerine yeni dosya istediğini kontrol edin. Dışarıdan açılan çok sayfalı workbook'ta da aynı korumayı kontrol edin.
5. İki sayfalı Excel'de ikinci sayfayı ve üçüncü başlık satırını seçin. `00123`, `NA`, boş hücre, Türkçe ad, gerçek tarih ve `1.234,56` değerlerini kaynakla karşılaştırın.
6. Türkçe Windows CSV, virgüllü CSV ve TSV açın; kodlama ve ayırıcıyı gerektiğinde elle seçin. Sütunları ve ilk veri satırını kontrol edin.
7. Tutar/şehir koşullarını VE ve VEYA ile deneyin. Tarih aralığında bitiş gününün 23:59 kaydını kontrol edin. Filtreli sıralı görünümde düzenleme/geri alma uygulayın.
8. Seçilen sütunlarla XLSX ve CSV çıktısı alın; yeniden açıp tüm sonuçları, sütun sırasını ve değerleri karşılaştırın. Sıfır sonuçta başlıkların kalmasını kontrol edin.
9. Bozuk dosya ve yazılamayan hedef deneyin; önceki belge korunmalı, açık hata gösterilmelidir. Düzenlemeden sonra dosya değiştirme/kapatma uyarısını kontrol edin.
10. Dar/geniş pencere ve büyük yazıda dosya gezinme, filtreler, kaydet/dışa aktar ve uzun başlıkları deneyin. Arka plan görevi sürerken pencere yanıt vermeli ve veri durumu tutarlı kalmalıdır.

## Dosya yapısı

| Modül | Görevi |
| --- | --- |
| `app.py`, `platforms.py` | Uygulama girişi ve işletim sistemi entegrasyonu |
| `workspace.py` | Gerçek klasör/dosya işlemleri ve doğrudan kaydedilebilir tablo kaydı |
| `workspace_widgets.py`, `workspace_ui.py` | Dosya görünümü ve çalışma alanı kullanıcı işlemleri |
| `ui.py`, `dialogs.py`, `widgets.py`, `theme.py` | Ana pencere, form akışları ve ortak görünüm |
| `models.py` | Kaynak çalışma belgesi, düzenleme geçmişi ve Qt tablo modeli |
| `core.py`, `io.py` | Tür/filtre/sıralama kuralları ve atomik dosya okuma/yazma |
| `smoke.py`, `packaging/` | Gömülü uygulama testi ve ayrı platform kurucuları |

`core.py` ve `io.py`, arayüzden bağımsızdır. Filtreleme, sıralama ve dışa aktarım aynı veri kurallarını kullanır; belge düzenlemeleri görüntü kopyasına değil kaynak belgeye uygulanır.
