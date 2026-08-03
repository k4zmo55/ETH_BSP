/**
  ******************************************************************************
  * @file    eth_port_eqos.c
  * @brief   Synopsys DWC Ethernet QoS portu (STM32H5, STM32H7).
  *
  * Secilmeyen aile icin bu dosya BOS derlenir; kullanici hicbir dosyayi
  * build'den cikarmak zorunda kalmaz.
  ******************************************************************************
  */

#include "eth_device.h"

#if ETH_PORT_EQOS

#include "eth_port.h"
#include <string.h>

/* ===== Register bit tanimlari ==========================================
 * CMSIS bunlarin cogunu zaten tanimlar (ETH_MACCR_TE vb.), fakat isimler
 * H5/H7 arasinda ufak farkliliklar gosterebildigi icin burada acikca
 * tutuluyor. Boylece port dosyasi tek dogruluk kaynagi oluyor.
 * ====================================================================== */

/* MACCR */
#define EQOS_MACCR_RE          (1UL << 0)   /* Receiver Enable      */
#define EQOS_MACCR_TE          (1UL << 1)   /* Transmitter Enable   */
#define EQOS_MACCR_DM          (1UL << 13)  /* Duplex Mode          */
#define EQOS_MACCR_FES         (1UL << 14)  /* Fast Ethernet Speed  */
#define EQOS_MACCR_DCRS        (1UL << 9)
#define EQOS_MACCR_IPG_96BIT   (0UL << 24)

/* MACPFR - Packet Filter */
#define EQOS_MACPFR_PR         (1UL << 0)   /* Promiscuous          */
#define EQOS_MACPFR_DB         (1UL << 5)   /* Disable Broadcast!   */
#define EQOS_MACPFR_PM         (1UL << 4)   /* Pass all Multicast   */

/* MACA0HR */
#define EQOS_MACA0HR_AE        (1UL << 31)  /* Address Enable       */

/* MACMDIOAR */
#define EQOS_MDIOAR_MB         (1UL << 0)   /* MII Busy             */
#define EQOS_MDIOAR_MOC_WR     (1UL << 2)   /* Operation = Write    */
#define EQOS_MDIOAR_MOC_RD     (3UL << 2)   /* Operation = Read     */
#define EQOS_MDIOAR_CR_Pos     8U           /* Clock Range [11:8]   */
#define EQOS_MDIOAR_RDA_Pos    16U          /* Reg Addr    [20:16]  */
#define EQOS_MDIOAR_PA_Pos     21U          /* PHY Addr    [25:21]  */

/* DMAMR */
#define EQOS_DMAMR_SWR         (1UL << 0)   /* Software Reset       */

/* DMACCR / DMACTXCR / DMACRXCR */
#define EQOS_DMACTXCR_ST       (1UL << 0)   /* Start Transmit       */
#define EQOS_DMACTXCR_TXPBL_Pos 16U
#define EQOS_DMACRXCR_SR       (1UL << 0)   /* Start Receive        */
#define EQOS_DMACRXCR_RBSZ_Pos 1U           /* Rx Buffer Size [14:1]*/
#define EQOS_DMACRXCR_RXPBL_Pos 16U

/* MTL */
#define EQOS_MTLTQOMR_TSF      (1UL << 1)   /* Tx Store and Forward */
#define EQOS_MTLTQOMR_TXQEN    (2UL << 2)   /* Tx Queue Enable      */
#define EQOS_MTLRQOMR_RSF      (1UL << 5)   /* Rx Store and Forward */

/* DMACSR - hata bayraklari */
#define EQOS_DMACSR_FBE        (1UL << 12)  /* Fatal Bus Error      */
#define EQOS_DMACSR_RBU        (1UL << 7)   /* Rx Buffer Unavailable*/
#define EQOS_DMACSR_TBU        (1UL << 2)   /* Tx Buffer Unavailable*/

/* Descriptor bitleri */
#define EQOS_DESC_OWN          (1UL << 31)
#define EQOS_TDES2_IOC         (1UL << 31)
#define EQOS_TDES2_B1L_MASK    (0x3FFFUL)
#define EQOS_TDES3_FD          (1UL << 29)
#define EQOS_TDES3_LD          (1UL << 28)
#define EQOS_TDES3_FL_MASK     (0x7FFFUL)
#define EQOS_RDES3_IOC         (1UL << 30)
#define EQOS_RDES3_BUF1V       (1UL << 24)
#define EQOS_RDES3_LD          (1UL << 28)
#define EQOS_RDES3_ES          (1UL << 15)
#define EQOS_RDES3_PL_MASK     (0x7FFFUL)

#define EQOS_SMI_TIMEOUT_MS    100U
#define EQOS_RESET_TIMEOUT_MS  500U

/* Ring taban adresleri - Kick fonksiyonlari tail pointer hesabi icin saklar */
static ETH_Desc_t *rx_ring_base;
static ETH_Desc_t *tx_ring_base;
static uint32_t    rx_ring_count;
static uint32_t    tx_ring_count;

/* ===== Donanim getirme ================================================= */

ETH_Status_t ETH_Port_SelectRMII(void)
{
#if defined(ETH_RMII_VIA_SBS)
    /* STM32H5: SBS blogunun clock'u once acilmali. */
    RCC->APB3ENR |= RCC_APB3ENR_SBSEN;
    (void)RCC->APB3ENR;
    /* ETH_SEL_PHY = 0b100 -> RMII */
    SBS->PMCR = (SBS->PMCR & ~SBS_PMCR_ETH_SEL_PHY_Msk)
              | (4UL << SBS_PMCR_ETH_SEL_PHY_Pos);

#elif defined(ETH_RMII_VIA_SYSCFG_PMCR)
    /* STM32H7: SYSCFG->PMCR EPIS_SEL = 0b100 -> RMII */
    RCC->APB4ENR |= RCC_APB4ENR_SYSCFGEN;
    (void)RCC->APB4ENR;
    SYSCFG->PMCR = (SYSCFG->PMCR & ~SYSCFG_PMCR_EPIS_SEL_Msk)
                 | (4UL << SYSCFG_PMCR_EPIS_SEL_Pos);
#else
    #error "EQOS portu icin RMII secim yontemi tanimlanmadi."
#endif
    return ETH_OK;
}

ETH_Status_t ETH_Port_EnableClocks(void)
{
#if defined(ETH_TARGET_STM32H563)
    RCC->AHB1ENR |= RCC_AHB1ENR_ETHEN | RCC_AHB1ENR_ETHTXEN | RCC_AHB1ENR_ETHRXEN;
#elif defined(ETH_TARGET_STM32H743)
    RCC->AHB1ENR |= RCC_AHB1ENR_ETH1MACEN | RCC_AHB1ENR_ETH1TXEN | RCC_AHB1ENR_ETH1RXEN;
#endif
    (void)RCC->AHB1ENR;
    return ETH_OK;
}

ETH_Status_t ETH_Port_ResetCore(void)
{
    uint32_t start;

    ETH->DMAMR |= EQOS_DMAMR_SWR;

    /* SWR biti kendiliginden temizlenmezse 50 MHz RMII referans saati
     * gelmiyor demektir. En sik karsilasilan entegrasyon hatasi budur. */
    start = ETH_GetTick();
    while (ETH->DMAMR & EQOS_DMAMR_SWR) {
        if ((ETH_GetTick() - start) > EQOS_RESET_TIMEOUT_MS) {
            return ETH_ERR_TIMEOUT;
        }
    }
    return ETH_OK;
}

void ETH_Port_Shutdown(void)
{
    ETH->MACCR      &= ~(EQOS_MACCR_TE | EQOS_MACCR_RE);
    ETH->DMACTXCR   &= ~EQOS_DMACTXCR_ST;
    ETH->DMACRXCR   &= ~EQOS_DMACRXCR_SR;

#if defined(ETH_TARGET_STM32H563)
    RCC->AHB1ENR &= ~(RCC_AHB1ENR_ETHEN | RCC_AHB1ENR_ETHTXEN | RCC_AHB1ENR_ETHRXEN);
#elif defined(ETH_TARGET_STM32H743)
    RCC->AHB1ENR &= ~(RCC_AHB1ENR_ETH1MACEN | RCC_AHB1ENR_ETH1TXEN | RCC_AHB1ENR_ETH1RXEN);
#endif
}

/* ===== MAC konfigurasyonu ============================================== */

void ETH_Port_SetMACAddress(const uint8_t mac[6])
{
    ETH->MACA0HR = EQOS_MACA0HR_AE
                 | ((uint32_t)mac[5] << 8) | (uint32_t)mac[4];
    ETH->MACA0LR = ((uint32_t)mac[3] << 24) | ((uint32_t)mac[2] << 16)
                 | ((uint32_t)mac[1] << 8)  | (uint32_t)mac[0];
}

void ETH_Port_SetSpeedDuplex(uint16_t speed_mbps, bool full_duplex)
{
    uint32_t cr = ETH->MACCR & ~(EQOS_MACCR_FES | EQOS_MACCR_DM);

    if (speed_mbps == 100U) cr |= EQOS_MACCR_FES;
    if (full_duplex)        cr |= EQOS_MACCR_DM;

    ETH->MACCR = cr | EQOS_MACCR_IPG_96BIT;
}

void ETH_Port_ConfigureFilters(void)
{
    /* DB (Disable Broadcast) bitini TEMIZ birakmak sart:
     * E-AETIS discovery UDP broadcast ile calisiyor. */
    ETH->MACPFR = 0U;                       /* Promiscuous kapali, broadcast acik */

    /* Store-and-Forward: RMII'de TX underrun'i onler, kesinlikle acik olmali. */
    ETH->MTLTQOMR = EQOS_MTLTQOMR_TSF | EQOS_MTLTQOMR_TXQEN;
    ETH->MTLRQOMR = EQOS_MTLRQOMR_RSF;
}

void ETH_Port_Start(void)
{
    ETH->DMACTXCR |= EQOS_DMACTXCR_ST;
    ETH->DMACRXCR |= EQOS_DMACRXCR_SR;
    ETH->MACCR    |= EQOS_MACCR_TE | EQOS_MACCR_RE;
}

/* ===== SMI / MDIO ====================================================== */

static uint32_t mdio_cr_value;

void ETH_Port_ConfigureMDCClock(uint32_t hclk_hz)
{
    /* MDC 2.5 MHz'i asmamali. Yanlis bolucu = PHY hic cevap vermez. */
    if      (hclk_hz <  35000000UL) mdio_cr_value = 2UL;  /* HCLK/16  */
    else if (hclk_hz <  60000000UL) mdio_cr_value = 3UL;  /* HCLK/26  */
    else if (hclk_hz < 100000000UL) mdio_cr_value = 0UL;  /* HCLK/42  */
    else if (hclk_hz < 150000000UL) mdio_cr_value = 1UL;  /* HCLK/62  */
    else if (hclk_hz < 250000000UL) mdio_cr_value = 4UL;  /* HCLK/102 */
    else                            mdio_cr_value = 5UL;  /* HCLK/124 */
}

static ETH_Status_t eqos_smi_wait(void)
{
    uint32_t start = ETH_GetTick();
    while (ETH->MACMDIOAR & EQOS_MDIOAR_MB) {
        if ((ETH_GetTick() - start) > EQOS_SMI_TIMEOUT_MS) return ETH_ERR_TIMEOUT;
    }
    return ETH_OK;
}

ETH_Status_t ETH_Port_SMI_Read(uint8_t phy_addr, uint8_t reg, uint16_t *val)
{
    if (eqos_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    ETH->MACMDIOAR = ((uint32_t)phy_addr << EQOS_MDIOAR_PA_Pos)
                   | ((uint32_t)reg      << EQOS_MDIOAR_RDA_Pos)
                   | (mdio_cr_value      << EQOS_MDIOAR_CR_Pos)
                   | EQOS_MDIOAR_MOC_RD
                   | EQOS_MDIOAR_MB;

    if (eqos_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    *val = (uint16_t)(ETH->MACMDIODR & 0xFFFFU);
    return ETH_OK;
}

ETH_Status_t ETH_Port_SMI_Write(uint8_t phy_addr, uint8_t reg, uint16_t val)
{
    if (eqos_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    ETH->MACMDIODR = (uint32_t)val;
    ETH->MACMDIOAR = ((uint32_t)phy_addr << EQOS_MDIOAR_PA_Pos)
                   | ((uint32_t)reg      << EQOS_MDIOAR_RDA_Pos)
                   | (mdio_cr_value      << EQOS_MDIOAR_CR_Pos)
                   | EQOS_MDIOAR_MOC_WR
                   | EQOS_MDIOAR_MB;

    return eqos_smi_wait();
}

/* ===== Descriptor soyutlamasi ========================================== */

void ETH_Port_SetupRings(ETH_Desc_t *rx, uint32_t rx_count,
                         ETH_Desc_t *tx, uint32_t tx_count)
{
    rx_ring_base  = rx;  rx_ring_count = rx_count;
    tx_ring_base  = tx;  tx_ring_count = tx_count;

    /* TX ring: sahiplik CPU'da, hepsi bos. */
    for (uint32_t i = 0U; i < tx_count; i++) {
        tx[i].DES0 = 0U; tx[i].DES1 = 0U; tx[i].DES2 = 0U; tx[i].DES3 = 0U;
    }

    /* EQOS'ta ring, next-pointer ile degil taban adres + uzunluk ile kurulur. */
    ETH->DMACTXDLAR = (uint32_t)(uintptr_t)tx;
    ETH->DMACTXRLR  = tx_count - 1U;
    ETH->DMACTXDTPR = (uint32_t)(uintptr_t)&tx[0];

    ETH->DMACRXDLAR = (uint32_t)(uintptr_t)rx;
    ETH->DMACRXRLR  = rx_count - 1U;
    ETH->DMACRXDTPR = (uint32_t)(uintptr_t)&rx[rx_count - 1U];

    /* Rx buffer boyutu ve burst uzunluklari */
    ETH->DMACRXCR = (ETH->DMACRXCR & ~(0x3FFFUL << EQOS_DMACRXCR_RBSZ_Pos))
                  | (((uint32_t)ETH_BUFFER_SIZE & 0x3FFFUL) << EQOS_DMACRXCR_RBSZ_Pos)
                  | (32UL << EQOS_DMACRXCR_RXPBL_Pos);
    ETH->DMACTXCR = (ETH->DMACTXCR & ~(0x3FUL << EQOS_DMACTXCR_TXPBL_Pos))
                  | (32UL << EQOS_DMACTXCR_TXPBL_Pos);
}

bool ETH_Port_DescIsOwnedByCPU(const ETH_Desc_t *d)
{
    return (d->DES3 & EQOS_DESC_OWN) == 0U;
}

bool ETH_Port_DescRxHasError(const ETH_Desc_t *d)
{
    /* Sadece son descriptor'da (LD) hata ozeti anlamlidir. */
    if ((d->DES3 & EQOS_RDES3_LD) == 0U) return true;   /* Parcali frame: destek yok */
    return (d->DES3 & EQOS_RDES3_ES) != 0U;
}

uint16_t ETH_Port_DescGetRxLength(const ETH_Desc_t *d)
{
    return (uint16_t)(d->DES3 & EQOS_RDES3_PL_MASK);
}

void ETH_Port_DescArmRx(ETH_Desc_t *d, uint8_t *buf)
{
    d->DES0 = (uint32_t)(uintptr_t)buf;
    d->DES1 = 0U;
    d->DES2 = 0U;
    __DMB();
    d->DES3 = EQOS_DESC_OWN | EQOS_RDES3_BUF1V | EQOS_RDES3_IOC;
    __DMB();
}

void ETH_Port_DescArmTx(ETH_Desc_t *d, uint8_t *buf, uint16_t len)
{
    d->DES0 = (uint32_t)(uintptr_t)buf;
    d->DES1 = 0U;
    d->DES2 = EQOS_TDES2_IOC | ((uint32_t)len & EQOS_TDES2_B1L_MASK);

    /* OWN bitini EN SON yaz. Bariyer olmadan DMA descriptor'i yarim okuyabilir. */
    __DMB();
    d->DES3 = EQOS_DESC_OWN | EQOS_TDES3_FD | EQOS_TDES3_LD
            | ((uint32_t)len & EQOS_TDES3_FL_MASK);
    __DMB();
}

void ETH_Port_KickRx(uint32_t next_index)
{
    /* Tail pointer "buraya kadar isle" demektir; DMA tail'e ULASINCA durur.
     * Bu yuzden serbest biraktigimiz descriptor'in BIR ONCESINI gosteriyoruz. */
    uint32_t prev = (next_index + rx_ring_count - 1U) % rx_ring_count;
    ETH->DMACRXDTPR = (uint32_t)(uintptr_t)&rx_ring_base[prev];
}

void ETH_Port_KickTx(uint32_t next_index)
{
    ETH->DMACTXDTPR = (uint32_t)(uintptr_t)&tx_ring_base[next_index];
}

/* ===== Olcum =========================================================== */

uint32_t ETH_Port_GetMissedFrames(void)
{
    /* DMACMFCR okundugunda temizlenir. Alt 11 bit sayac, bit 15 overflow. */
    uint32_t v = ETH->DMACMFCR;
    return v & 0x7FFUL;
}

uint32_t ETH_Port_GetAndClearDMAErrors(void)
{
    uint32_t sr = ETH->DMACSR;
    uint32_t err = sr & (EQOS_DMACSR_FBE | EQOS_DMACSR_RBU | EQOS_DMACSR_TBU);

    /* DMACSR bitleri write-1-to-clear. */
    ETH->DMACSR = err;

    uint32_t count = 0U;
    if (err & EQOS_DMACSR_FBE) count += 1U;
    if (err & EQOS_DMACSR_RBU) count += 1U;
    if (err & EQOS_DMACSR_TBU) count += 1U;
    return count;
}

#endif /* ETH_PORT_EQOS */
