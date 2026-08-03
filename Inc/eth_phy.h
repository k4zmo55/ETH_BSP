/**
  ******************************************************************************
  * @file    eth_phy.h
  * @brief   PHY sozlesmesi. Kullanici dokunmaz.
  *
  * PHY, MAC ailesinden BAGIMSIZ bir eksendir. Yeni PHY = yeni dosya.
  ******************************************************************************
  */
#ifndef ETH_PHY_H
#define ETH_PHY_H

#include "eth_device.h"
#include "eth_driver.h"

/* IEEE 802.3 Clause 22 standart register'lari (tum PHY'lerde ayni) */
#define PHY_REG_BMCR        0x00U
#define PHY_REG_BMSR        0x01U
#define PHY_REG_PHYID1      0x02U
#define PHY_REG_PHYID2      0x03U
#define PHY_REG_ANAR        0x04U
#define PHY_REG_ANLPAR      0x05U

#define PHY_BMCR_RESET      (1U << 15)
#define PHY_BMCR_LOOPBACK   (1U << 14)
#define PHY_BMCR_SPEED_100  (1U << 13)
#define PHY_BMCR_AUTONEG_EN (1U << 12)
#define PHY_BMCR_POWERDOWN  (1U << 11)
#define PHY_BMCR_ISOLATE    (1U << 10)
#define PHY_BMCR_RESTART_AN (1U << 9)
#define PHY_BMCR_FULLDUPLEX (1U << 8)

#define PHY_BMSR_AUTONEG_ABLE (1U << 3)
#define PHY_BMSR_AUTONEG_DONE (1U << 5)
#define PHY_BMSR_LINK_UP      (1U << 2)

/* --- PHY surucu sozlesmesi --- */

/** @brief PHY'yi ayaga kaldir: donanim reset, yazilim reset, auto-neg. */
ETH_Status_t ETH_PHY_Bringup(uint8_t addr);

/** @brief Anlasilan hiz/duplex'i vendor register'indan coz.
 *  @note  Standart BMSR bunu vermez; her uretici farkli yere koyar. */
ETH_Status_t ETH_PHY_GetSpeedDuplex(uint8_t addr, uint16_t *speed, bool *fd);

/** @brief PHY'yi dahili loopback'e al (E-AETIS kablo-suz test icin). */
ETH_Status_t ETH_PHY_SetLoopback(uint8_t addr, bool enable);

/** @brief Insan okunur PHY adi (E-AETIS teshis ekraninda gosterilir). */
const char  *ETH_PHY_GetName(void);

#endif /* ETH_PHY_H */
