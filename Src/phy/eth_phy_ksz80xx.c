/**
  ******************************************************************************
  * @file    eth_phy_ksz80xx.c
  * @brief   Microchip KSZ8081 PHY surucusu.
  ******************************************************************************
  */
#include "eth_device.h"

#if defined(ETH_PHY_KSZ8081)

#include "eth_phy.h"

/* PHY Control 1 (register 0x1E) - Operation Mode Indication */
#define KSZ8081_REG_PHYCTRL1    0x1EU
#define KSZ8081_OPMODE_Msk      (0x7U << 0)
#define KSZ8081_OPMODE_10HD     0x1U
#define KSZ8081_OPMODE_100HD    0x2U
#define KSZ8081_OPMODE_10FD     0x5U
#define KSZ8081_OPMODE_100FD    0x6U

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
    {
        const uint32_t p2 = ETH_PHY_RESET_PIN * 2U;
        ETH_PHY_RESET_PORT->MODER = (ETH_PHY_RESET_PORT->MODER & ~(3UL << p2))
                                  | (1UL << p2);
        ETH_PHY_RESET_PORT->OTYPER &= ~(1UL << ETH_PHY_RESET_PIN);
#if ETH_PHY_RESET_ACTIVE_LOW
        ETH_PHY_RESET_PORT->BSRR = (1UL << (ETH_PHY_RESET_PIN + 16U));
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
        ETH_PHY_RESET_PORT->BSRR = (1UL << ETH_PHY_RESET_PIN);
#else
        ETH_PHY_RESET_PORT->BSRR = (1UL << ETH_PHY_RESET_PIN);
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
        ETH_PHY_RESET_PORT->BSRR = (1UL << (ETH_PHY_RESET_PIN + 16U));
#endif
        phy_delay_ms(ETH_PHY_RESET_HOLD_MS);
    }
#endif

    if (ETH_PHY_Read(addr, PHY_REG_PHYID1, &reg) != ETH_OK) return ETH_ERR_PHY;
    if (reg == 0x0000U || reg == 0xFFFFU) return ETH_ERR_PHY;

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
    uint16_t ctrl = 0U;

    if (speed == NULL || fd == NULL) return ETH_ERR_PARAM;
    if (ETH_PHY_Read(addr, KSZ8081_REG_PHYCTRL1, &ctrl) != ETH_OK) return ETH_ERR_PHY;

    switch (ctrl & KSZ8081_OPMODE_Msk) {
        case KSZ8081_OPMODE_100FD: *speed = 100U; *fd = true;  break;
        case KSZ8081_OPMODE_100HD: *speed = 100U; *fd = false; break;
        case KSZ8081_OPMODE_10FD:  *speed = 10U;  *fd = true;  break;
        case KSZ8081_OPMODE_10HD:  *speed = 10U;  *fd = false; break;
        default:                   *speed = 10U;  *fd = false; return ETH_ERR_PHY;
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

const char *ETH_PHY_GetName(void) { return "KSZ8081"; }

#endif /* KSZ8081 */
