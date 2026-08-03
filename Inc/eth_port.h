/**
  ******************************************************************************
  * @file    eth_port.h
  * @brief   MAC ailesi port sozlesmesi. Kullanici dokunmaz.
  *
  * eth_driver.c bu sozlesmeden baska donanim fonksiyonu cagirmaz.
  * Yeni MAC ailesi = bu fonksiyonlari bir dosyada implemente etmek.
  ******************************************************************************
  */
#ifndef ETH_PORT_H
#define ETH_PORT_H

#include "eth_device.h"
#include "eth_driver.h"

/* --- Donanim getirme --- */
ETH_Status_t ETH_Port_SelectRMII(void);
ETH_Status_t ETH_Port_EnableClocks(void);
ETH_Status_t ETH_Port_ResetCore(void);
void         ETH_Port_Shutdown(void);

/* --- MAC konfigurasyonu --- */
void ETH_Port_SetMACAddress(const uint8_t mac[6]);
void ETH_Port_SetSpeedDuplex(uint16_t speed_mbps, bool full_duplex);
void ETH_Port_ConfigureFilters(void);   /* Broadcast KABUL edilmeli */
void ETH_Port_Start(void);

/* --- SMI / MDIO --- */
void         ETH_Port_ConfigureMDCClock(uint32_t hclk_hz);
ETH_Status_t ETH_Port_SMI_Read(uint8_t phy_addr, uint8_t reg, uint16_t *val);
ETH_Status_t ETH_Port_SMI_Write(uint8_t phy_addr, uint8_t reg, uint16_t val);

/* --- Descriptor soyutlamasi --- */
void     ETH_Port_SetupRings(ETH_Desc_t *rx, uint32_t rx_count,
                             ETH_Desc_t *tx, uint32_t tx_count);
bool     ETH_Port_DescIsOwnedByCPU(const ETH_Desc_t *d);
bool     ETH_Port_DescRxHasError(const ETH_Desc_t *d);
uint16_t ETH_Port_DescGetRxLength(const ETH_Desc_t *d);
void     ETH_Port_DescArmRx(ETH_Desc_t *d, uint8_t *buf);
void     ETH_Port_DescArmTx(ETH_Desc_t *d, uint8_t *buf, uint16_t len);
void     ETH_Port_KickRx(uint32_t next_index);
void     ETH_Port_KickTx(uint32_t next_index);

/* --- Olcum --- */
uint32_t ETH_Port_GetMissedFrames(void);
uint32_t ETH_Port_GetAndClearDMAErrors(void);

#endif /* ETH_PORT_H */
