# Referans Kılavuzları

Bu dosya, Ethernet_BSP kodunun dayandığı **resmi üretici dokümanlarını** listeler. Bunlar depoya dahil edilmemiştir (büyük binary PDF'ler, telif hakkına tabidir, ve üreticiler sürüm güncellemesi yaptığında depo içindeki kopya bayatlar) — bunun yerine, her donanım için hangi belgeye bakmanız gerektiği ve kod içindeki hangi dosya/fonksiyonun o belgenin hangi bölümüne karşılık geldiği burada eşlenir.

**Neden PDF'ler depoda değil?** `git clone` boyutunu şişirmemek ve her zaman üreticinin sitesindeki **güncel revizyona** yönlendirmek için. Bir kayıt (register) alan yerleşimini doğrularken her zaman en son revizyonu indirin — silikon revizyonları arasında register bit tanımları değişebilir.

## 1) MCU Referans Kılavuzları (Reference Manual)

| Hedef (`ETH_TARGET_*`) | Belge | Üretici / Kaynak |
|---|---|---|
| `ETH_TARGET_STM32H563` | **RM0481** — STM32H563/H573 Reference Manual | st.com → Ürün sayfası (STM32H563ZI) → "Technical documentation" → Reference manuals |
| `ETH_TARGET_STM32H743` | **RM0433** — STM32H742/743/750/753 Reference Manual | st.com → Ürün sayfası (STM32H743) → Reference manuals |
| `ETH_TARGET_STM32F407` | **RM0090** — STM32F405/415, STM32F407/417, STM32F427/437, STM32F429/439 Reference Manual | st.com → Ürün sayfası (STM32F407) → Reference manuals |
| `ETH_TARGET_STM32F767` | **RM0410** — STM32F76xxx/F77xxx Reference Manual | st.com → Ürün sayfası (STM32F767) → Reference manuals |

Her belgede aranacak bölüm başlığı MCU ailesine göre değişir:

- **H563 / H743 (EQOS ailesi):** "Ethernet (ETH): media access control (MAC)" bölümü. Bu bölüm Synopsys DesignWare Core EQOS IP'sinin ST tarafından uyarlanmış registerlarını listeler (`MACMDIOAR`, `DMACRXDTPR`, `DMACTXDTPR`, `MTLTXQ0OMR` vb.).
- **F407 / F767 (klasik GMAC ailesi):** "Ethernet (ETHERNET)" bölümü — register isimleri `ETH_MACMIIAR`, `ETH_DMARDLAR`, `ETH_DMATDLAR`, `ETH_DMARPDR` şeklindedir (EQOS'tan farklı isimlendirme).

### Kod → Belge eşlemesi (doğrulama sırası)

Bu proje register yerleşimlerini CMSIS başlıklarından (`stm32h5xx.h` vb.) alır; kendi kartınıza taşırken aşağıdaki noktaları ilgili RM ile **çapraz doğrulayın**:

| Dosya / Fonksiyon | RM'de aranacak bölüm |
|---|---|
| `Src/port/eth_port_eqos.c` → `ETH_Port_SMI_Read/Write` | `MACMDIOAR` register alanları: PA (PHY Address), RDA (Register Address), CR (Clock Range), MOC (Operation Command), MB (MDIO Busy) |
| `Src/port/eth_port_eqos.c` → `ETH_Port_ConfigureMDCClock` | `MACMDIOAR.CR` alanının HCLK aralığına göre değer tablosu ("MDC clock" alt bölümü) |
| `Src/port/eth_port_eqos.c` → RMII seçimi | İlgili MCU'nun `SBS->PMCR` (H5) veya `SYSCFG->PMCR` (H7) — "Ethernet PHY interface selection" alt bölümü |
| `Src/port/eth_port_eqos.c` → `ETH_Port_KickRx/KickTx` | `DMACRXDTPR` / `DMACTXDTPR` "tail pointer" semantiği — "DMA descriptors" bölümü |
| `Src/port/eth_port_gmac.c` → tüm fonksiyonlar | `ETH_MACMIIAR`, `ETH_DMARDLAR/TDLAR`, `ETH_DMARPDR` — "Ethernet (ETHERNET)" bölümü, register haritası |
| `Src/eth_driver.c` → MPU non-cacheable ayarı | İlgili MCU'nun "Memory protection unit (MPU)" bölümü — `MPU->RASR` (Cortex-M7, ARMv7-M) veya `MPU->RBAR/RLAR` + `MAIR0/1` (Cortex-M33, ARMv8-M) |
| `Src/eth_iap.c` → flash silme/yazma | İlgili MCU'nun "Embedded Flash memory (FLASH)" bölümü — sektör/sayfa boyutu, `FLASH_NSCR`/`FLASH_CR` sektör numarası alanı, yazma birimi (H5: quad-word/16B, F4/F7: word/byte) |

**Genel amaçlı Cortex-M mimarisi belgeleri** (üretici bağımsız, ARM tarafından yayınlanır):
- Cortex-M33: *Armv8-M Architecture Reference Manual* + *Cortex-M33 Devices Generic User Guide* (MPU `RBAR`/`RLAR`/`MAIR` alanları için)
- Cortex-M7 / M4: *Armv7-M Architecture Reference Manual* (MPU `RBAR`/`RASR` alanları için)

## 2) PHY Datasheet'leri

| Hedef (`ETH_PHY_*`) | Çip | Üretici / Kaynak |
|---|---|---|
| `ETH_PHY_LAN8720A` | LAN8720A | Microchip — ürün sayfası "LAN8720A" → Documents → Datasheet |
| `ETH_PHY_LAN8742A` | LAN8742A | Microchip — ürün sayfası "LAN8742A" → Documents → Datasheet |
| `ETH_PHY_KSZ8081`  | KSZ8081  | Microchip (eski Micrel) — ürün sayfası "KSZ8081" → Documents → Datasheet |

### Kod → Belge eşlemesi

| Dosya / Fonksiyon | Datasheet'te aranacak |
|---|---|
| `Src/phy/eth_phy_lan87xx.c` → `ETH_PHY_GetSpeedDuplex` | Register `0x1F` — "Special Control/Status Register (SCSR)", `SPEED`/`DUPLEX` alanları |
| `Src/phy/eth_phy_ksz80xx.c` → `ETH_PHY_GetSpeedDuplex` | Register `0x1E` — "PHY Control 1 Register (PC1R)", `OPERATION MODE` alanı |
| `Inc/eth_phy.h` / her iki dosya → `PHY_REG_BMSR` (`0x01`) | IEEE 802.3 standart MII registerları — "Basic Mode Status Register", bit 2 = Link Status (latching-low) |
| `Inc/eth_config.h` → `PHY_ADDRESS`, reset pin süresi | Datasheet'in "Reset" / "Strap Options" bölümü — donanımsal reset için minimum darbe genişliği ve strap pin yapılandırması |

Her iki ailede de (`LAN87xx`, `KSZ80xx`) IEEE 802.3 standart registerları (`0x00`–`0x0F`: `BMCR`, `BMSR`, `PHYID1`, `PHYID2`, ...) ortaktır; sadece vendor-specific registerlar (`0x10` ve üzeri) çipe özeldir.

## 3) Ek Kavramsal Kaynaklar

Kodun dayandığı protokol/algoritma kavramlarını tazelemek için:

- **IEEE 802.3** — Ethernet II çerçeve formatı, CRC32 (FCS) polinomu (`0xEDB88320` — `Src/eth_iap.c` ve `Src/eth_app.c` içindeki CRC32 implementasyonuyla aynı)
- **RFC 826** — Address Resolution Protocol (ARP) — `Src/eth_app.c` içindeki ARP önbellek/yanıt mantığı
- **RFC 792** — Internet Control Message Protocol (ICMP) — ping/echo işleyicisi
- **RFC 768** — User Datagram Protocol (UDP) — E-AETIS komut protokolünün taşıyıcısı
- **RFC 791** — Internet Protocol (IPv4) — `Src/eth_app.c` başlık ayrıştırma; bu BSP fragment reassembly YAPMAZ (bkz. README "Bilinen Sınırlar"), bu yüzden `MF` biti veya `fragment offset != 0` olan paketler kasıtlı olarak düşürülür

## 4) Doğrulama Önceliği (Özet)

Yeni bir karta taşırken, referans kılavuzlarını şu sırayla açın (bkz. README → "Karta Yüklemeden Önce Doğrulama Listesi" için gerekçeler):

1. MCU RM → `MACMDIOAR` (veya `ETH_MACMIIAR`) alan yerleşimi
2. MCU RM → RMII seçim register'ı (`SBS->PMCR` / `SYSCFG->PMCR`) değer kodu
3. MCU RM → DMA tail-pointer / next-pointer semantiği
4. Cortex-M mimari kılavuzu → MPU register alan yerleşimi
5. MCU RM → Flash controller sektör numarası alanı ve yazma birimi (yalnızca `ETH_ENABLE_IAP=1` ise)
6. PHY datasheet → vendor-specific speed/duplex register'ı
7. Kart şeması → RMII pin haritası (`eth_config.h`)
