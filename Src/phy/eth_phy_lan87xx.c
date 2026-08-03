/**
  ******************************************************************************
  * @file    eth_phy_lan87xx.c
  * @brief   Microchip LAN8720A / LAN8742A PHY surucusu.
  ******************************************************************************
  */
#include "eth_device.h"

#if defined(ETH_PHY_LAN8720A) || defined(ETH_PHY_LAN8742A)

#include "eth_phy.h"

/* Special Control/Status register (register 31) - hiz/duplex burada. */
#define LAN87XX_REG_SCSR        0x1FU
#define LAN87XX_SCSR_AUTODONE   (1U << 12)
#define LAN87XX_SCSR_MODE_Msk   (0x7U << 2)
#define LAN87XX_SCSR_10HD       (0x1U << 2)
#define LAN87XX_SCSR_100HD      (0x2U << 2)
#define LAN87XX_SCSR_10FD       (0x5U << 2)
#define LAN87XX_SCSR_100FD      (0x6U << 2)

static void phy_delay_ms(uint32_t ms)
{
    uint32_t t = ETH_GetTick();
    while ((ETH_GetTick() - t) < ms) { __NOP(); }
}

ETH_Status_t ETH_PHY_Bringup(uint8_t addr)
{
    uint16_t reg = 0U;
    uint32_t start;

#if ETH_PHY_HW_RESET
    /* Donanim reset pini: push-pull output yap, darbe uygula. */
    {
        const uint32_t p2 = ETH_PHY_RESET_PIN * 2U;
        ETH_PHY_RESET_PORT->MODER = (ETH_PHY_RESET_PORT->MODER & ~(3UL << p2))
                                  | (1UL << p2);          /* output */
        ETH_PHY_RESET_PORT->OTYPER &= ~(1UL << ETH_PHY_RESET_PIN);

#if ETH_PHY_RESET_ACTIVE_LOW
        ETH_PHY_RESET_PORT->BSRR = (1UL << (ETH_PHY_RESET_PIN + 16U)); /* low  */
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
        ETH_PHY_RESET_PORT->BSRR = (1UL << ETH_PHY_RESET_PIN);         /* high */
#else
        ETH_PHY_RESET_PORT->BSRR = (1UL << ETH_PHY_RESET_PIN);
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
        ETH_PHY_RESET_PORT->BSRR = (1UL << (ETH_PHY_RESET_PIN + 16U));
#endif
        /* LAN8720A datasheet: reset sonrasi SMI erisimi icin bekleme gerekir. */
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
    }
#endif

    /* PHY gercekten orada mi? */
    if (ETH_PHY_Read(addr, PHY_REG_PHYID1, &reg) != ETH_OK) return ETH_ERR_PHY;
    if (reg == 0x0000U || reg == 0xFFFFU) return ETH_ERR_PHY;

    /* Yazilim reset */
    if (ETH_PHY_Write(addr, PHY_REG_BMCR, PHY_BMCR_RESET) != ETH_OK) return ETH_ERR_PHY;

    start = ETH_GetTick();
    do {
        if ((ETH_GetTick() - start) > 500U) return ETH_ERR_TIMEOUT;
        if (ETH_PHY_Read(addr, PHY_REG_BMCR, &reg) != ETH_OK) return ETH_ERR_PHY;
    } while (reg & PHY_BMCR_RESET);

#if (ETH_AUTONEG_TIMEOUT_MS > 0U)
    if (ETH_PHY_Write(addr, PHY_REG_BMCR,
                      PHY_BMCR_AUTONEG_EN | PHY_BMCR_RESTART_AN) != ETH_OK) {
        return ETH_ERR_PHY;
    }

    start = ETH_GetTick();
    do {
        if ((ETH_GetTick() - start) > ETH_AUTONEG_TIMEOUT_MS) return ETH_ERR_LINK_DOWN;
        if (ETH_PHY_Read(addr, PHY_REG_BMSR, &reg) != ETH_OK) return ETH_ERR_PHY;
    } while ((reg & PHY_BMSR_AUTONEG_DONE) == 0U);
#else
    if (ETH_PHY_Write(addr, PHY_REG_BMCR,
                      PHY_BMCR_SPEED_100 | PHY_BMCR_FULLDUPLEX) != ETH_OK) {
        return ETH_ERR_PHY;
    }
    phy_delay_ms(50U);
#endif

    return ETH_OK;
}

ETH_Status_t ETH_PHY_GetSpeedDuplex(uint8_t addr, uint16_t *speed, bool *fd)
{
    uint16_t scsr = 0U;

    if (speed == NULL || fd == NULL) return ETH_ERR_PARAM;
    if (ETH_PHY_Read(addr, LAN87XX_REG_SCSR, &scsr) != ETH_OK) return ETH_ERR_PHY;

    switch (scsr & LAN87XX_SCSR_MODE_Msk) {
        case LAN87XX_SCSR_100FD: *speed = 100U; *fd = true;  break;
        case LAN87XX_SCSR_100HD: *speed = 100U; *fd = false; break;
        case LAN87XX_SCSR_10FD:  *speed = 10U;  *fd = true;  break;
        case LAN87XX_SCSR_10HD:  *speed = 10U;  *fd = false; break;
        default:                 *speed = 10U;  *fd = false; return ETH_ERR_PHY;
    }
    return ETH_OK;
}

ETH_Status_t ETH_PHY_SetLoopback(uint8_t addr, bool enable)
{
    uint16_t bmcr = 0U;
    if (ETH_PHY_Read(addr, PHY_REG_BMCR, &bmcr) != ETH_OK) return ETH_ERR_PHY;

    if (enable) bmcr |=  PHY_BMCR_LOOPBACK;
    else        bmcr &= ~PHY_BMCR_LOOPBACK;

    return ETH_PHY_Write(addr, PHY_REG_BMCR, bmcr);
}

const char *ETH_PHY_GetName(void)
{
#if defined(ETH_PHY_LAN8742A)
    return "LAN8742A";
#else
    return "LAN8720A";
#endif
}

#endif /* LAN87xx */
