# DataDesk

Excel ve CSV dosyalarını açın, birkaç adımda filtreleyin ve ihtiyacınız olan sütunlarla temiz çıktılar alın. DataDesk, Türkçe arayüzü olan ve dosyalarınızı bilgisayarınızda işleyen bir masaüstü uygulamasıdır.

![DataDesk çalışma alanı ve filtrelenmiş örnek tablo](docs/screenshot.png)

## Neler yapabilirsiniz?

- **Excel ve CSV açma:** `.xlsx`, `.xlsm`, `.xls`, `.csv` ve `.tsv`; Excel sayfasını, başlık satırını, CSV ayıracını ve karakter kodlamasını seçme.
- **Sütunları koruma:** Eksik ve tekrarlanan başlıklara benzersiz adlar verme; başlığı eksik diye ilk veri satırını silmeme; metin olarak saklanan `00123`, `NA` ve `null` değerlerini koruma.
- **Sayı, tarih ve metin filtreleri:** İçerir/içermez, tam eşleşme, başlangıç/bitiş, aralık, karşılaştırma ve boş/dolu koşulları; tüm kelimeler veya herhangi bir kelimeyle arama.
- **Birden çok koşul:** Filtreleri **tümü eşleşsin (VE)** veya **herhangi biri eşleşsin (VEYA)** ile birleştirme; bütün tabloda arama yapma.
- **Sıralama ve düzenleme:** Sütun tipine göre sıralama, satır ekleme/silme ve hücre düzenleme; düzenlemeleri geri alma ve yineleme.
- **İstediğiniz çıktıyı alma:** Görünen sonucun tüm satırlarını ve seçtiğiniz sütunları Excel, CSV, TSV veya Word olarak dışa aktarma. Sıfır sonuçta da sütun başlıklarını içeren dosya oluşturma.
- **Büyük tablolarla çalışma:** Ekrandaki hücreleri gerektiğinde çizen Qt tablo modeli; dosya okuma, filtreleme ve çıktı işlemleri için arka plan görevleri.

Kaynak dosyanız doğrudan düzenlenmez. Değişiklikler çalışma belleğinde tutulur; sonucu ayrı bir dosyaya dışa aktarın. Dosyalarınız bir sunucuya yüklenmez.

## Kurulum ve çalıştırma

Python **3.11–3.14** gerekir. Geliştirmede Python 3.12 kullanılır.

### uv ile

[uv](https://docs.astral.sh/uv/) kuruluysa:

```bash
git clone https://github.com/KrAlmano/DataDesk.git
cd DataDesk
uv run datadesk
```

`uv`, proje için gereken Python ortamını ve bağımlılıkları hazırlar.

### pip ile

```bash
git clone https://github.com/KrAlmano/DataDesk.git
cd DataDesk
python3.12 -m venv .venv
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -e .
python -m datadesk
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m datadesk
```

Windows'ta sanal ortamı `py -3.12 -m venv .venv` ile de oluşturabilirsiniz. Kurulumdan sonra `datadesk`, `python main.py` ve eski `python Excel_project/main.py` girişleri aynı uygulamayı açar.

## İlk dosyanızı filtreleyin

1. **Dosya aç** ile bir Excel veya CSV seçin. İçeri aktarma ayarlarında doğru sayfayı, başlık satırını ve gerekirse ayraç/kodlamayı seçin.
2. Bir sütun ve koşul seçip filtreyi ekleyin. Örneğin `Tutar` sütununda `1.000,50` ile `5.000,00` aralığını kullanın.
3. İkinci koşulu ekleyin. `Şehir = İstanbul` ve tutar koşulunun birlikte sağlanması için **tümü**, ikisinden birinin yeterli olması için **herhangi biri** seçeneğini kullanın.
4. Sonuç sayısını ve tablodaki değerleri kontrol edin. Sütun başlığıyla sıralayın; gerektiğinde filtreleri tek tek kaldırın.
5. **Dışa aktar** ile formatı, sütunları ve kayıt konumunu seçin. Çıktı yalnızca ekrandaki birkaç satırı değil, filtre sonucunun tamamını içerir.

## Veri okuma ve çıktı davranışı

| Konu | Davranış |
| --- | --- |
| Sayılar | Türkçe `1.234,56` ve uluslararası `1,234.56` biçimleriyle filtreleme; karşılaştırma için yapılan dönüşüm kaynak hücreyi değiştirmez. |
| Tarihler | Gerçek Excel tarihleri ve açık tarih biçimleriyle filtreleme. Tarih aralığının başlangıç ve bitiş günleri dahildir. |
| Kodlar / kimlikler | Metin olarak saklanan baştaki sıfırlar korunur. CSV'nin veri tipi bilgisi yoktur; kimlikleri Excel'e güvenilir biçimde taşımak için `.xlsx` çıktısı kullanın. |
| Başlıklar | Başlık satırı açıkça seçilir; başlıksız tablolar da açılabilir. Eksik ve tekrarlı adlar benzersiz hale getirilir. |
| Boş değerler | Gerçek boş hücreler ile `NA`, `null` gibi metinler ayrı tutulur. |
| CSV | Otomatik ayraç/kodlama algılaması ve elle seçim. Varsayılan çıktı Excel'le uyumlu UTF-8 BOM ve noktalı virgül kullanır. |
| Excel çıktısı | Başlık biçimi, filtre ve sabit başlık satırı; sayı/tarih hücrelerinin yerel tiplerini koruyan yeni çalışma kitabı. |
| CSV formül güvenliği | Varsayılan güvenli çıktı, formül gibi yorumlanabilecek metinlere tek tırnak öneki ekler. Ham metin aktarımı gerekiyorsa bu seçenek kapatılabilir. |

Sütun tipi algılama temkinlidir. Karışık veya anlamı belirsiz bir sütunda filtre için türü kendiniz seçin. Tarihlerde gün/ay/yıl ve ISO yıl/ay/gün biçimleri kullanılır; `03/04/2026` gün/ay/yıl olarak yorumlanır.

Sayı biçiminde **Otomatik** seçiliyken tek ayraçlı `1.234` ve `1,234` değerleri **1,234 ondalık değeri** olarak yorumlanır. Binlik ayracını açıkça belirtmek için **Türkçe** veya **İngilizce** sayı biçimini seçin: Türkçe biçimde `1.234`, İngilizce biçimde `1,234` bin iki yüz otuz dörttür. Otomatik biçimde iki ayraç birlikteyse sonuncusu ondalık ayraçtır; `1.234,56` ile `1,234.56` aynı sayıdır. Bu seçim karşılaştırmayı ve sıralamayı belirler; kaynak metinleri yeniden yazmaz.

## Sınırlar

- DataDesk bir Excel hesaplama motoru değildir. Formüllerde Excel'in en son kaydettiği hesaplanmış değer kullanılır; önbellek değeri olmayan formüller görünür metin olarak tutulur ve uyarı verilir. Böyle bir dosyayı Excel/LibreOffice'te hesaplatıp kaydedin ve yeniden açın.
- Makrolar çalıştırılmaz ve yeni çıktıya taşınmaz. Kaynak dosyanın grafikleri, resimleri, birleşik hücreleri ve özgün biçimlendirmesi yeniden üretilmez; çıktı bir veri tablosudur.
- CSV kodlamasını her dosyada kesin olarak tahmin etmek mümkün değildir. Türkçe karakterler beklediğiniz gibi görünmüyorsa kodlamayı elle seçerek tekrar açın.
- Tablolar belleğe yüklenir; işlenebilecek dosya boyutu bilgisayarın belleğine bağlıdır. Excel'in satır/sütun sınırları geçerlidir. Çok geniş tablolar için Word yerine Excel/CSV tercih edin.
- Eski sürümün masaüstünde oluşturduğu `Veri Düzenleyici VeriTabanı` klasörü taşınmaz veya silinmez. İçindeki dosyaları **Dosya aç** ile doğrudan seçebilirsiniz.

## Geliştirme ve testler

```bash
uv sync --extra dev
uv run --extra dev ruff check .
QT_QPA_PLATFORM=offscreen uv run --extra dev pytest -q
```

`uv` olmadan:

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

PowerShell'de testten önce `$env:QT_QPA_PLATFORM = "offscreen"` kullanın. Ekran açıkken test etmek için bu değişkeni kaldırabilirsiniz. GitHub Actions, Linux üzerinde Python 3.11–3.14 için aynı kontrolleri çalıştırır.

Testler geçici dizinlerde ürettikleri gerçek Excel/CSV dosyalarını yeniden açarak veri, sütun sırası ve filtre sonuçlarını denetler. Arayüz testleri Qt olay döngüsüyle çalışır. İnceleme notları ve elle kontrol senaryoları: [Teknik inceleme](docs/TEKNIK_INCELEME.md).

100.000 satırlık dosya akışını ayrıca doğrulamak için `uv run python tools/benchmark.py` çalıştırın. Araç bağımsız beklenen sonuçlarla karşılaştırma yapar, geçici dosyalarını temizler ve bu bilgisayardaki işlem sürelerini raporlar.

```text
datadesk/
├── app.py          # Uygulama girişi
├── ui.py           # Ana pencere ve kullanıcı akışları
├── dialogs.py      # İçe/dışa aktarma ayarları
├── models.py       # Qt tablo modeli ve çalışma belgesi
├── theme.py        # Arayüz teması
├── core.py         # Tip algılama, filtreleme ve sıralama
└── io.py           # Dosya okuma ve atomik dışa aktarma
tests/              # Veri motoru, dosya ve arayüz testleri
docs/               # İnceleme notları
Excel_project/main.py  # Eski çalıştırma yoluna uyumluluk
```

## Lisans

[MIT](LICENSE).
