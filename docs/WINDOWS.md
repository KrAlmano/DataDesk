# Windows kurulumu

DataDesk'in Windows ve macOS sürümleri aynı veri motorunu ve aynı arayüzü kullanır. Windows paketi uygulamayı ve gereken Python/Qt bileşenlerini birlikte taşır; son kullanıcı için Python, uv veya Excel kurulumu gerekmez.

## Hazır paketle kurulum

1. İlgili [GitHub derleme çalışmasının](https://github.com/KrAlmano/DataDesk/actions) **Artifacts** alanından Windows x64 kurulum paketini alın. Artifacts bir ZIP olarak indirilirse önce içeriğini çıkartın.
2. `DataDesk-1.0.0-windows-x64-setup.exe` dosyasını açın. Yeni sürümlerde dosya adındaki sürüm numarası değişir.
3. Kurulum adımlarını izleyin. DataDesk varsayılan olarak kullanıcının `%LOCALAPPDATA%\Programs\DataDesk` dizinine kurulur; yönetici yetkisi istemez.
4. İsterseniz masaüstü kısayolunu işaretleyin. Uygulamayı **Başlat → DataDesk** üzerinden açın.

Kurulum dili Türkçe veya İngilizce seçilebilir. Uygulamanın veri çalışma alanı her iki işletim sisteminde de Türkçedir. Windows kısayollarında `Ctrl`, macOS kısayollarında `Cmd` kullanılır. Kurulum, Excel/CSV dosyalarının varsayılan açılış uygulamasını değiştirmez.

Paket Windows **10 sürüm 1809 (derleme 17763) veya sonrası / Windows 11, x64** içindir. Bu alt sınır kullanılan Qt 6.12 sürümünün [Windows destek tablosuyla](https://doc.qt.io/qt-6.12/windows.html) eşleşir. Yerel ARM64 paketi yerine x64 paket hazırlanır; ARM cihazlar için doğal ARM64 desteği vaat edilmez.

İmzalı bir dağıtım yayımlanmamışsa Windows yayımcı doğrulaması uygulamanın tanınmadığını gösterebilir. Paketin bu depodaki doğru sürümden geldiğini ve yayımlanan SHA-256 özetiyle eşleştiğini kontrol edin; işletim sisteminin güvenlik ayarlarını değiştirmek gerekmez.

İndirilen dosyanın özetini PowerShell ile görmek için:

```powershell
Get-FileHash .\DataDesk-1.0.0-windows-x64-setup.exe -Algorithm SHA256
```

Değeri paketle birlikte gelen `.exe.sha256` dosyasının ilk alanıyla karşılaştırın.

## Güncelleme ve kaldırma

- Güncellemeden önce açık DataDesk penceresindeki düzenlemeleri dışa aktarın ve uygulamayı kapatın. Yeni kurulum dosyasını çalıştırın; önceki kurulum dizini ve kısayol tercihi korunur.
- Kaldırmak için **Ayarlar → Uygulamalar → Yüklü uygulamalar → DataDesk → Kaldır** yolunu kullanın.
- Kaldırıcı yalnızca kurduğu uygulama dosyalarını ve kısayolları kaldırır. Çalıştığınız Excel/CSV dosyalarını, dışa aktardığınız çıktıları ve kullanıcı tercihlerini silmez.

## Kaynak koddan çalıştırma

Geliştirme için [uv](https://docs.astral.sh/uv/getting-started/installation/) kullanabilirsiniz:

```powershell
git clone https://github.com/KrAlmano/DataDesk.git
cd DataDesk
uv run datadesk
```

Elle Python ortamı oluşturmak isterseniz Python 3.12 ile:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m datadesk
```

Sanal ortamı etkinleştirmek veya PowerShell'in kalıcı yürütme ilkesini değiştirmek gerekmez.

## Windows kurulum dosyasını üretme

Bu adımlar Windows üzerinde uygulanır; Windows uygulaması macOS üzerinde çapraz derlenmez.

Gerekenler: Git, uv ve [Inno Setup 6.4 veya sonrası](https://jrsoftware.org/isdl.php). Paylaşılan paketleyici Python ortamını ve uygulama dosyalarını hazırlar; Inno Setup bunları kullanıcıya özel kurulum dosyasına dönüştürür.

Proje kökünde:

```powershell
pwsh -File packaging/windows/Build-Installer.ps1
```

Windows PowerShell 5.1 ile de çalıştırılabilir:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/windows/Build-Installer.ps1
```

Buradaki yürütme ilkesi yalnızca başlatılan PowerShell işlemi içindir; sistem tercihini değiştirmez.

Çıktılar:

```text
dist/DataDesk/DataDesk.exe
dist/DataDesk/_internal/...
dist/installers/DataDesk-1.0.0-windows-x64-setup.exe
dist/installers/DataDesk-1.0.0-windows-x64-setup.exe.sha256
```

Taşınabilir uygulama klasörünü kullanacaksanız `dist/DataDesk` klasörünün tamamı gerekir; `DataDesk.exe` dosyasını tek başına kopyalamayın. Normal dağıtım için `setup.exe` dosyasını paylaşın.

Derlenmiş uygulamayı tekrar kullanmak veya Inno Setup yolunu belirtmek için:

```powershell
pwsh -File packaging/windows/Build-Installer.ps1 -SkipBundle `
  -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

`-OutputDirectory` verilmezse depo kökündeki `dist` kullanılır. Betik başka dizinden çağrılsa da kaynak yolları depo köküne göre çözülür. Derleyici veya uygulama dosyaları bulunamazsa işlem açık bir hatayla durur.

## Kurulumun doğrulanması

Temiz bir Windows kullanıcısında, üretilen kurulum dosyasını gerçek kurulum/kaldırma akışıyla test edin:

```powershell
pwsh -File packaging/windows/Test-Installer.ps1 `
  -InstallerPath dist/installers/DataDesk-1.0.0-windows-x64-setup.exe `
  -ReportDirectory dist/installer-test-reports
```

Bu test önce mevcut DataDesk kurulumu olmadığını denetler. Ardından geçici, Türkçe ve boşluk içeren bir dizine sessiz kurulum yapar; Başlat kısayolunu ve kurulu uygulamanın gerçek Qt + Excel/CSV/TSV/Word iş akışını doğrular. Son olarak uygulamayı kaldırır ve ayrı bir belgeler dizinindeki kaynak CSV'nin özetinin değişmediğini kontrol eder. Test dosyaları temizlenir; istenen rapor dizininde kurulum/kaldırma günlükleri ile uygulama raporu bırakılır.

Kurulum paketi sessiz çalıştırıldığında uygulama kendiliğinden açılmaz. Etkileşimli kurulumda açılış seçeneği kullanıcı tarafından işaretlenebilir.
