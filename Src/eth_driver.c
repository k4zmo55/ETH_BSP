/**
  ******************************************************************************
  * @file    eth_port_gmac.c
  * @brief   Klasik ST/Synopsys 3.x MAC portu (STM32F4, STM32F7).
  *
  * EQOS'tan temel farki: ring, descriptor'lar arasi NEXT-POINTER zinciri
  * ile kurulur (TCH/RCH bitleri) ve "kick" islemi tail pointer yerine
  * poll demand register'ina yazmaktir.
  ******************************************************************************
  */

#include "eth_device.h"

#if ETH_PORT_GMAC

#include "eth_port.h"
#include <string.h>

/* ===== MACCR ===== */
#define GMAC_MACCR_RE          (1UL << 2)
#define GMAC_MACCR_TE          (1UL << 3)
#define GMAC_MACCR_DM          (1UL << 11)
#define GMAC_MACCR_FES         (1UL << 14)
#define GMAC_MACCR_IPCO        (1UL << 10)

/* ===== MACFFR (frame filter) ===== */
#define GMAC_MACFFR_BFD        (1UL << 5)   /* Broadcast Frames Disable */
#define GMAC_MACFFR_PM         (1UL << 0)   /* Promiscuous */

/* ===== MACMIIAR ===== */
#define GMAC_MIIAR_MB          (1UL << 0)
#define GMAC_MIIAR_MW          (1UL << 1)
#define GMAC_MIIAR_CR_Pos      2U
#define GMAC_MIIAR_MR_Pos      6U
#define GMAC_MIIAR_PA_Pos      11U

/* ===== DMABMR / DMAOMR ===== */
#define GMAC_DMABMR_SR         (1UL << 0)   /* Software Reset */
#define GMAC_DMAOMR_SR         (1UL << 1)   /* Start Receive  */
#define GMAC_DMAOMR_ST         (1UL << 13)  /* Start Transmit */
#define GMAC_DMAOMR_TSF        (1UL << 21)
#define GMAC_DMAOMR_RSF        (1UL << 25)
#define GMAC_DMAOMR_FTF        (1UL << 20)

/* ===== DMASR ===== */
#define GMAC_DMASR_FBES        (1UL << 13)
#define GMAC_DMASR_RBUS        (1UL << 7)
#define GMAC_DMASR_TBUS        (1UL << 2)

/* ===== Descriptor bitleri (legacy normal format) ===== */
#define GMAC_DESC_OWN          (1UL << 31)
#define GMAC_TDES0_IC          (1UL << 30)
#define GMAC_TDES0_LS          (1UL << 29)
#define GMAC_TDES0_FS          (1UL << 28)
#define GMAC_TDES0_TCH         (1UL << 20)  /* Second Address Chained */
#define GMAC_TDES1_TBS1_MASK   (0x1FFFUL)
#define GMAC_RDES0_ES          (1UL << 15)
#define GMAC_RDES0_LS          (1UL << 8)
#define GMAC_RDES0_FL_Pos      16U
#define GMAC_RDES0_FL_MASK     (0x3FFFUL)
#define GMAC_RDES1_RCH         (1UL << 14)
#define GMAC_RDES1_RBS1_MASK   (0x1FFFUL)

#define GMAC_SMI_TIMEOUT_MS    100U
#define GMAC_RESET_TIMEOUT_MS  500U

static ETH_Desc_t *rx_ring_base;
static ETH_Desc_t *tx_ring_base;
static uint32_t    mdio_cr_value;

/* ===== Donanim getirme ================================================= */

ETH_Status_t ETH_Port_SelectRMII(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
    (void)RCC->APB2ENR;
    SYSCFG->PMC |= SYSCFG_PMC_MII_RMII_SEL;
    return ETH_OK;
}

ETH_Status_t ETH_Port_EnableClocks(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_ETHMACEN | RCC_AHB1ENR_ETHMACTXEN
                  | RCC_AHB1ENR_ETHMACRXEN;
    (void)RCC->AHB1ENR;
    return ETH_OK;
}

ETH_Status_t ETH_Port_ResetCore(void)
{
    uint32_t start;

    ETH->DMABMR |= GMAC_DMABMR_SR;

    start = ETH_GetTick();
    while (ETH->DMABMR & GMAC_DMABMR_SR) {
        if ((ETH_GetTick() - start) > GMAC_RESET_TIMEOUT_MS) return ETH_ERR_TIMEOUT;
    }
    return ETH_OK;
}

void ETH_Port_Shutdown(void)
{
    ETH->MACCR  &= ~(GMAC_MACCR_TE | GMAC_MACCR_RE);
    ETH->DMAOMR &= ~(GMAC_DMAOMR_ST | GMAC_DMAOMR_SR);
    RCC->AHB1ENR &= ~(RCC_AHB1ENR_ETHMACEN | RCC_AHB1ENR_ETHMACTXEN
                    | RCC_AHB1ENR_ETHMACRXEN);
}

/* ===== MAC konfigurasyonu ============================================== */

void ETH_Port_SetMACAddress(const uint8_t mac[6])
{
    ETH->MACA0HR = (1UL << 31)
                 | ((uint32_t)mac[5] << 8) | (uint32_t)mac[4];
    ETH->MACA0LR = ((uint32_t)mac[3] << 24) | ((uint32_t)mac[2] << 16)
                 | ((uint32_t)mac[1] << 8)  | (uint32_t)mac[0];
}

void ETH_Port_SetSpeedDuplex(uint16_t speed_mbps, bool full_duplex)
{
    uint32_t cr = ETH->MACCR & ~(GMAC_MACCR_FES | GMAC_MACCR_DM);
    if (speed_mbps == 100U) cr |= GMAC_MACCR_FES;
    if (full_duplex)        cr |= GMAC_MACCR_DM;
    ETH->MACCR = cr;
}

void ETH_Port_ConfigureFilters(void)
{
    /* BFD (Broadcast Frames Disable) TEMIZ kalmali - discovery broadcast. */
    ETH->MACFFR = 0U;

    ETH->DMAOMR |= GMAC_DMAOMR_TSF | GMAC_DMAOMR_RSF;
}

void ETH_Port_Start(void)
{
    ETH->MACCR  |= GMAC_MACCR_TE | GMAC_MACCR_RE;
    ETH->DMAOMR |= GMAC_DMAOMR_FTF;
    ETH->DMAOMR |= GMAC_DMAOMR_ST | GMAC_DMAOMR_SR;
}

/* ===== SMI ============================================================= */

void ETH_Port_ConfigureMDCClock(uint32_t hclk_hz)
{
    if      (hclk_hz <  35000000UL) mdio_cr_value = 2UL;  /* /16  */
    else if (hclk_hz <  60000000UL) mdio_cr_value = 3UL;  /* /26  */
    else if (hclk_hz < 100000000UL) mdio_cr_value = 0UL;  /* /42  */
    else if (hclk_hz < 150000000UL) mdio_cr_value = 1UL;  /* /62  */
    else                            mdio_cr_value = 4UL;  /* /102 */
}

static ETH_Status_t gmac_smi_wait(void)
{
    uint32_t start = ETH_GetTick();
    while (ETH->MACMIIAR & GMAC_MIIAR_MB) {
        if ((ETH_GetTick() - start) > GMAC_SMI_TIMEOUT_MS) return ETH_ERR_TIMEOUT;
    }
    return ETH_OK;
}

ETH_Status_t ETH_Port_SMI_Read(uint8_t phy_addr, uint8_t reg, uint16_t *val)
{
    if (gmac_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    ETH->MACMIIAR = ((uint32_t)phy_addr << GMAC_MIIAR_PA_Pos)
                  | ((uint32_t)reg      << GMAC_MIIAR_MR_Pos)
                  | (mdio_cr_value      << GMAC_MIIAR_CR_Pos)
                  | GMAC_MIIAR_MB;                    /* MW=0 -> read */

    if (gmac_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    *val = (uint16_t)(ETH->MACMIIDR & 0xFFFFU);
    return ETH_OK;
}

ETH_Status_t ETH_Port_SMI_Write(uint8_t phy_addr, uint8_t reg, uint16_t val)
{
    if (gmac_smi_wait() != ETH_OK) return ETH_ERR_TIMEOUT;

    ETH->MACMIIDR = (uint32_t)val;
    ETH->MACMIIAR = ((uint32_t)phy_addr << GMAC_MIIAR_PA_Pos)
                  | ((uint32_t)reg      << GMAC_MIIAR_MR_Pos)
                  | (mdio_cr_value      << GMAC_MIIAR_CR_Pos)
                  | GMAC_MIIAR_MW | GMAC_MIIAR_MB;

    return gmac_smi_wait();
}

/* ===== Descriptor soyutlamasi ========================================== */

void ETH_Port_SetupRings(ETH_Desc_t *rx, uint32_t rx_count,
                         ETH_Desc_t *tx, uint32_t tx_count)
{
    rx_ring_base = rx;
    tx_ring_base = tx;

    /* Legacy MAC'te ring, DES3'teki next-pointer ile ZINCIRLENIR. */
    for (uint32_t i = 0U; i < rx_count; i++) {
        rx[i].DES1 = GMAC_RDES1_RCH | (ETH_BUFFER_SIZE & GMAC_RDES1_RBS1_MASK);
        rx[i].DES3 = (uint32_t)(uintptr_t)&rx[(i + 1U) % rx_count];
    }
    for (uint32_t i = 0U; i < tx_count; i++) {
        tx[i].DES0 = GMAC_TDES0_TCH;
        tx[i].DES3 = (uint32_t)(uintptr_t)&tx[(i + 1U) % tx_count];
    }

    ETH->DMARDLAR = (uint32_t)(uintptr_t)rx;
    ETH->DMATDLAR = (uint32_t)(uintptr_t)tx;
}

bool ETH_Port_DescIsOwnedByCPU(const ETH_Desc_t *d)
{
    return (d->DES0 & GMAC_DESC_OWN) == 0U;   /* Legacy'de OWN, DES0'da */
}

bool ETH_Port_DescRxHasError(const ETH_Desc_t *d)
{
    if ((d->DES0 & GMAC_RDES0_LS) == 0U) return true;
    return (d->DES0 & GMAC_RDES0_ES) != 0U;
}

uint16_t ETH_Port_DescGetRxLength(const ETH_Desc_t *d)
{
    uint16_t fl = (uint16_t)((d->DES0 >> GMAC_RDES0_FL_Pos) & GMAC_RDES0_FL_MASK);
    /* Legacy MAC uzunluga 4 baytlik CRC'yi dahil eder; cikariyoruz. */
    return (fl > 4U) ? (uint16_t)(fl - 4U) : 0U;
}

void ETH_Port_DescArmRx(ETH_Desc_t *d, uint8_t *buf)
{
    d->DES2 = (uint32_t)(uintptr_t)buf;
    d->DES1 = GMAC_RDES1_RCH | (ETH_BUFFER_SIZE & GMAC_RDES1_RBS1_MASK);
    __DMB();
    d->DES0 = GMAC_DESC_OWN;
    __DMB();
}

void ETH_Port_DescArmTx(ETH_Desc_t *d, uint8_t *buf, uint16_t len)
{
    d->DES2 = (uint32_t)(uintptr_t)buf;
    d->DES1 = (uint32_t)len & GMAC_TDES1_TBS1_MASK;
    __DMB();
    d->DES0 = GMAC_DESC_OWN | GMAC_TDES0_IC | GMAC_TDES0_FS
            | GMAC_TDES0_LS | GMAC_TDES0_TCH;
    __DMB();
}

void ETH_Port_KickRx(uint32_t next_index)
{
    (void)next_index;
    /* Legacy'de tail pointer yok: RBUS bayragini temizleyip poll demand yaz. */
    if (ETH->DMASR & GMAC_DMASR_RBUS) {
        ETH->DMASR   = GMAC_DMASR_RBUS;
        ETH->DMARPDR = 0U;
    }
}

void ETH_Port_KickTx(uint32_t next_index)
{
    (void)next_index;
    if (ETH->DMASR & GMAC_DMASR_TBUS) {
        ETH->DMASR   = GMAC_DMASR_TBUS;
        ETH->DMATPDR = 0U;
    }
}

/* ===== Olcum =========================================================== */

uint32_t ETH_Port_GetMissedFrames(void)
{
    uint32_t v = ETH->DMAMFBOCR;   /* Okundugunda temizlenir */
    return v & 0xFFFFUL;
}

uint32_t ETH_Port_GetAndClearDMAErrors(void)
{
    uint32_t sr  = ETH->DMASR;
    uint32_t err = sr & (GMAC_DMASR_FBES | GMAC_DMASR_RBUS | GMAC_DMASR_TBUS);
    ETH->DMASR = err;

    uint32_t c = 0U;
    if (err & GMAC_DMASR_FBES) c++;
    if (err & GMAC_DMASR_RBUS) c++;
    if (err & GMAC_DMASR_TBUS) c++;
    return c;
}

#endif /* ETH_PORT_GMAC */
