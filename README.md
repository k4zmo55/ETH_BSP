# Ethernet_BSP — E-AETIS

Taşınabilir, bare-metal STM32 Ethernet Board Support Package (BSP). RTOS yok, LwIP yok — yalnızca CMSIS register erişimi ve DMA descriptor ring yönetimi. Yanında, kartla UDP üzerinden konuşan bir masaüstü test/teşhis arayüzü (**E-AETIS GUI**) gelir.

## İçindekiler

- [Genel Bakış](#genel-bakış)
- [Desteklenen Donanım](#desteklenen-donanım)
- [Proje Yapısı](#proje-yapısı)
- [Entegrasyon (3 Adım)](#entegrasyon-3-adım)
- [Yapılandırma — `eth_config.h`](#yapılandırma--eth_configh)
- [Kullanıcı API'si — `eth_app.h`](#kullanıcı-apisi--eth_apph)
- [Mimari](#mimari)
- [Yeni MCU / MAC Ailesi / PHY Eklemek](#yeni-mcu--mac-ailesi--phy-eklemek)
- [E-AETIS Protokolü (UDP)](#e-aetis-protokolü-udp)
- [E-AETIS GUI Aracı](#e-aetis-gui-aracı)
- [Karta Yüklemeden Önce Doğrulama Listesi](#karta-yüklemeden-önce-doğrulama-listesi)
- [Bilinen Sınırlar](#bilinen-sınırlar)
- [Bilinen Depo Sorunları](#bilinen-depo-sorunları)

## Genel Bakış

**E-AETIS** (Advanced Ethernet Testing & Inspection System), Ethernet BSP'nin performansını doğrulamak, ping/ICMP testleri koşmak, kart değişkenlerini gerçek zamanlı izlemek ve IAP bootloader işlemlerini yönetmek için tasarlanmış bir masaüstü test ve telemetri arayüzüdür.

<p align="center">
  <img src="Docs/gui.png" alt="E-AETIS GUI" width="100%">
</p>

**Öne çıkan özellikler:**
- **Kart I/O ve Telemetri:** Otomatik değişken keşfi ve gerçek zamanlı izleme.
- **Ağ Testleri:** Ping (ICMP) testi, UDP konsol loglama, performans/jitter analizi.
- **Teşhis:** PHY / DMA teşhisi ve hata enjeksiyonu (fault injection) modülleri.
- **Firmware Güncelleme:** Entegre Bootloader (IAP) yönetimi.

## Desteklenen Donanım

Hedef MCU ve PHY, `eth_config.h` içinden derleme zamanında **tam olarak bir tanesi** seçilerek belirlenir (`eth_device.h` seçimi doğrular, birden fazla veya hiç seçim yoksa derleme `#error` ile durur).

| Kategori | Desteklenenler | Port katmanı |
|---|---|---|
| MCU | STM32H563, STM32H743 | Synopsys DWC EQOS (`eth_port_eqos.c`) |
| MCU | STM32F407, STM32F767 | Klasik ST/DWC GMAC 3.x (`eth_port_gmac.c`) |
| PHY | LAN8720A, LAN8742A | `eth_phy_lan87xx.c` |
| PHY | KSZ8081 | `eth_phy_ksz80xx.c` |

`eth_config.h`'deki RMII pin haritası varsayılan olarak NUCLEO-H563ZI atamalarını içerir — kendi kart şemanıza göre doğrulanmalı/güncellenmelidir.

## Proje Yapısı

```
ETH_BSP/
├── Inc/
│   ├── eth_config.h      # Kullanıcının düzenlediği TEK dosya
│   ├── eth_app.h          # Uygulamanın include ettiği TEK başlık (kullanıcı API'si)
│   ├── eth_device.h       # MCU → MAC ailesi + yetenek eşlemesi (dokunulmaz)
│   ├── eth_driver.h       # Ortak tipler (ETH_Status_t, ETH_Stats_t...) ve çekirdek driver API'si
│   ├── eth_port.h          # MAC ailesi port sözleşmesi — 21 fonksiyon (dokunulmaz)
│   └── eth_phy.h           # PHY sözleşmesi — 4 fonksiyon (dokunulmaz)
├── Src/
│   ├── eth_driver.c        # Ring yönetimi, sahiplik protokolü, istatistik — register erişimi yok
│   ├── eth_app.c           # ARP / ICMP / UDP / E-AETIS komut işleyicisi
│   ├── eth_iap.c            # IAP bootloader (opsiyonel, `ETH_ENABLE_IAP`)
│   ├── port/
│   │   ├── eth_port_eqos.c  # H5 / H7 register erişimi
│   │   └── eth_port_gmac.c  # F4 / F7 register erişimi
│   └── phy/
│       ├── eth_phy_lan87xx.c
│       └── eth_phy_ksz80xx.c
├── Examples/
│   └── main.c               # Uçtan uca entegrasyon örneği (telemetri değişkenleri, LED getter/setter)
├── Docs/
│   ├── linker_snippet.ld    # `.eth_desc` section'ı için linker script eklentisi
│   └── gui.png
├── PDF/                      # MCU/PHY referans dokümanları
└── ethernet_test_gui.py     # E-AETIS masaüstü GUI (PyQt5)
```

## Entegrasyon (3 Adım)

**1.** `Ethernet_BSP/` klasörünü projeye kopyalayın. `Src/` altındaki **tüm** `.c` dosyalarını build path'e ekleyin — seçilmeyen port ve PHY dosyaları boş derlenir, elle çıkarmanıza gerek yoktur. `Inc/` klasörünü include path'e tanıtın.

**2.** Yalnızca `Inc/eth_config.h` dosyasını düzenleyin: hedef MCU, PHY çipi, IP/MAC, RMII pin haritası, PHY adresi.

**3.** `main.c` içinde tek bir başlık ile başlatın ve ana döngüde çağırın:

```c
#include "eth_app.h"

int main(void) {
    HAL_Init();
    SystemClock_Config();          // 50 MHz RMII referans saati aktif olmalı

    if (ETH_BSP_Init() != ETH_OK) { /* hata kodu nedeni söyler */ }

    while (1) {
        ETH_BSP_ProcessEvents();   // bloklamaz
        // kendi uygulama kodunuz
    }
}
```

Ek olarak linker script'e `.eth_desc` section'ı eklenmelidir (bkz. [`Docs/linker_snippet.ld`](Docs/linker_snippet.ld)). Uçtan uca çalışan bir örnek (sıcaklık/besleme telemetrisi + arayüzden kontrol edilebilir LED) için [`Examples/main.c`](Examples/main.c) dosyasına bakın.

## Yapılandırma — `eth_config.h`

Bu dosya `eth_config.h`'nin **tek elle düzenlenen** dosya olduğu prensibiyle, tüm kullanıcı ayarlarını sekiz grupta toplar:

| # | Grup | İçerik |
|---|---|---|
| 1 | Hedef işlemci | `ETH_TARGET_STM32H563` / `H743` / `F407` / `F767` (sadece biri) |
| 2 | PHY çipi | `ETH_PHY_LAN8720A` / `LAN8742A` / `KSZ8081` (sadece biri) |
| 3 | Ağ kimliği | MAC adresi (6 bayt), IP, netmask, gateway |
| 4 | PHY ayarları | `PHY_ADDRESS`, donanım reset pini, auto-negotiation timeout |
| 5 | RMII pin haritası | Her RMII sinyali için port/pin + `ETH_GPIO_CLOCK_MASK` |
| 6 | DMA / bellek | RX/TX descriptor sayısı (2'nin kuvveti), buffer boyutu, descriptor bölgesi adresi/boyutu, `ETH_HCLK_HZ` |
| 7 | Özellik anahtarları | ARP/ICMP/UDP/istatistik/E-AETIS komut/kullanıcı komut/telemetri/IAP aç-kapa, `ETH_EAETIS_PORT` |
| 8 | Hata ayıklama | `ETH_DEBUG_ENABLE` |

`eth_device.h`, derleme zamanında sağlık kontrolleri yapar: descriptor sayılarının 2'nin kuvveti olması, buffer boyutunun ≥1524 ve 4'ün katı olması, descriptor+buffer toplamının ayrılan bölgeye sığması, ve D-Cache'li hedeflerde MPU non-cacheable ayarının açık olması (`#error` / `#warning` ile).

> **H7 notu:** Descriptor bölgesi DTCM'de (`0x20000000`) olamaz — ETH DMA oraya erişemez; D2 domain SRAM (`0x30000000`) kullanılmalıdır. `eth_device.h` bunu derleme zamanında zorlar.

## Kullanıcı API'si — `eth_app.h`

Uygulama kodunun dokunduğu tek başlık. Öne çıkan fonksiyonlar:

| Fonksiyon | Amaç |
|---|---|
| `ETH_BSP_Init()` | BSP'yi `eth_config.h` ayarlarıyla başlatır. |
| `ETH_BSP_ProcessEvents()` | Ana döngüde sürekli çağrılır; gelen paketleri işler, bloklamaz. |
| `ETH_BSP_SendUDP()` / `ETH_BSP_ReplyUDP()` | UDP datagram gönderir (ARP çözümü otomatik). |
| `ETH_BSP_RegisterUDPCallback()` | Kendi UDP portunuza gelen veriyi almak için kaydolun. |
| `ETH_BSP_RegisterCommandHandler()` | E-AETIS arayüzünden gelen, BSP'nin tanımadığı komutları (LED, sensör vb.) kendi donanımınıza yönlendirir. |
| `ETH_BSP_SendTelemetry()` / `ETH_BSP_TelemetryReady()` | Kart tarafından tetiklenen (push) telemetri; arayüz abone olduktan sonra kullanılır. |
| `ETH_BSP_RegisterVar()` / `ETH_BSP_GetVarCount()` | Arayüzün sorup kartın cevapladığı (pull) değişkenleri (`ETH_Var_t`) kaydeder; GUI `GET_VARS` ile otomatik keşfeder. |
| `ETH_BSP_GetLinkState()` / `ETH_BSP_GetStats()` / `ETH_BSP_GetIPAddress()` | Bağlantı durumu, istatistikler, kendi IP adresi. |

`ETH_Var_t` iki kullanım biçimini destekler: doğrudan bellek erişimi (`ptr`, sensör değişkenleri için) veya fonksiyon üzerinden (`getter`/`setter`, GPIO gibi yan etkisi olan işlemler için). Yapı, ömrü boyunca geçerli kalmalıdır (`static const` olarak tanımlanmalı) — BSP yapıyı kopyalamaz, işaretçisini saklar.

## Mimari

Üç **bağımsız** eksen vardır. Birinde yapılan değişiklik diğerlerini etkilemez.

```
eth_config.h            Kullanıcının dokunduğu tek dosya
    │
eth_device.h            MCU → MAC ailesi + yetenek eşlemesi
    │
    ├── eth_port.h      Port sözleşmesi (21 fonksiyon)
    │     ├── eth_port_eqos.c    Synopsys DWC EQOS   → H5, H7
    │     └── eth_port_gmac.c    Klasik ST/DWC 3.x   → F4, F7
    │
    ├── eth_phy.h       PHY sözleşmesi (4 fonksiyon)
    │     ├── eth_phy_lan87xx.c  LAN8720A, LAN8742A
    │     └── eth_phy_ksz80xx.c  KSZ8081
    │
    ├── eth_driver.c    Ring, sahiplik protokolü, istatistik
    │                   → tek bir register erişimi içermez
    │
    └── eth_app.c       ARP / ICMP / UDP / E-AETIS komutları
          └── eth_iap.c IAP bootloader (opsiyonel)
```

## Yeni MCU / MAC Ailesi / PHY Eklemek

**Yeni MCU:** `eth_device.h` içine bir blok eklemek yeterlidir:

```c
#elif defined(ETH_TARGET_STM32F429)
  #include "stm32f4xx.h"
  #define ETH_PORT_EQOS         0
  #define ETH_PORT_GMAC         1
  #define ETH_HAS_DCACHE        0
  #define ETH_RMII_VIA_SYSCFG_PMC 1
  #define ETH_GPIO_RCC_REG      (RCC->AHB1ENR)
  #define ETH_DEVICE_NAME       "STM32F429"
```

MAC ailesi (EQOS veya GMAC) zaten destekleniyorsa **başka hiçbir dosya değişmez.**

**Yeni MAC ailesi:** `eth_port.h`'deki 21 fonksiyonu yeni bir `.c` dosyasında implemente edin, tamamını `#if ETH_PORT_XXX ... #endif` içine alın.

**Yeni PHY:** `eth_phy.h`'deki 4 fonksiyonu (`Bringup`, `GetSpeedDuplex`, `SetLoopback`, `GetName`) yeni bir dosyada implemente edin. PHY, MAC ailesinden bağımsız bir eksendir.

## E-AETIS Protokolü (UDP)

`ethernet_test_gui.py` ile konuşulan UDP sözleşmesi (varsayılan port `ETH_EAETIS_PORT` = 5000):

| İstek | Yanıt |
|---|---|
| `DISCOVER_STM32_REQ` (broadcast) | `STM32_ACK\|DEV:...\|PHY:...` |
| `GET_PHY_DMA_STATS` | `PHY_STATS\|BCR:..\|BSR:..\|LINK:..\|SPEED:..\|DUPLEX:..\|DMA_RX_ERR:..\|DMA_TX_ERR:..` |
| `PERF_TEST_...` | aynı payload (echo) |
| `START_IAP\|SIZE:n\|CRC:0x..` | `IAP_READY` |
| `FW_DATA\|SEQ:i\|LEN:n\|<binary>` | `ACK:i` |
| `END_IAP` | `FLASH_SUCCESS\|JUMP_OK` |
| `GET_VARS` | `ETH_BSP_RegisterVar()` ile kayıtlı değişkenlerin listesi (otomatik keşif) |
| `TELEMETRY_SUB\|PORT:n` | Karttan push telemetri aboneliği başlatır (`ETH_BSP_SendTelemetry()`) |
| Tanınmayan komut | `ETH_BSP_RegisterCommandHandler()` ile kaydedilen kullanıcı handler'ına yönlendirilir |

ICMP echo (ping) ve ARP otomatik yanıtlanır.

**Fault injection notu:** 2048 baytlık test paketi IP katmanında parçalanır. BSP fragment reassembly yapmaz; bu paketler sessizce düşürülür ve GUI'nin timeout alması **beklenen doğru davranıştır.**

## E-AETIS GUI Aracı

`ethernet_test_gui.py`, PyQt5 tabanlı masaüstü test arayüzüdür.

**Gereksinimler:** Python 3, `PyQt5`

```bash
pip install PyQt5
python ethernet_test_gui.py
```

Varsayılan hedef `192.168.1.50:5000` — kartın IP'si `eth_config.h` ile eşleşmelidir. Arayüz `DISCOVER_STM32_REQ` broadcast'i ile kartı otomatik keşfedebilir, `GET_VARS` ile kayıtlı telemetri değişkenlerini otomatik listeler.

## Karta Yüklemeden Önce Doğrulama Listesi

Register bit konumları ilgili referans kılavuzundan (RM) **doğrulanmalıdır.** Öncelik sırası:

1. `eth_port_eqos.c` → `MACMDIOAR` alan yerleşimi (PA/RDA/CR/MOC/MB)
2. `eth_port_eqos.c` → `SBS->PMCR` `ETH_SEL_PHY` için RMII değer kodu
3. `eth_port_eqos.c` → `DMACRXDTPR` tail pointer semantiği
4. `eth_driver.c` → ARMv8-M MPU `RBAR`/`RLAR` alan yerleşimi
5. `eth_iap.c` → `FLASH_NSCR` sektör numarası alanı ve yazma birimi
6. `eth_config.h` → RMII pin haritası (kart şemasından)

**İlk test:** `ETH_PHY_ScanAddress()` çağırıp PHY ID okuyabildiğinizi doğrulayın. Bu çalışıyorsa RMII saati, GPIO AF ayarları, clock enable ve SMI zamanlaması — hepsi doğrudur. Geri kalan her şey bunun üzerine kurulur.

## Bilinen Sınırlar

- IP fragment reassembly yok (tasarım kararı)
- TCP yok — yalnızca UDP/ICMP/ARP
- Tek DMA kanalı, tek kuyruk (QoS/VLAN önceliklendirme yok)
- IAP'de kimlik doğrulama yok, yalnızca CRC32 bütünlük kontrolü
- Polling tabanlı; kesme desteği yok (`ProcessEvents` çağrı sıklığına bağımlı)


