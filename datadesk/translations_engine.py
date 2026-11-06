"""English messages for table processing; cell contents are never translated."""

from .i18n import register_translations, tr as tr

EN = {
    "Geçersiz sayı biçimi; Otomatik, Türkçe veya İngilizce seçin.": "Invalid number format; choose Automatic, Turkish or English.",
    "Geçersiz sütun türü.": "Invalid column type.",
    "1234,56 veya 1234.56": "1234,56 or 1234.56",
    "Seçili sayı biçimine uygun bir değer girin (örnek: {example}).": "Enter a value in the selected number format (for example: {example}).",
    "Geçerli bir tarih girin (örnek: 31.12.2026 veya 2026-12-31).": "Enter a valid date (for example: 31.12.2026 or 2026-12-31).",
    "Evet / Hayır veya True / False girin.": "Enter Yes / No or True / False.",
    "Filtre değeri boş bırakılamaz.": "A filter value is required.",
    "En az bir eşleşme değeri girin.": "Enter at least one matching value.",
    "Bilinmeyen filtre işlemi: {operator}": "Unknown filter operator: {operator}",
    "Aralık ve büyüklük filtreleri için Sayı veya Tarih türünü seçin.": "Choose Number or Date for range and comparison filters.",
    "Filtre değeri boş bırakılamaz; boş hücreler için 'Boş' filtresini kullanın.": "A filter value is required; use the 'Is empty' filter for empty cells.",
    "Aralığın başlangıcını ve bitişini girin.": "Enter the start and end of the range.",
    "Aralık başlangıcı bitişten büyük olamaz.": "The start of the range cannot be greater than its end.",
    "Filtre birleştirme türü 'all' veya 'any' olmalıdır.": "Filter matching must be 'all' or 'any'.",
    "Sütun bulunamadı: {column}": "Column not found: {column}",
    "Aynı adlı sütunlar önce benzersiz adlarla içe aktarılmalıdır.": "Columns with duplicate names must first be imported with unique names.",
    "Dosya bulunamadı: {name}": "File not found: {name}",
    "Desteklenen giriş biçimleri: XLSX, XLSM, XLS, CSV ve TSV.": "Supported input formats: XLSX, XLSM, XLS, CSV and TSV.",
    "Dosya {encoding} kodlamasıyla okunamadı. Kodlamayı değiştirin.": "The file could not be read using {encoding}. Choose a different encoding.",
    (
        "UTF-8 olmayan CSV, Windows Türkçe (CP1254) ile okundu. Harfler yanlış görünüyorsa içe"
        " aktarma kodlamasını CP1252 veya başka bir kodlama olarak değiştirin."
    ): (
        "The CSV is not UTF-8 and was read using Windows Turkish (CP1254). If characters look "
        "incorrect, change the import encoding to CP1252 or another encoding."
    ),
    "Dosyanın metin kodlaması belirlenemedi. Kodlamayı elle seçin.": "The file encoding could not be detected. Choose an encoding manually.",
    "CSV ayıracı tek bir karakter olmalıdır (ör. ; , veya sekme).": "The CSV delimiter must be one character (for example: ; , or a tab).",
    ("Metin kodlaması otomatik belirlenemedi. İçe aktarma penceresinde kodlamayı elle seçin."): (
        "The text encoding could not be detected automatically. Choose an encoding in the import dialog."
    ),
    "Excel dosyası açılamadı: {error}": "The Excel file could not be opened: {error}",
    "Sütun {position}": "Column {position}",
    "Başlık satırı 1 veya daha büyük olmalıdır.": "The header row must be 1 or greater.",
    "Dosya veya seçilen sayfa boş.": "The file or selected sheet is empty.",
    "Başlık satırı dosyadaki satır sayısını aşıyor.": "The header row is beyond the last row in the file.",
    "Dosyada okunabilir sütun bulunamadı.": "No readable columns were found in the file.",
    "Seçilen Excel sayfası bulunamadı.": "The selected Excel sheet was not found.",
    (
        "{count} formül hücresinin kayıtlı sonucu yok; formül metni gösteriliyor. Sonuçlarla "
        "filtrelemek için dosyayı Excel veya LibreOffice'te yeniden hesaplayıp kaydedin. "
        "DataDesk formülleri yeniden hesaplamaz."
    ): (
        "Formula cells without a saved result: {count}. Their formula text is shown. To filter "
        "calculated results, recalculate and save the file in Excel or LibreOffice. DataDesk "
        "does not recalculate formulas."
    ),
    "CSV, {line}. satırda okunamadı: {error}": "The CSV could not be read at line {line}: {error}",
    (
        "CSV {record}. kayıtta {actual} alan içeriyor; beklenen {expected}. Ayıraç ve tırnak "
        "işaretlerini kontrol edin. Hiçbir satır atlanmadı."
    ): (
        "CSV record {record} contains {actual} fields; expected {expected}. Check the "
        "delimiter and quotation marks. No rows were skipped."
    ),
    "Dosya okunamadı: {error}": "The file could not be read: {error}",
    "Excel sınırı aşıldı (1.048.575 veri satırı, 16.384 sütun). CSV kullanın.": "Excel limits exceeded (1,048,575 data rows, 16,384 columns). Use CSV.",
    "Excel sayfa adı 1–31 karakter olmalı ve \\ / * ? : [ ] içermemelidir.": "An Excel sheet name must contain 1–31 characters and cannot contain \\ / * ? : [ ].",
    "Bir hücre veya başlık Excel'in 32.767 karakter sınırını aşıyor. CSV kullanın.": "A cell or heading exceeds Excel's 32,767-character limit. Use CSV.",
    ("Bir hücre Excel'in desteklemediği denetim karakteri içeriyor. CSV kullanın veya metni düzeltin."): (
        "A cell contains a control character that Excel does not support. Use CSV or correct the text."
    ),
    "Bir hücre Excel'in 32.767 karakter sınırını aşıyor. CSV kullanın.": "A cell exceeds Excel's 32,767-character limit. Use CSV.",
    "DataDesk · Sonuçlar": "DataDesk · Results",
    "{rows:,} satır · {columns} sütun": "Rows: {rows:,} · Columns: {columns}",
    "Desteklenen çıktı biçimleri: XLSX, CSV, TSV ve DOCX.": "Supported output formats: XLSX, CSV, TSV and DOCX.",
    "Çıktı sütun başlıkları benzersiz olmalıdır.": "Output column headings must be unique.",
    "Çıktı sütun seçimi geçersiz.": "The output column selection is invalid.",
    "Dışa aktarmak için en az bir sütun seçin.": "Select at least one column to export.",
    "Çıktı klasörü bulunamadı.": "The output folder was not found.",
    "Dosya kaydedilemedi: {error}": "The file could not be saved: {error}",
    "Bir ad yazın.": "Enter a name.",
    "Ad nokta ile başlayamaz.": "The name cannot start with a dot.",
    "Adın başında veya sonunda boşluk, sonunda nokta bulunamaz.": "The name cannot start or end with a space, or end with a dot.",
    'Ad; / \\ : * ? " < > | veya denetim karakteri içeremez.': 'The name cannot contain / \\ : * ? " < > | or control characters.',
    "Bu ad Windows tarafından ayrılmış. Başka bir ad seçin.": "This name is reserved by Windows. Choose a different name.",
    "Ad çok uzun. Daha kısa bir ad yazın.": "The name is too long. Enter a shorter name.",
    "Güvenli taşıma bu sistemde desteklenmiyor.": "Safe file moves are not supported on this system.",
    "Çalışma alanı klasörü bulunamadı.": "The workspace folder was not found.",
    "Çalışma alanı açılamadı: {error}": "The workspace could not be opened: {error}",
    "Çalışma alanı kaydı bir bağlantı; dosyalar güvenli kaydetme için tanınamadı.": "The workspace record is a symbolic link; files could not be verified for safe saving.",
    "Çalışma alanı kaydı okunamadı; mevcut dosyalar Farklı Kaydet ile korunacak.": (
        "The workspace record could not be read; existing files will be protected by using Save As."
    ),
    (
        "Dosya işlemi tamamlandı ancak çalışma alanı kaydı güncellenemedi. Bu dosyada Farklı Kaydet kullanın."
    ): (
        "The file operation completed, but the workspace record could not be updated. Use Save"
        " As for this file."
    ),
    "Kaydedilebilir bir XLSX, CSV veya TSV dosyası seçin.": "Choose a writable XLSX, CSV or TSV file.",
    "Dosya kaydı güncellenemedi: {error}": "The file record could not be updated: {error}",
    "Çalışma alanının dışındaki bir yol kullanılamaz.": "A path outside the workspace cannot be used.",
    "Dosya veya klasör bulunamadı ya da erişilemiyor.": "The file or folder was not found or cannot be accessed.",
    "Çalışma alanında sembolik bağlantılar kullanılamaz.": "Symbolic links cannot be used inside the workspace.",
    "Dosya veya klasör bulunamadı.": "The file or folder was not found.",
    "Bir klasör seçin.": "Choose a folder.",
    "Klasör okunamadı: {error}": "The folder could not be read: {error}",
    "“{name}” zaten var. Başka bir ad seçin.": "“{name}” already exists. Choose a different name.",
    "Klasör oluşturulamadı: {error}": "The folder could not be created: {error}",
    "Yeni dosya biçimi XLSX, CSV veya TSV olmalıdır.": "The new file format must be XLSX, CSV or TSV.",
    "En az bir boş olmayan sütun adı yazın.": "Enter at least one non-empty column name.",
    "Sütun adları birbirinden farklı olmalıdır.": "Column names must be unique.",
    "Excel dosyasında en fazla 16.384 sütun olabilir.": "An Excel file can contain at most 16,384 columns.",
    "Sayfa1": "Sheet1",
    "Dosya oluşturulamadı: {error}": "The file could not be created: {error}",
    "Yalnızca XLSX, XLSM, XLS, CSV ve TSV dosyaları eklenebilir.": "Only XLSX, XLSM, XLS, CSV and TSV files can be added.",
    "Dosyalar eklenemedi: {error}": "The files could not be added: {error}",
    "Çalışma alanının ana klasörü yeniden adlandırılamaz.": "The workspace root folder cannot be renamed.",
    "Dosyanın uzantısını değiştirmeden yeniden adlandırın.": "Rename the file without changing its extension.",
    "Ad değiştirilemedi: {error}": "The name could not be changed: {error}",
    "Çalışma alanının ana klasörü taşınamaz.": "The workspace root folder cannot be moved.",
    "Bir klasör kendi içine taşınamaz.": "A folder cannot be moved inside itself.",
    "Dosya veya klasör taşınamadı: {error}": "The file or folder could not be moved: {error}",
    "Metin": "Text",
    "Sayı": "Number",
    "Tarih": "Date",
    "Mantıksal": "Boolean",
    "Evet": "Yes",
    "Hayır": "No",
    "{column} · {kind}\nSıralamak için tıklayın.": "{column} · {kind}\nClick to sort.",
}

register_translations(EN)
