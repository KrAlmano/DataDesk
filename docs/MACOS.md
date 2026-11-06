# macOS kurulumu ve paketleme

DataDesk'in macOS ve Windows sürümleri aynı arayüzü ve aynı veri motorunu kullanır. macOS paketi uygulama simgesi, Finder'dan başlatma ve Command kısayollarıyla sisteme uyarlanır. Hazır uygulamada Python veya Microsoft Excel kurulumu gerekmez.

Hazır paket **macOS 14 (Sonoma) veya sonrası** içindir. Kullanılan kilitli Qt/PySide6 ikililerinin dağıtım hedefi bu alt sınırı belirler; Python'un daha eski bir macOS'ta çalışabilmesi, hazır DataDesk paketinin de orada çalışacağı anlamına gelmez.

## Hazır paketi kurma

1. [Desktop packages derlemesinin](https://github.com/KrAlmano/DataDesk/actions/workflows/desktop-packages.yml) son başarılı çalışmasının **Artifacts** bölümünden Mac'inize uygun paketi indirin ve ZIP içeriğini çıkarın. İndirme GitHub oturumu gerektirebilir:
   - Apple Silicon, M serisi: `DataDesk-<sürüm>-macos-arm64.dmg`
   - Intel: `DataDesk-<sürüm>-macos-x86_64.dmg`
2. DMG dosyasını açın ve **DataDesk.app** simgesini **Applications** klasörüne sürükleyin.
3. Kopyalama bitince disk görüntüsünü çıkarın ve **Applications → DataDesk** üzerinden başlatın.

Uygulamayı kapatıp yeni sürümü aynı Applications klasörüne kopyalayarak güncelleyin. Uygulamayı kaldırmak için DataDesk.app dosyasını Çöp Sepeti'ne taşıyın. Excel/CSV dosyalarınız ve çıktılarınız uygulama paketinin dışında kalır.

### İmza ve ilk açılış

Yerel geliştirme paketleri ad hoc imzalanabilir; bu, Apple Developer ID imzası veya Apple noter onayı anlamına gelmez. Dağıtılan paketin gerçek imzalama durumunu sürüm notları belirtir. Apple dışında dağıtılan yeni yazılımlarda Developer ID ve noter onayı, macOS'un geliştiriciyi ve paketi doğrulamasını sağlar. [Apple imzalama ve noter onayı belgeleri](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

macOS bir geliştirme paketini açmayı engellerse önce doğru depodan indirdiğinizi ve sürümün imzalama durumunu kontrol edin. Yalnızca kaynağına güvendiğiniz kendi geliştirme paketinizi açmak için Apple'ın **Sistem Ayarları → Gizlilik ve Güvenlik → Yine de Aç** akışını kullanabilirsiniz. Bu, yalnızca ilgili uygulama için kullanıcının verdiği bir istisnadır; sistem korumasını kapatmak gerekmez. [Apple'ın ilk açılış açıklaması](https://support.apple.com/en-ie/102445).

## Kaynaktan çalıştırma

Python 3.12 ve [uv](https://docs.astral.sh/uv/) ile:

```bash
git clone https://github.com/KrAlmano/DataDesk.git
cd DataDesk
uv run datadesk
```

Bu yol geliştiriciler içindir. Hazır DMG kurulumu bu araçları gerektirmez.

## Yerel uygulama ve DMG oluşturma

Derlemeyi hedef mimariyle eşleşen macOS/Python ortamında çalıştırın. Apple Silicon ve Intel paketleri kendi macOS ortamlarında üretilir; bir makinede diğer mimarinin bağımlılıkları karıştırılmaz.

```bash
uv sync --extra build
bash packaging/macos/build.sh
```

Üretilen uygulama `dist/DataDesk.app`, kurulum dosyası `dist/installers/DataDesk-<sürüm>-macos-<mimari>.dmg` konumundadır. Betik Mach-O mimarisini, paket kimliğini ve kod imzasının bütünlüğünü denetler; DMG sağlama toplamını doğrular ve yanında `.sha256` dosyası yazar.

Uygulama daha önce derlendiyse yalnızca paketleme:

```bash
bash packaging/macos/build.sh --skip-build --arch arm64
```

Özel çıktı klasörü için `--output-dir "/tam/yol/çıktılar"` kullanın. `--arch x86_64` ile Intel paketini belirtin; betik istenen mimari uygulamada yoksa işlemi durdurur. Paketleme kaynak verilerinizi, sistem tarayıcınızı veya güvenlik ayarlarınızı değiştirmez.

### Developer ID ve noter onayıyla dağıtım

Apple Developer hesabınızın **Developer ID Application** sertifikasını derleme makinesinin Keychain'ine yükleyin. Noter onayı kimlik bilgilerini `notarytool store-credentials` ile ayrı bir Keychain profiline kaydedin; parolaları veya sertifikaları depoya koymayın.

```bash
export MACOS_SIGN_IDENTITY="Developer ID Application: Şirket Adı (TEAMID)"
export APPLE_NOTARY_PROFILE="datadesk-notary"
bash packaging/macos/build.sh
```

Ortak derleyici bu kimlikle iç içe ikili dosyaları ve uygulamayı imzalar. Paketleme betiği uygulamayı noter onayına gönderir, bileti uygulamaya ekler; ardından DMG'yi oluşturur, imzalar ve DMG'nin noter biletini de ekleyip doğrular. İşlem reddedilirse dağıtım başarılı sayılmaz; yanıt JSON dosyaları `dist/installers` altında incelenebilir. Apple bu işlem için Developer ID, Hardened Runtime ve güvenli zaman damgası ister; ad hoc imza noter onayının yerine geçmez. [Apple dağıtım iş akışı](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).

Bu değişkenler verilmezse betik yerel geliştirme paketi üretir ve noter onayının yapılmadığını açıkça bildirir. `APPLE_NOTARY_PROFILE` verilirse geçerli Developer ID kimliği zorunludur. Betik Gatekeeper'ı kapatmaz, karantina özniteliklerini silmez ve yönetici yetkisi istemez.

## Paketi doğrulama

```bash
hdiutil verify dist/installers/DataDesk-1.0.0-macos-arm64.dmg
codesign --verify --deep --strict dist/DataDesk.app
QT_QPA_PLATFORM=offscreen dist/DataDesk.app/Contents/MacOS/DataDesk --smoke-test /tmp/datadesk-macos-smoke.json
bash packaging/macos/verify.sh dist/installers/DataDesk-1.0.0-macos-arm64.dmg
```

Smoketest kurulu Python yerine uygulamanın gömülü çalışma ortamını kullanır. `verify.sh`, DMG'yi salt okunur bağlar, Applications kısayolunu denetler ve uygulamayı geçici bir kurulum klasörüne kopyalayıp gömülü çalışma ortamıyla test eder; gerçek Applications klasörünü değiştirmez. Raporu DMG'nin yanında `-smoke.json` adıyla tutar. Farklı bir Mac'te Applications klasörüne kopyalanmış uygulamayla da açılış, dosya okuma, filtreleme ve çıktı alma akışlarını denetleyin. Bir mimarideki yerel test, diğer mimarinin veya başka bir macOS sürümünün çalıştığını tek başına kanıtlamaz.
