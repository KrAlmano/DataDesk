# DataDesk kullanım kılavuzu

DataDesk, Excel ve CSV verilerini cihazınızda açıp filtrelemenizi ve sonucu ayrı bir dosyaya kaydetmenizi sağlar. macOS ve Windows'ta çalışma alanı aynıdır; macOS kısayollarında **Cmd**, Windows'ta **Ctrl** kullanılır.

Önce [kurulum paketini indirin](https://github.com/KrAlmano/DataDesk/releases/latest). İşletim sisteminize ait adımlar: [macOS kurulumu](MACOS.md) · [Windows kurulumu](WINDOWS.md). Hazır paketi kullanırken Python veya Excel kurmanız gerekmez.

## 1. Dosyayla başlayın veya örneği deneyin

**Dosya aç** ile kendi dosyanızı seçin; dosyayı pencereye sürükleyerek de açabilirsiniz. Desteklenen girişler: `.xlsx`, `.xlsm`, `.xls`, `.csv` ve `.tsv`.

Uygulamayı denemek için **Örnek veriyi keşfet** düğmesini kullanın. Ekran görüntülerindeki satış kayıtları bu düğmeyle açılan **yapay örnek verilerdir**; gerçek müşteri verisi içermez.

![DataDesk başlangıç ekranı](screenshots/01-start.png)

## 2. Sayfayı, başlığı ve sütunları kontrol edin

1. Excel'de **Excel sayfası** alanından doğru sayfayı seçin.
2. **Başlık satırı** alanına sütun adlarının bulunduğu satırı yazın. Örneğin dosyada iki açıklama satırı varsa başlık satırı `3` olabilir. Başlık yoksa **Dosyada başlık yok** seçeneğini işaretleyin.
3. CSV'de sütunlar tek alanda görünüyorsa **CSV ayırıcısı** seçimini değiştirin. Türkçe karakterler bozuksa **CSV kodlaması** alanından, örneğin **Türkçe Windows (1254)** seçin.
4. Ayar değiştirdiğinizde **Önizlemeyi yenile** ile ilk satırları kontrol edin. İlk kaydın, kodların ve sütunların doğru olduğunu görünce **Dosyayı aç** düğmesine basın.

Eksik veya tekrarlanan başlıklar benzersiz adlarla açılır. Kaynak dosya bu işlem sırasında değiştirilmez.

![Excel sayfası ve başlık satırıyla içe aktarma önizlemesi](screenshots/02-import.png)

## 3. Bir veya birden fazla filtre ekleyin

**Filtreler → Koşul ekle** bölümünde sütunu, koşulu ve değeri seçip **Filtre ekle** düğmesine basın. Uygulama sütunun veri türünü gösterir. Karışık bir sütunda gerektiğinde **Metin**, **Sayı** veya **Tarih olarak işle** seçebilirsiniz; bu seçim kaynak hücreleri yeniden yazmaz.

Örnek satış verisinde aşağıdaki iki koşulu ekleyin:

| Sütun | Koşul | Değerler |
| --- | --- | --- |
| Tutar | Arasında (dahil) | Alt sınır `5.000,00`, üst sınır `20.000,00`; sayı biçimi **Türkçe** |
| Durum | Eşittir | `Tamamlandı` |

![Tutar aralığı için filtre oluşturma](screenshots/03-filter-builder.png)

**Aktif** sekmesindeki **Tümü eşleşsin (VE)** seçeneği iki koşulu da sağlayan kayıtları getirir. **Biri eşleşsin (VEYA)** seçeneği koşullardan en az birini sağlayanları getirir. Yukarıdaki iki koşul, örnek veride **VE** ile 37 satır döndürür.

- Tarih aralığı için örneğin `01.10.2026` ve `31.10.2026` kullanın; bitiş gününün tamamı dahildir.
- **Türkçe** sayı biçiminde `1.234` bin iki yüz otuz dörttür. **İngilizce** biçimde aynı sayı `1,234` yazılır. **Otomatik** biçimde tek nokta veya virgül ondalık sayılır; belirsiz binlik ayıracında biçimi açıkça seçin.
- **Boştur / Boş değildir** koşullarında değer girmeniz gerekmez.
- **Listedekilerden biri** için değerleri noktalı virgülle ayırın: `İstanbul; Ankara` veya ondalık sayılarda `1,5; 2,5`.

Tablonun üstündeki arama kutusu bütün sütunlarda arar ve aktif filtre sonucunu ayrıca daraltır. Metin araması büyük/küçük harfe duyarsızdır.

![İki koşulla filtrelenmiş örnek sonuç tablosu](screenshots/04-results.png)

## 4. Sıralayın ve gerekiyorsa düzenleyin

Sütun başlığına bir kez tıklayarak artan, tekrar tıklayarak azalan sıralayın. Sayı ve tarihler veri türüne göre sıralanır; sonuç sırası dışa aktarıma da taşınır.

Bir hücreyi düzenlemek için çift tıklayın. **＋ Satır** yeni kayıt ekler; seçili satırlar **Satır sil / Seçili satırları sil** düğmesiyle kaldırılır. **↶ (Geri al)** ve **↷ (Yinele)** düğmeleriyle son düzenlemeler arasında geçebilirsiniz; geri alma geçmişi son 10 işlemi tutar.

Düzenlemeler çalışma belleğinde tutulur. Kaynak dosya üzerine yazılmaz; çalışmanızı korumak için sonucu dışa aktarın. Filtreli görünümde yaptığınız düzenleme çalışma tablosundaki ilgili satıra uygulanır ve filtreyi kaldırınca kaybolmaz.

## 5. İstediğiniz sütunları dışa aktarın

1. **Dışa aktar** düğmesine basın. Pencerenin üstündeki satır sayısını kontrol edin.
2. **Dosya biçimi** olarak Excel `.xlsx`, CSV `.csv`, sekmeyle ayrılmış `.tsv` veya Word `.docx` seçin.
3. Çıktıda istemediğiniz sütunların işaretini kaldırın. Sütunları sürükleyerek çıktıdaki sırayı değiştirin.
4. CSV kullanıyorsanız ayırıcıyı ve kodlamayı seçin. Varsayılan UTF-8 BOM ve noktalı virgül, Türkçe veriler için uygundur.
5. **Konum seç ve kaydet** ile kaynak dosyadan farklı bir çıktı adı seçin.

![Biçim ve sütun seçerek dışa aktarma](screenshots/05-export.png)

Çıktı, filtre sonucunun **tüm satırlarını** içerir; ekranda aynı anda görünen satırlarla sınırlı değildir. Sıfır eşleşmede de sütun başlıkları kaydedilir. Baştaki sıfırları olan kimlikleri Excel'e taşırken `.xlsx` seçin; Excel'in CSV açılışındaki otomatik tür tahmini kodları değiştirebilir.

CSV/TSV'de **CSV formül güvenliği** varsayılan olarak açıktır. `=`, `+`, `-` veya `@` ile başlayan metinlere tek tırnak ekler; gerçek sayısal hücreleri değiştirmez. Kaynak metni birebir aktarmak istiyorsanız bu seçeneği kapatın. Excel çıktısında formül gibi başlayan metinler metin olarak tutulur.

Excel formülleri yeniden hesaplanmaz; dosyada kayıtlı sonuçları okunur. Kayıtlı sonucu bulunmayan formüller uyarıyla metin olarak gösterilir. Böyle bir dosyayı Excel/LibreOffice'te hesaplatıp kaydedin ve yeniden açın. Makrolar yeni çıktıya taşınmaz.

## 6. Görünümü sıfırlayın ve ekranınıza uyarlayın

**Aktif** sekmesinde bir koşulu seçip **Seçili filtreyi kaldır** ile tek filtreyi silin. **Sıfırla**, bütün filtreleri, aramayı ve sıralamayı temizler; hücre düzenlemelerini geri almaz.

Dar pencerede yan menü küçülür. **Filtreler** filtre görünümünü açar, **Tabloya dön** sonuçlara döndürür. Geçerli filtre eklendiğinde tablo kendiliğinden açılır. Geniş pencerede tablo ve filtre paneli yan yana kullanılabilir; aralarındaki ayırıcıyı sürükleyerek genişliği ayarlayın.

![Dar pencerede sonuç tablosu](screenshots/06-compact.png)

Alt çubuktaki `−` ve `＋` düğmeleriyle veya **Görünüm** menüsünden arayüzü %75–150 arasında ayarlayın. Yüzde düğmesi %100'e döndürür; tercih sonraki açılış için hatırlanır. Uzun formlarda alanlar kaydırılır, filtre ve dosya işlem düğmeleri görünür kalır.

![Yüzde 150 büyüklükte arayüz](screenshots/07-zoom.png)

## Sık kullanılan kısayollar

| İşlem | macOS | Windows |
| --- | --- | --- |
| Dosya aç | `Cmd+O` | `Ctrl+O` |
| Dışa aktar | `Cmd+Shift+E` | `Ctrl+Shift+E` |
| Bütün tabloda ara | `Cmd+F` | `Ctrl+F` |
| Filtre görünümünü aç/kapat | `Cmd+Shift+F` | `Ctrl+Shift+F` |
| Düzenlemeyi geri al | `Cmd+Z` | `Ctrl+Z` |
| Büyüt / küçült | `Cmd++` / `Cmd+−` | `Ctrl++` / `Ctrl+−` |
| Arayüzü %100'e döndür | `Cmd+0` | `Ctrl+0` |

Alanlar arasında `Tab` ve `Shift+Tab` ile geçebilirsiniz. Seçili tablo satırlarını başlıklarıyla kopyalamak için `Cmd+C` / `Ctrl+C` kullanın.
