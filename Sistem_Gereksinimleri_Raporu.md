# E-AETIS / Ethernet BSP — Sistem Gereksinimleri Raporu

**Proje:** E-AETIS (Advanced Ethernet Testing & Inspection System) — STM32 tabanlı, taşınabilir, bare-metal Ethernet BSP ve buna eşlik eden masaüstü test/teşhis arayüzü
---

## 1. Giriş ve Amaç

Projenin nihai hedefi iki parçadan oluşur:

1. **Gömülü taraf:** STM32H5 (ve ailesi genişletildiğinde H7/F4/F7) mikrodenetleyicileri üzerinde, işletim sistemi (RTOS) ve hazır ağ yığını (LwIP) kullanmadan, doğrudan register erişimiyle çalışan bir Ethernet Board Support Package (BSP).
2. **Masaüstü taraf:** Bu BSP'nin çalıştığı kartla UDP üzerinden konuşan, PyQt5 tabanlı bir test/teşhis/firmware güncelleme arayüzü (E-AETIS GUI).

Bu rapor, bu iki parçayı birlikte üretebilmek için gerekli olan tüm ön koşulları kapsar.

## 2. Kapsam

- Hedef MCU ailesi: STM32H563 / STM32H743 (Synopsys EQOS Ethernet MAC) ve STM32F407 / STM32F767 (klasik ST/DWC GMAC)
- Hedef PHY çipleri: LAN8720A, LAN8742A, KSZ8081
- Desteklenen protokoller: ARP, ICMP (ping), UDP (özel komut protokolü + IAP firmware güncelleme)
- Masaüstü arayüz: kart keşfi, telemetri izleme, PHY/DMA teşhisi, performans testi, IAP yönetimi

---

## 3. Donanım Gereksinimleri

### 3.1 Hedef Kart / MCU
| Gereksinim | Açıklama |
|---|---|
| MCU | STM32H563ZITx (Cortex-M33) veya ailesi destekleyen diğer bir STM32 (H743/F407/F767) |
| Flash / RAM | Projede kullanılan referans kart için ≥2 MB Flash, ≥640 KB RAM |
| Sistem saati | ≥250 MHz'e çıkabilen bir PLL yapılandırması (dahili osilatör + PLL yeterli) |
| MPU | ARMv7-M/ARMv8-M MPU desteği (DMA erişimli bellek bölgesini non-cacheable işaretlemek için zorunlu) |

### 3.2 Ethernet Donanımı
| Gereksinim | Açıklama |
|---|---|
| MAC | MCU'ya entegre, RMII arayüzü destekleyen Ethernet MAC (EQOS veya GMAC ailesi) |
| PHY | Harici PHY çipi (LAN8720A / LAN8742A / KSZ8081), RMII üzerinden MAC'e bağlı |
| RMII referans saati | 50 MHz — genellikle PHY'nin kendi kristali üzerinden üretilir |
| Fiziksel katman | RJ45 konnektör + magnetics (trafo) |
| PHY reset | Donanımsal reset hattı (opsiyonel, yazılımdan açılıp kapatılabilir) |

### 3.3 Programlama / Debug Donanımı
- ST-Link V2/V3 (veya kart üzerinde entegre debugger) — SWD üzerinden flash yükleme ve debug
- USB kablosu (PC–kart bağlantısı)

### 3.4 Test Ortamı
- Ethernet kablosu ve bir switch/router (kartı ve test PC'sini aynı ağ segmentine almak için)
- GUI'nin çalışacağı bir PC (Ethernet portu veya USB-Ethernet adaptörü ile)

---

## 4. Yazılım ve Geliştirme Ortamı Gereksinimleri

### 4.1 Gömülü Yazılım Tarafı
| Araç | Amaç |
|---|---|
| `arm-none-eabi-gcc` | ARM Cortex-M için çapraz derleyici (toolchain) |
| CMake ≥ 3.22 + Ninja | Build sistemi |
| STM32CubeMX | Pin/saat/peripheral konfigürasyonu, HAL kod üretimi (`.ioc` dosyası üzerinden) |
| STM32CubeIDE veya VS Code + Cortex-Debug | Geliştirme ve donanım üzerinde debug |
| STM32CubeProgrammer / OpenOCD | Flash'a yükleme |
| Git | Versiyon kontrolü |

### 4.2 Masaüstü Uygulama (GUI) Tarafı
| Araç | Amaç |
|---|---|
| Python 3 | GUI'nin çalışma ortamı |
| PyQt5 | Arayüz kütüphanesi |
| `socket`, `struct`, `zlib` (standart kütüphane) | UDP haberleşme, binary paket kodlama, CRC32 bütünlük kontrolü |

---

## 5. Fonksiyonel Gereksinimler

Sistemin yapması gereken işler:

| # | Gereksinim |
|---|---|
| FR1 | Kart, RMII üzerinden PHY ile haberleşip link durumunu (bağlı/kopuk, hız, duplex) tespit edebilmeli |
| FR2 | Kart, statik IP/MAC ile ağda görünür olmalı; gelen ARP isteklerine otomatik yanıt vermeli |
| FR3 | Kart, ICMP echo (ping) isteklerine yanıt vermeli |
| FR4 | Kart, özel bir UDP komut protokolünü (keşif, istatistik sorgulama, performans testi, değişken listeleme) işleyebilmeli |
| FR5 | Kart, kullanıcı tanımlı değişkenleri (sensör okuma, LED durumu vb.) arayüze kayıt/keşif mekanizmasıyla açabilmeli; isteğe bağlı olarak kendiliğinden (push) telemetri gönderebilmeli |
| FR6 | Kart, GUI üzerinden gönderilen yeni bir firmware'i IAP (In-Application Programming) ile flash'a yazabilmeli ve CRC32 ile bütünlüğünü doğrulayabilmeli |
| FR7 | Kart, tanımadığı komutları (örn. LED aç/kapa) uygulama geliştiricisinin tanımladığı bir işleyiciye yönlendirebilmeli |
| FR8 | GUI, ağdaki kartı broadcast ile otomatik keşfedebilmeli; PHY/DMA istatistiklerini, bağlantı kalitesini ve performans/jitter değerlerini görüntüleyebilmeli |

---

## 6. Fonksiyonel Olmayan Gereksinimler

| # | Gereksinim | Neden |
|---|---|---|
| NFR1 | **Taşınabilirlik** — kod tabanı, MAC ailesi ve PHY çipinden bağımsız üç eksenli bir mimariyle tasarlanmalı | Yeni bir MCU/PHY eklerken mevcut dosyaların değişmemesi, sadece yeni bir dosya eklenmesi gerekir |
| NFR2 | **Sınırlı bellek içinde çalışma** — DMA descriptor + buffer alanı, ayrılan sabit bölgeyi (tipik 32 KB) aşmamalı | Bu bölge genelde SRAM'in küçük, DMA'nın erişebildiği özel bir kısmıdır |
| NFR3 | **Bloklamayan (non-blocking) çalışma** — ana döngüdeki paket işleme fonksiyonu beklemeden dönmeli | RTOS olmadığı için tek görev tüm sistemi bloklayabilir |
| NFR4 | **Bellek tutarlılığı** — D-Cache'li hedeflerde DMA erişimli bölge MPU ile "non-cacheable" işaretlenmeli | Aksi halde CPU ve DMA'nın gördüğü veri birbirini tutmaz (cache coherency sorunu) |
| NFR5 | **Kullanım kolaylığı** — hedef donanıma özgü tüm ayarlar tek bir yapılandırma dosyasında toplanmalı, çekirdek dosyalara dokunulmamalı | Entegrasyon süresini ve hata riskini azaltır |
| NFR6 | **Güvenlik sınırı** — IAP mekanizmasında kimlik doğrulama olmadığından bu özellik yalnızca izole/güvenilir ağlarda kullanılmalı | Yetkisiz kullanıcı flash'a yazabilir; bu bilinen ve kabul edilmiş bir kısıttır |

---

## 7. Gerekli Bilgi ve Beceri Alanları

Bu tür bir projeyi geliştirebilmek için ihtiyaç duyulan teorik ve pratik bilgi alanları:

1. **Gömülü C programlama (C11)** — register seviyesinde donanım erişimi, CMSIS kullanımı
2. **ARM Cortex-M mimarisi** — kesme sistemi (NVIC), MPU (bellek koruma birimi), FPU
3. **Ethernet donanım katmanı** — MAC/PHY ayrımı, RMII arayüzü, MDIO/SMI yönetim protokolü, DMA descriptor ring (RX/TX) yönetimi
4. **Ağ protokolleri** — Ethernet II çerçeve formatı, ARP, ICMP, IP, UDP; bunların hazır kütüphane (LwIP) kullanmadan uçtan uca elle yazılması
5. **Linker script ve bellek haritası** — bölüm (section) yerleştirme, cacheable/non-cacheable bellek bölgeleri, MPU bölge hizalama kuralları
6. **Flash programlama ve bootloader mantığı** — IAP (In-Application Programming), sektör yazma, bütünlük doğrulama (CRC32)
7. **Çapraz derleme (cross-compilation)** — CMake + arm-none-eabi-gcc toolchain kurulumu ve yönetimi
8. **STM32CubeMX ile donanım konfigürasyonu** — saat ağacı (clock tree), pin haritası, peripheral başlatma
9. **Python ile masaüstü uygulama geliştirme** — PyQt5, soket (UDP) programlama, threading
10. **Versiyon kontrolü** — Git/GitHub ile bireysel/takım geliştirme süreci
11. **Donanım doğrulama becerisi** — osiloskop/lojik analizör ile RMII saat/veri hatlarının incelenmesi, SWD/JTAG ile debug

---

## 8. Test ve Doğrulama Gereksinimleri

| Aşama | Doğrulama |
|---|---|
| 1 | Register bit yerleşimlerinin ilgili MCU referans kılavuzundan (Reference Manual) doğrulanması |
| 2 | PHY adresinin taranarak (adres tarama fonksiyonu) doğru PHY ID'nin okunabildiğinin doğrulanması — projenin ilk fonksiyonel testi |
| 3 | Link durumu, hız ve duplex modunun doğru tespit edildiğinin doğrulanması |
| 4 | ARP/ICMP/UDP fonksiyonel testleri (GUI üzerinden keşif ve ping) |
| 5 | Performans ve jitter testi |
| 6 | Hata enjeksiyonu testi (örn. parçalanan paketlerin beklenen şekilde reddedilmesi) |
| 7 | IAP güncelleme testi (CRC doğrulama, başarılı/başarısız yazma senaryoları) |

---

## 9. Bilinen Kısıtlar / Riskler

- IP fragment reassembly (parçalanmış paketleri birleştirme) desteklenmiyor — tasarım kararı
- TCP desteklenmiyor, yalnızca UDP/ICMP/ARP
- Tek DMA kanalı ve tek kuyruk — QoS/VLAN önceliklendirme yok
- IAP'de kimlik doğrulama yok, yalnızca bütünlük (CRC32) kontrolü var
- Kesme tabanlı değil, polling tabanlı çalışma — gecikme, ana döngünün çağrı sıklığına bağımlı

---

## 10. Sonuç

Bu proje, hem gömülü sistemler (register seviyesi donanım programlama, ağ protokolleri, bellek yönetimi) hem de masaüstü yazılım (Python/GUI, soket programlama) alanlarını bir arada gerektiren, uçtan uca bir mühendislik çalışmasıdır. Yukarıdaki donanım, yazılım, bilgi/beceri ve doğrulama gereksinimleri, projenin sıfırdan geliştirilebilmesi için gerekli asgari çerçeveyi oluşturur.
