/**
  ******************************************************************************
  * @file    eth_driver.h
  * @brief   Aileden bagimsiz surucu API'si. Kullanici dokunmaz.
  ******************************************************************************
  */
#ifndef ETH_DRIVER_H
#define ETH_DRIVER_H

#include "eth_device.h"
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    ETH_OK             =  0,
    ETH_ERR_PARAM      = -1,
    ETH_ERR_TIMEOUT    = -2,
    ETH_ERR_PHY        = -3,
    ETH_ERR_LINK_DOWN  = -4,
    ETH_ERR_NO_TX_DESC = -5,
    ETH_ERR_NO_DATA    = -6,
    ETH_ERR_TOO_LARGE  = -7,
    ETH_ERR_DMA        = -8,
    ETH_ERR_FLASH      = -9
} ETH_Status_t;

/* DMA descriptor. Alan anlamlari porta gore degisir; sadece port yorumlar. */
typedef struct __attribute__((aligned(32))) {
    volatile uint32_t DES0;
    volatile uint32_t DES1;
    volatile uint32_t DES2;
    volatile uint32_t DES3;
} ETH_Desc_t;

typedef struct {
    bool     link_up;
    uint16_t speed_mbps;
    bool     full_duplex;
    bool     autoneg_done;
    uint16_t bcr;              /* Ham BMCR - E-AETIS teshis ekrani icin */
    uint16_t bsr;              /* Ham BMSR */
} ETH_LinkState_t;

typedef struct {
    uint32_t rx_frames;
    uint32_t tx_frames;
    uint32_t rx_bytes;
    uint32_t tx_bytes;
    uint32_t rx_dropped;       /* Yazilim: bozuk/uzun frame elendi */
    uint32_t rx_missed_hw;     /* Donanim missed frame sayaci */
    uint32_t rx_crc_errors;
    uint32_t tx_no_desc;       /* TX ring dolu oldugu icin reddedilen */
    uint32_t dma_errors;
} ETH_Stats_t;

/* ===== Yasam dongusu ================================================== */
ETH_Status_t ETH_Driver_Init(void);
void         ETH_Driver_DeInit(void);
bool         ETH_Driver_IsReady(void);

/* ===== Frame transferi ================================================ */
ETH_Status_t ETH_SendFrame(const uint8_t *data, uint16_t len);

/** Zero-copy alim. Isiniz bitince ETH_ReleaseRxFrame() cagirmak ZORUNLU. */
ETH_Status_t ETH_ReceiveFrame(uint8_t **data, uint16_t *len);
void         ETH_ReleaseRxFrame(void);

/** TX buffer'ini dogrudan doldurmak icin (ekstra memcpy'den kacinmak).
 *  ETH_ClaimTxBuffer -> doldur -> ETH_CommitTxBuffer(len) */
ETH_Status_t ETH_ClaimTxBuffer(uint8_t **buf);
ETH_Status_t ETH_CommitTxBuffer(uint16_t len);

/* ===== PHY ============================================================ */
ETH_Status_t ETH_PHY_Read(uint8_t phy_addr, uint8_t reg, uint16_t *value);
ETH_Status_t ETH_PHY_Write(uint8_t phy_addr, uint8_t reg, uint16_t value);
ETH_Status_t ETH_PHY_ScanAddress(uint8_t *found_addr);

/* ===== Durum / olcum ================================================== */
ETH_Status_t ETH_GetLinkState(ETH_LinkState_t *state);
void         ETH_GetStats(ETH_Stats_t *stats);
void         ETH_ResetStats(void);

/* ===== Zaman tabani =================================================== */
uint32_t     ETH_GetTick(void);

#endif /* ETH_DRIVER_H */
