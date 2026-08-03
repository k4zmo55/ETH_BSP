# Ethernet_BSP — E-AETIS

Bare-metal STM32 Ethernet Board Support Package. RTOS yok, LwIP yok.
Yalnızca CMSIS register erişimi ve DMA descriptor ring yönetimi.

---

## Entegrasyon (3 adım)

**1.** `Ethernet_BSP/` klasörünü projeye kopyalayın. `Src/` altındaki **tüm**
`.c` dosyalarını build path'e ekleyin — seçilmeyen port ve PHY dosyaları
boş derlenir, elle çıkarmanıza gerek yoktur. `Inc/` klasörünü include
path'e tanıtın.

**2.** Yalnızca `Inc/eth_config.h` dosyasını düzenleyin: hedef MCU, PHY
çipi, IP/MAC, RMII pin haritası, PHY adresi.

**3.** `main.c` içinde tek bir başlık:

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

Ek olarak linker script'e `.eth_desc` section'ı eklenmelidir
(bkz. `Docs/linker_snippet.ld`).

---

## Mimari

Üç **bağımsız** eksen vardır. Birinde yapılan değişiklik diğerlerini etkilemez.

```
eth_config.h            Kullanıcının dokunduğu tek dosya
    │
eth_device.h            MCU → MAC ailesi + yetenek eşlemesi
    │
    ├── eth_port.h      Port sözleşmesi (20 fonksiyon)
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

### Yeni MCU eklemek

`eth_device.h` içine bir blok:

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

MAC ailesi zaten destekleniyorsa **başka hiçbir dosya değişmez.**

### Yeni MAC ailesi eklemek

`eth_port.h`'deki fonksiyonları yeni bir `.c` dosyasında implemente edin,
tamamını `#if ETH_PORT_XXX ... #endif` içine alın.

---

## E-AETIS protokolü

`ethernet_test_gui.py` ile konuşulan UDP sözleşmesi (varsayılan port 5000):

| İstek | Yanıt |
|---|---|
| `DISCOVER_STM32_REQ` (broadcast) | `STM32_ACK\|DEV:...\|PHY:...` |
| `GET_PHY_DMA_STATS` | `PHY_STATS\|BCR:..\|BSR:..\|LINK:..\|SPEED:..\|DUPLEX:..\|DMA_RX_ERR:..\|DMA_TX_ERR:..` |
| `PERF_TEST_...` | aynı payload (echo) |
| `START_IAP\|SIZE:n\|CRC:0x..` | `IAP_READY` |
| `FW_DATA\|SEQ:i\|LEN:n\|<binary>` | `ACK:i` |
| `END_IAP` | `FLASH_SUCCESS\|JUMP_OK` |

ICMP echo (ping) ve ARP otomatik yanıtlanır.

**Fault injection notu:** 2048 baytlık test paketi IP katmanında parçalanır.
BSP fragment reassembly yapmaz; bu paketler sessizce düşürülür ve GUI'nin
timeout alması **beklenen doğru davranıştır.**

---

## Doğrulama listesi — karta yüklemeden önce

Register bit konumları RM'den **doğrulanmalıdır.** Öncelik sırası:

1. `eth_port_eqos.c` → `MACMDIOAR` alan yerleşimi (PA/RDA/CR/MOC/MB)
2. `eth_port_eqos.c` → `SBS->PMCR` `ETH_SEL_PHY` için RMII değer kodu
3. `eth_port_eqos.c` → `DMACRXDTPR` tail pointer semantiği
4. `eth_driver.c` → ARMv8-M MPU `RBAR`/`RLAR` alan yerleşimi
5. `eth_iap.c` → `FLASH_NSCR` sektör numarası alanı ve yazma birimi
6. `eth_config.h` → RMII pin haritası (kart şemasından)

**İlk test:** `ETH_PHY_ScanAddress()` çağırıp PHY ID okuyabildiğinizi
doğrulayın. Bu çalışıyorsa RMII saati, GPIO AF ayarları, clock enable ve
SMI zamanlaması — hepsi doğrudur. Geri kalan her şey bunun üzerine kurulur.

---

## Bilinen sınırlar

- IP fragment reassembly yok (tasarım kararı)
- TCP yok — yalnızca UDP/ICMP/ARP
- Tek DMA kanalı, tek kuyruk (QoS/VLAN önceliklendirme yok)
- IAP'de kimlik doğrulama yok, yalnızca CRC32 bütünlük kontrolü
- Polling tabanlı; kesme desteği yok (`ProcessEvents` çağrı sıklığına bağımlı)
# ETH_BSP
