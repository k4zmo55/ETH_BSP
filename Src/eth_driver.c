/**
  ******************************************************************************
  * @file    eth_driver.c
  * @brief   Aileden bagimsiz surucu cekirdegi: ring, PHY, istatistik.
  *
  * Bu dosyada TEK BIR register erisimi yoktur. Donanima dokunan her sey
  * ETH_Port_* sozlesmesi uzerinden port dosyalarina delege edilir.
  ******************************************************************************
  */

#include "eth_driver.h"
#include "eth_port.h"
#include "eth_phy.h"
#include <string.h>

/* ===== Statik bellek =================================================== */

static ETH_Desc_t rx_desc[ETH_RX_DESC_COUNT]
    __attribute__((section(ETH_DESC_SECTION), aligned(32)));
static ETH_Desc_t tx_desc[ETH_TX_DESC_COUNT]
    __attribute__((section(ETH_DESC_SECTION), aligned(32)));

static uint8_t rx_buf[ETH_RX_DESC_COUNT][ETH_BUFFER_SIZE]
    __attribute__((section(ETH_DESC_SECTION), aligned(4)));
static uint8_t tx_buf[ETH_TX_DESC_COUNT][ETH_BUFFER_SIZE]
    __attribute__((section(ETH_DESC_SECTION), aligned(4)));

#define RX_MASK (ETH_RX_DESC_COUNT - 1U)
#define TX_MASK (ETH_TX_DESC_COUNT - 1U)

static volatile uint32_t rx_idx;
static volatile uint32_t tx_idx;
static bool        rx_held;        /* ReceiveFrame verildi, Release bekliyor */
static bool        tx_claimed;     /* ClaimTxBuffer verildi, Commit bekliyor */
static bool        driver_ready;
static ETH_Stats_t stats;

/* ===== Zaman tabani ==================================================== */

__attribute__((weak)) uint32_t ETH_GetTick(void)
{
    /* Varsayilan: HAL SysTick. HAL kullanmiyorsaniz kendi projenizde
     * bu fonksiyonu tekrar tanimlayin (weak, override edilebilir). */
    extern uint32_t HAL_GetTick(void);
    return HAL_GetTick();
}

/* ===== MPU: descriptor bolgesini non-cacheable yap ===================== */

#if ETH_HAS_DCACHE && ETH_USE_MPU_NONCACHEABLE

static void eth_mpu_config(void)
{
    __DMB();
    MPU->CTRL = 0U;

#if (__ARM_ARCH_8M_MAIN__ == 1) || (__ARM_ARCH_8M_BASE__ == 1) || defined(ETH_TARGET_STM32H563)
    /* --- ARMv8-M (Cortex-M33 / STM32H5) --- */
    /* MAIR attribute 0 = Normal, Outer/Inner Non-cacheable */
    MPU->MAIR0 = (MPU->MAIR0 & ~0xFFUL) | 0x44UL;

    MPU->RNR = ETH_MPU_REGION_NUMBER;
    /* RBAR: BASE | SH(inner shareable=0b01<<3) | AP(RW any priv=0b01<<1) | XN(1) */
    MPU->RBAR = (ETH_DESC_REGION_BASE & 0xFFFFFFE0UL)
              | (1UL << 3)      /* SH  = Outer shareable degil, non-shareable=0 */
              | (1UL << 1)      /* AP  = RW, priv+unpriv */
              | (1UL << 0);     /* XN  = execute never */
    /* RLAR: LIMIT | AttrIndx(0) | EN */
    MPU->RLAR = ((ETH_DESC_REGION_BASE + ETH_DESC_REGION_SIZE - 1UL) & 0xFFFFFFE0UL)
              | (0UL << 1)      /* AttrIndx = 0 */
              | (1UL << 0);     /* Enable */
#else
    /* --- ARMv7-M (Cortex-M7 / STM32H7, F7) --- */
    /* Boyut kodu: log2(size) - 1 */
    uint32_t size_code = 0U;
    uint32_t s = ETH_DESC_REGION_SIZE;
    while (s > 1U) { s >>= 1U; size_code++; }
    size_code -= 1U;

    MPU->RNR  = ETH_MPU_REGION_NUMBER;
    MPU->RBAR = ETH_DESC_REGION_BASE;
    MPU->RASR = (1UL << 28)             /* XN  */
              | (3UL << 24)             /* AP  = full access */
              | (1UL << 19)             /* TEX = 001 */
              | (0UL << 18)             /* S   = 0 */
              | (0UL << 17)             /* C   = 0 -> non-cacheable */
              | (0UL << 16)             /* B   = 0 */
              | (size_code << 1)
              | (1UL << 0);             /* Enable */
#endif

    MPU->CTRL = (1UL << 2) | (1UL << 0);   /* PRIVDEFENA | ENABLE */
    __DSB();
    __ISB();
}

#else
static void eth_mpu_config(void) { }
#endif

/* ===== GPIO: RMII pinleri ============================================== */

static void eth_gpio_init_af(GPIO_TypeDef *port, uint32_t pin)
{
    const uint32_t p2 = pin * 2U;

    port->MODER   = (port->MODER   & ~(3UL << p2)) | (2UL << p2);  /* AF     */
    port->OTYPER &= ~(1UL << pin);                                 /* PP     */
    port->OSPEEDR = (port->OSPEEDR & ~(3UL << p2)) | (3UL << p2);  /* V.High */
    port->PUPDR  &= ~(3UL << p2);                                  /* NoPull */

    if (pin < 8U) {
        port->AFR[0] = (port->AFR[0] & ~(0xFUL << (pin * 4U)))
                     | ((uint32_t)ETH_AF_NUMBER << (pin * 4U));
    } else {
        const uint32_t s = (pin - 8U) * 4U;
        port->AFR[1] = (port->AFR[1] & ~(0xFUL << s))
                     | ((uint32_t)ETH_AF_NUMBER << s);
    }
}

static void eth_gpio_init(void)
{
    ETH_GPIO_RCC_REG |= ETH_GPIO_CLOCK_MASK;
    (void)ETH_GPIO_RCC_REG;   /* Yazma-okuma gecikmesi icin */

    eth_gpio_init_af(ETH_PIN_REF_CLK_PORT, ETH_PIN_REF_CLK_NUM);
    eth_gpio_init_af(ETH_PIN_MDIO_PORT,    ETH_PIN_MDIO_NUM);
    eth_gpio_init_af(ETH_PIN_CRS_DV_PORT,  ETH_PIN_CRS_DV_NUM);
    eth_gpio_init_af(ETH_PIN_MDC_PORT,     ETH_PIN_MDC_NUM);
    eth_gpio_init_af(ETH_PIN_RXD0_PORT,    ETH_PIN_RXD0_NUM);
    eth_gpio_init_af(ETH_PIN_RXD1_PORT,    ETH_PIN_RXD1_NUM);
    eth_gpio_init_af(ETH_PIN_TX_EN_PORT,   ETH_PIN_TX_EN_NUM);
    eth_gpio_init_af(ETH_PIN_TXD0_PORT,    ETH_PIN_TXD0_NUM);
    eth_gpio_init_af(ETH_PIN_TXD1_PORT,    ETH_PIN_TXD1_NUM);
}

/* ===== PHY erisimi (porta delege) ====================================== */

ETH_Status_t ETH_PHY_Read(uint8_t phy_addr, uint8_t reg, uint16_t *value)
{
    if (value == NULL || phy_addr > 31U || reg > 31U) return ETH_ERR_PARAM;
    return ETH_Port_SMI_Read(phy_addr, reg, value);
}

ETH_Status_t ETH_PHY_Write(uint8_t phy_addr, uint8_t reg, uint16_t value)
{
    if (phy_addr > 31U || reg > 31U) return ETH_ERR_PARAM;
    return ETH_Port_SMI_Write(phy_addr, reg, value);
}

ETH_Status_t ETH_PHY_ScanAddress(uint8_t *found_addr)
{
    if (found_addr == NULL) return ETH_ERR_PARAM;

    for (uint8_t a = 0U; a < 32U; a++) {
        uint16_t id1 = 0U;
        if (ETH_Port_SMI_Read(a, PHY_REG_PHYID1, &id1) != ETH_OK) continue;
        /* Bos bus 0x0000 veya 0xFFFF verir; ikisi de gecersiz PHY ID. */
        if (id1 != 0x0000U && id1 != 0xFFFFU) {
            *found_addr = a;
            return ETH_OK;
        }
    }
    return ETH_ERR_PHY;
}

ETH_Status_t ETH_GetLinkState(ETH_LinkState_t *state)
{
    if (state == NULL) return ETH_ERR_PARAM;

    uint16_t bmcr = 0U, bmsr = 0U;
    if (ETH_Port_SMI_Read(PHY_ADDRESS, PHY_REG_BMCR, &bmcr) != ETH_OK) return ETH_ERR_PHY;

    /* BMSR'nin link biti "latching low": dusmus link'i yakalamak icin
     * iki kez okunur. Ilki gecmisi, ikincisi anlik durumu verir. */
    (void)ETH_Port_SMI_Read(PHY_ADDRESS, PHY_REG_BMSR, &bmsr);
    if (ETH_Port_SMI_Read(PHY_ADDRESS, PHY_REG_BMSR, &bmsr) != ETH_OK) return ETH_ERR_PHY;

    state->bcr          = bmcr;
    state->bsr          = bmsr;
    state->link_up      = (bmsr & PHY_BMSR_LINK_UP) != 0U;
    state->autoneg_done = (bmsr & PHY_BMSR_AUTONEG_DONE) != 0U;
    state->speed_mbps   = 10U;
    state->full_duplex  = false;

    if (state->link_up) {
        uint16_t sp = 10U; bool fd = false;
        if (ETH_PHY_GetSpeedDuplex(PHY_ADDRESS, &sp, &fd) == ETH_OK) {
            state->speed_mbps  = sp;
            state->full_duplex = fd;
        }
    }
    return ETH_OK;
}

/* ===== Ring kurulumu =================================================== */

static void eth_rings_init(void)
{
    memset((void *)rx_desc, 0, sizeof(rx_desc));
    memset((void *)tx_desc, 0, sizeof(tx_desc));

    ETH_Port_SetupRings(rx_desc, ETH_RX_DESC_COUNT, tx_desc, ETH_TX_DESC_COUNT);

    for (uint32_t i = 0U; i < ETH_RX_DESC_COUNT; i++) {
        ETH_Port_DescArmRx(&rx_desc[i], &rx_buf[i][0]);
    }

    rx_idx = 0U;
    tx_idx = 0U;
    rx_held = false;
    tx_claimed = false;
}

/* ===== Baslatma ======================================================== */

ETH_Status_t ETH_Driver_Init(void)
{
    ETH_Status_t st;

    memset(&stats, 0, sizeof(stats));
    driver_ready = false;

    /* Sira kritik: RMII secimi MAC clock'lari acilmadan once yapilmali,
     * yoksa MAC yanlis arayuzle reset'ten cikar. */
    eth_mpu_config();
    eth_gpio_init();

    st = ETH_Port_SelectRMII();
    if (st != ETH_OK) return st;

    st = ETH_Port_EnableClocks();
    if (st != ETH_OK) return st;

    /* Bu adim takilirsa neredeyse her zaman 50 MHz RMII referans saati yoktur. */
    st = ETH_Port_ResetCore();
    if (st != ETH_OK) return st;

    ETH_Port_ConfigureMDCClock(ETH_HCLK_HZ);

    st = ETH_PHY_Bringup(PHY_ADDRESS);
    if (st != ETH_OK) return st;

    ETH_LinkState_t link;
    st = ETH_GetLinkState(&link);
    if (st != ETH_OK) return st;
    if (!link.link_up) return ETH_ERR_LINK_DOWN;

    ETH_Port_SetSpeedDuplex(link.speed_mbps, link.full_duplex);

    const uint8_t mac[6] = { ETH_MAC_ADDR0, ETH_MAC_ADDR1, ETH_MAC_ADDR2,
                             ETH_MAC_ADDR3, ETH_MAC_ADDR4, ETH_MAC_ADDR5 };
    ETH_Port_SetMACAddress(mac);
    ETH_Port_ConfigureFilters();

    eth_rings_init();
    ETH_Port_Start();

    driver_ready = true;
    return ETH_OK;
}

void ETH_Driver_DeInit(void)
{
    ETH_Port_Shutdown();
    driver_ready = false;
}

bool ETH_Driver_IsReady(void) { return driver_ready; }

/* ===== Gonderme ======================================================== */

ETH_Status_t ETH_ClaimTxBuffer(uint8_t **buf)
{
    if (!driver_ready)  return ETH_ERR_DMA;
    if (buf == NULL)    return ETH_ERR_PARAM;
    if (tx_claimed)     return ETH_ERR_PARAM;

    if (!ETH_Port_DescIsOwnedByCPU(&tx_desc[tx_idx])) {
#if ETH_ENABLE_STATS
        stats.tx_no_desc++;
#endif
        return ETH_ERR_NO_TX_DESC;
    }

    *buf = &tx_buf[tx_idx][0];
    tx_claimed = true;
    return ETH_OK;
}

ETH_Status_t ETH_CommitTxBuffer(uint16_t len)
{
    if (!tx_claimed)            return ETH_ERR_PARAM;
    if (len == 0U)              { tx_claimed = false; return ETH_ERR_PARAM; }
    if (len > ETH_BUFFER_SIZE)  { tx_claimed = false; return ETH_ERR_TOO_LARGE; }

    /* Ethernet minimum frame 60 bayt (FCS haric). Kisa frame'i sifirla doldur;
     * MAC padding yapsa da acikca yapmak fuzzing testinde belirsizligi kaldirir. */
    uint16_t tx_len = len;
    if (tx_len < 60U) {
        memset(&tx_buf[tx_idx][tx_len], 0, 60U - tx_len);
        tx_len = 60U;
    }

    ETH_Port_DescArmTx(&tx_desc[tx_idx], &tx_buf[tx_idx][0], tx_len);

    tx_idx = (tx_idx + 1U) & TX_MASK;
    ETH_Port_KickTx(tx_idx);
    tx_claimed = false;

#if ETH_ENABLE_STATS
    stats.tx_frames++;
    stats.tx_bytes += tx_len;
#endif
    return ETH_OK;
}

ETH_Status_t ETH_SendFrame(const uint8_t *data, uint16_t len)
{
    uint8_t *buf = NULL;

    if (data == NULL || len == 0U) return ETH_ERR_PARAM;
    if (len > ETH_BUFFER_SIZE)     return ETH_ERR_TOO_LARGE;

    ETH_Status_t st = ETH_ClaimTxBuffer(&buf);
    if (st != ETH_OK) return st;

    memcpy(buf, data, len);
    return ETH_CommitTxBuffer(len);
}

/* ===== Alma (zero-copy) ================================================ */

ETH_Status_t ETH_ReceiveFrame(uint8_t **data, uint16_t *len)
{
    if (!driver_ready)               return ETH_ERR_DMA;
    if (data == NULL || len == NULL) return ETH_ERR_PARAM;
    if (rx_held)                     return ETH_ERR_PARAM;

    ETH_Desc_t *d = &rx_desc[rx_idx];

    if (!ETH_Port_DescIsOwnedByCPU(d)) return ETH_ERR_NO_DATA;

    __DMB();

    /* Hatali frame'i uygulamaya vermiyoruz: sayaci artir, descriptor'i iade et. */
    if (ETH_Port_DescRxHasError(d)) {
#if ETH_ENABLE_STATS
        stats.rx_crc_errors++;
#endif
        ETH_Port_DescArmRx(d, &rx_buf[rx_idx][0]);
        rx_idx = (rx_idx + 1U) & RX_MASK;
        ETH_Port_KickRx(rx_idx);
        return ETH_ERR_NO_DATA;
    }

    uint16_t flen = ETH_Port_DescGetRxLength(d);

    if (flen < 14U || flen > ETH_BUFFER_SIZE) {
        /* Fuzzing testinde bu yol sik tetiklenecek. Uygulamaya hicbir sey verme. */
#if ETH_ENABLE_STATS
        stats.rx_dropped++;
#endif
        ETH_Port_DescArmRx(d, &rx_buf[rx_idx][0]);
        rx_idx = (rx_idx + 1U) & RX_MASK;
        ETH_Port_KickRx(rx_idx);
        return ETH_ERR_NO_DATA;
    }

    *data = &rx_buf[rx_idx][0];
    *len  = flen;
    rx_held = true;

#if ETH_ENABLE_STATS
    stats.rx_frames++;
    stats.rx_bytes += flen;
#endif
    return ETH_OK;
}

void ETH_ReleaseRxFrame(void)
{
    if (!rx_held) return;

    ETH_Port_DescArmRx(&rx_desc[rx_idx], &rx_buf[rx_idx][0]);
    rx_idx = (rx_idx + 1U) & RX_MASK;
    rx_held = false;

    /* Tail pointer ilerletilmezse DMA bu descriptor'i gormez ve
     * ring bir tur sonra kalici olarak tikanir. */
    ETH_Port_KickRx(rx_idx);
}

/* ===== Istatistikler =================================================== */

void ETH_GetStats(ETH_Stats_t *s)
{
    if (s == NULL) return;
#if ETH_ENABLE_STATS
    /* Donanim sayaclari okundugunda temizlenir; biriktirerek tutuyoruz. */
    stats.rx_missed_hw += ETH_Port_GetMissedFrames();
    stats.dma_errors   += ETH_Port_GetAndClearDMAErrors();
#endif
    *s = stats;
}

void ETH_ResetStats(void)
{
    (void)ETH_Port_GetMissedFrames();
    (void)ETH_Port_GetAndClearDMAErrors();
    memset(&stats, 0, sizeof(stats));
}
