# Staj Defteri – Gün Gün Kod Özetleri (30 Temmuz itibariyle)

Her gün için staj defterindeki anlatıma karşılık gelen, projeden alınmış kısa kod parçaları.

---

## 30 Temmuz 2026 – Gün 9
Klasör iskeleti + `eth_config.h` (8 grup) ve `eth_device.h` (derleme zamanı kontrolleri).

```c
// Inc/eth_config.h
#define ETH_TARGET_STM32H563
#define ETH_PHY_LAN8720A
#define ETH_RX_DESC_COUNT   8U   /* 2'nin kuvveti olmali */
#define ETH_BUFFER_SIZE     1536U
#define ETH_DESC_REGION_BASE 0x20000000UL
#define ETH_DESC_REGION_SIZE (32U * 1024U)
```

```c
// Inc/eth_device.h
#if ETH_TGT_N_ == 0
  #error "eth_config.h icinde bir ETH_TARGET_* secilmedi."
#endif
#if (ETH_RX_DESC_COUNT & (ETH_RX_DESC_COUNT - 1U)) != 0U
  #error "ETH_RX_DESC_COUNT 2'nin kuvveti olmali."
#endif
#if (ETH_DESC_REGION_BASE >= 0x20000000UL) && (ETH_DESC_REGION_BASE < 0x24000000UL)
  #error "H7'de descriptor bolgesi DTCM'de olamaz. D2 SRAM kullanin (0x30000000)."
#endif
```

---

## 31 Temmuz 2026 – Gün 10
Üç sözleşme başlığı: `eth_driver.h`, `eth_port.h` (21 fonksiyon), `eth_phy.h` (4 fonksiyon).

```c
// Inc/eth_driver.h
typedef struct __attribute__((aligned(32))) {
    volatile uint32_t DES0, DES1, DES2, DES3;
} ETH_Desc_t;

typedef enum {
    ETH_OK = 0, ETH_ERR_TIMEOUT = -2, ETH_ERR_PHY = -3, ETH_ERR_LINK_DOWN = -4
} ETH_Status_t;
```

```c
// Inc/eth_port.h  (port sozlesmesinden ornekler)
void ETH_Port_SetupRings(ETH_Desc_t *rx, uint32_t rx_count,
                         ETH_Desc_t *tx, uint32_t tx_count);
void ETH_Port_KickRx(uint32_t next_index);
void ETH_Port_KickTx(uint32_t next_index);
```

```c
// Inc/eth_phy.h
ETH_Status_t ETH_PHY_Bringup(uint8_t addr);
ETH_Status_t ETH_PHY_GetSpeedDuplex(uint8_t addr, uint16_t *speed, bool *fd);
#define PHY_REG_BMSR  0x01U
#define PHY_BMSR_LINK_UP (1U << 2)
```

---

## 10 Ağustos 2026 – Gün 11
`eth_driver.c`: MPU non-cacheable bölge (M33/M7 ayrımı), RMII GPIO AF, `ETH_Driver_Init` sırası, `ETH_PHY_ScanAddress`, link durumu (latching-low okuma).

```c
// Src/eth_driver.c
#if (__ARM_ARCH_8M_MAIN__ == 1) || defined(ETH_TARGET_STM32H563)
    MPU->MAIR0 = (MPU->MAIR0 & ~0xFFUL) | 0x44UL;   /* Cortex-M33: Non-cacheable */
#else
    MPU->RASR = (1UL<<28)|(3UL<<24)|(1UL<<19)|(size_code<<1)|(1UL<<0); /* Cortex-M7 */
#endif
```

```c
ETH_Status_t ETH_PHY_ScanAddress(uint8_t *found_addr)
{
    for (uint8_t a = 0U; a < 32U; a++) {
        uint16_t id1 = 0U;
        if (ETH_Port_SMI_Read(a, PHY_REG_PHYID1, &id1) != ETH_OK) continue;
        if (id1 != 0x0000U && id1 != 0xFFFFU) { *found_addr = a; return ETH_OK; }
    }
    return ETH_ERR_PHY;
}
```

```c
/* BMSR link biti "latching low": dusen linki yakalamak icin iki kez okunur. */
(void)ETH_Port_SMI_Read(PHY_ADDRESS, PHY_REG_BMSR, &bmsr);
if (ETH_Port_SMI_Read(PHY_ADDRESS, PHY_REG_BMSR, &bmsr) != ETH_OK) return ETH_ERR_PHY;
```

---

## 11 Ağustos 2026 – Gün 12
Ring init, `ETH_SendFrame` (60 bayta padding), zero-copy `Claim/Commit` ve `Receive/Release`, istatistik biriktirme.

```c
// Src/eth_driver.c
ETH_Status_t ETH_CommitTxBuffer(uint16_t len)
{
    uint16_t tx_len = len;
    if (tx_len < 60U) {                      /* min Ethernet frame */
        memset(&tx_buf[tx_idx][tx_len], 0, 60U - tx_len);
        tx_len = 60U;
    }
    ETH_Port_DescArmTx(&tx_desc[tx_idx], &tx_buf[tx_idx][0], tx_len);
    tx_idx = (tx_idx + 1U) & TX_MASK;
    ETH_Port_KickTx(tx_idx);
    return ETH_OK;
}
```

```c
ETH_Status_t ETH_ReceiveFrame(uint8_t **data, uint16_t *len)
{
    ETH_Desc_t *d = &rx_desc[rx_idx];
    if (!ETH_Port_DescIsOwnedByCPU(d)) return ETH_ERR_NO_DATA;
    if (ETH_Port_DescRxHasError(d)) { stats.rx_crc_errors++; /* re-arm & kick */ return ETH_ERR_NO_DATA; }

    uint16_t flen = ETH_Port_DescGetRxLength(d);
    if (flen < 14U || flen > ETH_BUFFER_SIZE) { stats.rx_dropped++; return ETH_ERR_NO_DATA; }

    *data = &rx_buf[rx_idx][0]; *len = flen; rx_held = true;
    return ETH_OK;
}
```

```c
void ETH_GetStats(ETH_Stats_t *s)
{
    stats.rx_missed_hw += ETH_Port_GetMissedFrames();  /* okununca temizlenir */
    stats.dma_errors   += ETH_Port_GetAndClearDMAErrors();
    *s = stats;
}
```

---

## 12 Ağustos 2026 – Gün 13
`eth_port_eqos.c`: register sabitleri, RMII seçimi (SBS/SYSCFG), MDC bölücü, taban+uzunluk+tail-pointer ring, `__DMB()` bariyeri.

```c
// Src/port/eth_port_eqos.c
#if defined(ETH_RMII_VIA_SBS)
    SBS->PMCR = (SBS->PMCR & ~SBS_PMCR_ETH_SEL_PHY_Msk) | (4UL << SBS_PMCR_ETH_SEL_PHY_Pos);
#elif defined(ETH_RMII_VIA_SYSCFG_PMCR)
    SYSCFG->PMCR = (SYSCFG->PMCR & ~SYSCFG_PMCR_EPIS_SEL_Msk) | (4UL << SYSCFG_PMCR_EPIS_SEL_Pos);
#endif
```

```c
void ETH_Port_ConfigureMDCClock(uint32_t hclk_hz)
{
    if      (hclk_hz <  35000000UL) mdio_cr_value = 2UL;  /* HCLK/16  */
    else if (hclk_hz < 250000000UL) mdio_cr_value = 4UL;  /* HCLK/102 */
    else                            mdio_cr_value = 5UL;  /* HCLK/124: MDC <= 2.5MHz */
}
```

```c
void ETH_Port_KickRx(uint32_t next_index)
{
    /* Tail pointer "buraya kadar isle" demek; bu yuzden serbest biraktigimiz
     * descriptor'in BIR ONCESINI gosteriyoruz. */
    uint32_t prev = (next_index + rx_ring_count - 1U) % rx_ring_count;
    ETH->DMACRXDTPR = (uint32_t)(uintptr_t)&rx_ring_base[prev];
}

void ETH_Port_DescArmTx(ETH_Desc_t *d, uint8_t *buf, uint16_t len)
{
    d->DES0 = (uint32_t)(uintptr_t)buf; d->DES2 = EQOS_TDES2_IOC | len;
    __DMB();                                   /* OWN bitini EN SON yaz */
    d->DES3 = EQOS_DESC_OWN | EQOS_TDES3_FD | EQOS_TDES3_LD | len;
    __DMB();
}
```

---

## 13 Ağustos 2026 – Gün 14
`eth_port_gmac.c`: next-pointer zincir (TCH), poll-demand "kick", RX uzunluğundan 4 bayt CRC çıkarma.

```c
// Src/port/eth_port_gmac.c
void ETH_Port_SetupRings(ETH_Desc_t *rx, uint32_t rx_count, ETH_Desc_t *tx, uint32_t tx_count)
{
    for (uint32_t i = 0U; i < rx_count; i++) {
        rx[i].DES1 = GMAC_RDES1_RCH | ETH_BUFFER_SIZE;
        rx[i].DES3 = (uint32_t)(uintptr_t)&rx[(i + 1U) % rx_count];   /* next-pointer */
    }
}
```

```c
void ETH_Port_KickRx(uint32_t next_index)
{
    (void)next_index;
    if (ETH->DMASR & GMAC_DMASR_RBUS) {         /* tail pointer yok: poll demand */
        ETH->DMASR   = GMAC_DMASR_RBUS;
        ETH->DMARPDR = 0U;
    }
}

uint16_t ETH_Port_DescGetRxLength(const ETH_Desc_t *d)
{
    uint16_t fl = (uint16_t)((d->DES0 >> GMAC_RDES0_FL_Pos) & GMAC_RDES0_FL_MASK);
    return (fl > 4U) ? (uint16_t)(fl - 4U) : 0U;   /* legacy MAC uzunluga CRC'yi dahil eder */
}
```

---

## 14 Ağustos 2026 – Gün 15
PHY sürücüleri: ortak bringup adımları, hız/duplex için farklı vendor register'ı (LAN87xx `0x1F` vs KSZ8081 `0x1E`).

```c
// Src/phy/eth_phy_lan87xx.c
#define LAN87XX_REG_SCSR  0x1FU
ETH_Status_t ETH_PHY_GetSpeedDuplex(uint8_t addr, uint16_t *speed, bool *fd)
{
    uint16_t scsr; ETH_PHY_Read(addr, LAN87XX_REG_SCSR, &scsr);
    switch (scsr & LAN87XX_SCSR_MODE_Msk) {
        case LAN87XX_SCSR_100FD: *speed = 100U; *fd = true; break;
        /* ... */
    }
    return ETH_OK;
}
```

```c
// Src/phy/eth_phy_ksz80xx.c
#define KSZ8081_REG_PHYCTRL1  0x1EU
ETH_Status_t ETH_PHY_GetSpeedDuplex(uint8_t addr, uint16_t *speed, bool *fd)
{
    uint16_t ctrl; ETH_PHY_Read(addr, KSZ8081_REG_PHYCTRL1, &ctrl);
    switch (ctrl & KSZ8081_OPMODE_Msk) {
        case KSZ8081_OPMODE_100FD: *speed = 100U; *fd = true; break;
        /* ... */
    }
    return ETH_OK;
}
```

```c
/* Her ikisinde ortak bringup: PHYID gecerlilik kontrolu */
if (ETH_PHY_Read(addr, PHY_REG_PHYID1, &reg) != ETH_OK) return ETH_ERR_PHY;
if (reg == 0x0000U || reg == 0xFFFFU) return ETH_ERR_PHY;   /* bos SMI hatti */
```

---

## 17 Ağustos 2026 – Gün 16
`eth_app.h`: `ETH_Var_t`, `ETH_BSP_RegisterVar`, push/pull telemetri, kullanıcı komut genişletmesi.

```c
// Inc/eth_app.h
typedef struct {
    const char   *name;
    ETH_VarType_t type;
    bool          writable;
    void         *ptr;          /* NULL ise getter/setter kullanilir */
    float       (*getter)(void);
    void        (*setter)(float value);
} ETH_Var_t;

ETH_Status_t ETH_BSP_RegisterVar(const ETH_Var_t *var);
ETH_Status_t ETH_BSP_SendTelemetry(const char *text);   /* push */
void ETH_BSP_RegisterCommandHandler(ETH_UserCmdHandler_t handler);
```

---

## 18 Ağustos 2026 – Gün 17
`eth_app.c`: ARP önbelleği (LRU), `icmp_handle`, `udp_send_to_mac`, IPv4 parçalanmış paketleri düşürme.

```c
// Src/eth_app.c
static void arp_cache_put(const uint8_t ip[4], const uint8_t mac[6])
{
    /* eslesme varsa guncelle, yoksa en eski (en dusuk last_seen) girdiyi degistir */
    for (uint32_t i = 0U; i < ETH_ARP_CACHE_SIZE; i++) {
        if (arp_cache[i].valid && memcmp(arp_cache[i].ip, ip, 4) == 0) {
            memcpy(arp_cache[i].mac, mac, 6); arp_cache[i].last_seen = ETH_GetTick();
            return;
        }
    }
    /* ... oldest_idx secilip uzerine yazilir ... */
}
```

```c
static ETH_Status_t udp_send_to_mac(const uint8_t dst_mac[6], const uint8_t dst_ip[4],
                                    uint16_t dst_port, uint16_t src_port,
                                    const void *data, uint16_t len)
{
    /* ETH_BSP_SendUDP ve ETH_BSP_ReplyUDP'nin ortak alt yapisi */
    uint8_t *buf; ETH_ClaimTxBuffer(&buf);
    uint16_t o = build_eth_header(buf, dst_mac, ETHERTYPE_IPV4);
    o += build_ip_header(&buf[o], dst_ip, IP_PROTO_UDP, UDP_HDR_LEN + len);
    /* UDP basligi + veri yazilir */
    return ETH_CommitTxBuffer(o + UDP_HDR_LEN + len);
}
```

```c
/* BSP fragment reassembly yapmiyor: MF biti veya offset != 0 -> sessizce dustur */
uint16_t frag = rd16(&ip[6]);
if ((frag & IP_FLAG_MF) || (frag & IP_FRAG_OFF_MASK)) return;
```

---

## 19 Ağustos 2026 – Gün 18
`eaetis_handle` komut dağıtımı, kendi sınırlı `parse_uint/float/str` fonksiyonları, `START_IAP/FW_DATA/END_IAP`, `eth_iap.h`/`eth_iap.c` iskeleti.

```c
// Src/eth_app.c
static bool eaetis_parse_uint(const uint8_t *d, uint16_t len, const char *key,
                              int base, uint32_t *out)
{
    /* "ANAHTAR:" sonrasindaki sayiyi tampon sinirini asmadan okur (strtof yok) */
    for (uint16_t i = 0U; (uint16_t)(i + klen) <= len; i++) {
        if (memcmp(&d[i], key, klen) != 0) continue;
        /* hex/decimal ayristirma, tasma kontrolu ile */
    }
    return false;
}
```

```c
if (len >= 18U && memcmp(data, "DISCOVER_STM32_REQ", 18) == 0) {
    char out[64];
    int n = snprintf(out, sizeof(out), "STM32_ACK|DEV:%s|PHY:%s",
                     ETH_DEVICE_NAME, ETH_PHY_GetName());
    if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
    return true;
}
```

```c
/* --- IAP: FW_DATA|SEQ:i|LEN:n|<binary> ---
 * Basligi metin, binary kismi bayt bayt isleriz; strlen/strcmp KULLANILMAZ
 * (veri icinde rastgele '\0' gelebilir). */
for (i = 0U; i < len && bars < 3U; i++) {
    if (data[i] == '|') { bars++; /* SEQ:/LEN: alanlarini sayisal olarak coz */ }
}
if (ETH_IAP_WriteChunk(seq, &data[i], (uint16_t)dlen) == ETH_OK) { /* ACK */ }
```

```c
// Inc/eth_iap.h  (18. gundeki sozlesme iskeleti - flash mantigi henuz TODO)
ETH_Status_t ETH_IAP_Begin(uint32_t total_size, uint32_t expected_crc32);
ETH_Status_t ETH_IAP_WriteChunk(uint32_t seq, const uint8_t *data, uint16_t len);
ETH_Status_t ETH_IAP_Finish(void);
void         ETH_IAP_JumpToApplication(void);
```

---

## 20 Ağustos 2026 – Gün 19
`Docs/linker_snippet.ld`: `.eth_desc` section'ının non-cacheable RAM_DESC bölgesine yerleşimi.

```ld
/* Docs/linker_snippet.ld - STM32H563 ornegi */
MEMORY
{
  RAM_DESC (rw) : ORIGIN = 0x20000000, LENGTH = 32K   /* ETH bolgesi */
}

.eth_desc (NOLOAD) :
{
  . = ALIGN(32);
  *(.eth_desc)
  . = ALIGN(32);
} >RAM_DESC
```

---

## 21 Ağustos 2026 – Gün 20
`Examples/main.c`: üç telemetri değişkeni tipi (ptr sensör, ptr I2C, getter/setter LED) ve bloklamayan ana döngü.

```c
// Examples/main.c
static const ETH_Var_t var_temp = {
    .name = "sicaklik", .unit = "C", .type = ETH_VAR_F32,
    .writable = false, .ptr = &g_temperature_c
};
static const ETH_Var_t var_led = {
    .name = "led", .type = ETH_VAR_U8, .writable = true,
    .ptr = NULL, .getter = led_get, .setter = led_set
};
```

```c
while (1) {
    (void)ETH_BSP_ProcessEvents();          /* bloklamaz */

    uint32_t now = HAL_GetTick();
    if ((now - last_sample) >= 100U) {      /* ayri 100ms zamanlama */
        last_sample = now;
        g_temperature_c = ReadTemperatureSensor();
        g_humidity_rh   = ReadI2CHumiditySensor();
    }
}
```

---

## 24 Ağustos 2026 – Gün 21
`ethernet_test_gui.py`: tüm soketlerin geçtiği `Protocol` sınıfı — `request()`, `fire()`, `discover()`.

```python
# ethernet_test_gui.py
class Protocol:
    def request(self, payload, expect_reply=True, timeout=None, ip=None):
        s = self._sock(timeout=timeout)
        s.sendto(payload, (ip or self.ip, self.port))
        data, _ = s.recvfrom(4096)
        return data, (time.perf_counter() - t0) * 1000.0   # (yanit, gecikme_ms)

    def fire(self, payload, ip=None):
        """Yanit beklemeden gonder (fuzzing icin)."""
        s = self._sock()
        s.sendto(payload, (ip or self.ip, self.port))

    def discover(self, timeout=2.0):
        s = self._sock(broadcast=True, timeout=timeout)
        s.sendto(b"DISCOVER_STM32_REQ", ("255.255.255.255", self.port))
        # STM32_ACK yanitlarini sure dolana kadar toplar
```

---

## 25 Ağustos 2026 – Gün 22
`PingWorker` (echo tabanlı gecikme) ve `BenchmarkWorker` (min/ort/p95/max/jitter + donanım sayaçlarıyla karşılaştırma).

```python
class BenchmarkWorker(QThread):
    def run(self):
        self.proto.reset_stats()
        for i in range(self.count):
            data, ms = self.proto.request(payload, timeout=0.5)
            if data is None: lost += 1
            else: lat.append(ms)

        mean = sum(lat) / len(lat)
        var  = sum((x - mean) ** 2 for x in lat) / len(lat)
        summary = {
            "min_ms": lat_sorted[0], "max_ms": lat_sorted[-1], "avg_ms": mean,
            "jitter_ms": var ** 0.5,
            "p95_ms": lat_sorted[int(len(lat_sorted) * 0.95) - 1],
        }
        # yazilim kaybi ile donanimin RX_MISS sayaci ayri raporlanir
```

---

## 26 Ağustos 2026 – Gün 23
`FaultInjectionWorker` (3 senaryo) ve `FirmwareUpdateWorker` (512B parça + ACK döngüsü).

```python
class FaultInjectionWorker(QThread):
    def run(self):
        self.proto.fire(b"X" * 2048)              # [1] IP parcalanmasi
        for m in [b"START_IAP", b"FW_DATA|SEQ:9999|LEN:99999|", b"|" * 200]:
            self.proto.fire(m)                     # [2] kesik/tutarsiz basliklar
        for i in range(self.fuzz_count):
            self.proto.fire(bytes(random.getrandbits(8) for _ in range(size)))  # [3] fuzz
        # test sonunda GET_PHY_DMA_STATS ile canlilik kontrolu
```

```python
class FirmwareUpdateWorker(QThread):
    def run(self):
        crc = zlib.crc32(blob) & 0xFFFFFFFF
        self.proto.request("START_IAP|SIZE:%d|CRC:0x%08X" % (size, crc))
        for i in range(total):
            packet = ("FW_DATA|SEQ:%d|LEN:%d|" % (i, len(piece))).encode() + piece
            for attempt in range(3):              # en fazla 3 deneme
                resp, _ = self.proto.request(packet, timeout=2.0)
                if resp starts with "ACK:%d" % i: break
        self.proto.request("END_IAP", timeout=10.0)
```

---

## 3 Eylül 2026 – Gün 29
STM32H563 flash denetleyicisi: `flash_unlock`/`flash_wait_ready`/`flash_erase_sector`.

```c
// Src/eth_iap.c
static ETH_Status_t flash_unlock(void)
{
    if ((FLASH->NSCR & FLASH_NSCR_LOCK) == 0U) return ETH_OK;
    FLASH->NSKEYR = IAP_FLASH_KEY1;
    FLASH->NSKEYR = IAP_FLASH_KEY2;
    return ((FLASH->NSCR & FLASH_NSCR_LOCK) == 0U) ? ETH_OK : ETH_ERR_FLASH;
}

static ETH_Status_t flash_erase_sector(uint32_t sector)
{
    flash_wait_ready();
    FLASH->NSCR = (FLASH->NSCR & ~FLASH_NSCR_SNB_Msk)
                | (sector << FLASH_NSCR_SNB_Pos) | FLASH_NSCR_SER;
    FLASH->NSCR |= FLASH_NSCR_STRT;
    return flash_wait_ready();
}
```

---

## 4 Eylül 2026 – Gün 30
CRC32 (zlib ile aynı polinom), `ETH_IAP_Begin`/`ETH_IAP_WriteChunk` (16 baytlık quad-word tamponlama), eski hata bayrağının temizlenmesi düzeltmesi.

```c
static uint32_t crc32_update(uint32_t crc, const uint8_t *data, uint32_t len)
{
    crc = ~crc;
    for (uint32_t i = 0U; i < len; i++) {
        crc ^= data[i];
        for (uint32_t b = 0U; b < 8U; b++) {
            uint32_t mask = (uint32_t)(-(int32_t)(crc & 1U));
            crc = (crc >> 1) ^ (0xEDB88320UL & mask);   /* IEEE 802.3 polinomu */
        }
    }
    return ~crc;
}
```

```c
static ETH_Status_t flash_wait_ready(void)
{
    while (FLASH->NSSR & FLASH_NSSR_BSY) { /* timeout kontrolu */ }
    if (FLASH->NSSR & (FLASH_NSSR_WRPERR | FLASH_NSSR_PGSERR | FLASH_NSSR_STRBERR)) {
        /* onceki basarisiz denemeden kalan bayrak PGSERR'e sebep oluyordu -> temizle */
        FLASH->NSCCR |= (FLASH_NSCCR_CLR_WRPERR | FLASH_NSCCR_CLR_PGSERR
                       | FLASH_NSCCR_CLR_STRBERR | FLASH_NSCCR_CLR_EOP);
        return ETH_ERR_FLASH;
    }
    return ETH_OK;
}
```

---

## 7 Eylül 2026 – Gün 31
`ETH_IAP_JumpToApplication`: vektör tablosunu taşıma, kesmeleri kapatıp yeni uygulamaya atlama.

```c
void ETH_IAP_JumpToApplication(void)
{
    uint32_t app_msp          = *(volatile uint32_t *)ETH_IAP_APP_BASE_ADDR;
    uint32_t app_reset_vector = *(volatile uint32_t *)(ETH_IAP_APP_BASE_ADDR + 4U);

    ETH_Driver_DeInit();          /* atlamadan once DMA/kesme kapatilmali */
    __disable_irq();
    SysTick->CTRL = 0U;

    SCB->VTOR = ETH_IAP_APP_BASE_ADDR;
    __set_MSP(app_msp);

    ((void (*)(void))(uintptr_t)app_reset_vector)();
    while (1) { }                 /* buraya asla ulasilmamali */
}
```
