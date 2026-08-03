/**
  ******************************************************************************
  * @file    eth_device.h
  * @brief   MCU -> MAC ailesi + yetenek eslemesi. Kullanici dokunmaz.
  *
  * Yeni bir MCU desteklemek = buraya bir blok eklemek.
  * Ailesi zaten destekleniyorsa BASKA HICBIR DOSYA DEGISMEZ.
  ******************************************************************************
  */
#ifndef ETH_DEVICE_H
#define ETH_DEVICE_H

#include "eth_config.h"
#include <stdint.h>
#include <stddef.h>

/* ===== Hedef sayisi dogrulamasi ======================================== */
#define ETH_TGT_N_ (defined(ETH_TARGET_STM32H563) + \
                    defined(ETH_TARGET_STM32H743) + \
                    defined(ETH_TARGET_STM32F407) + \
                    defined(ETH_TARGET_STM32F767))
#if ETH_TGT_N_ == 0
  #error "eth_config.h icinde bir ETH_TARGET_* secilmedi."
#elif ETH_TGT_N_ > 1
  #error "eth_config.h icinde birden fazla ETH_TARGET_* secili."
#endif

/* ===== PHY sayisi dogrulamasi ========================================== */
#define ETH_PHY_N_ (defined(ETH_PHY_LAN8720A) + \
                    defined(ETH_PHY_LAN8742A) + \
                    defined(ETH_PHY_KSZ8081))
#if ETH_PHY_N_ != 1
  #error "eth_config.h icinde tam olarak bir PHY secilmeli."
#endif

/* ==========================================================================
 * HEDEFE OZEL BLOKLAR
 *
 * ETH_PORT_EQOS : Synopsys DWC Ethernet QoS. Ring = taban adres + uzunluk
 *                 + tail pointer. SMI = MACMDIOAR/MACMDIODR.
 * ETH_PORT_GMAC : Klasik ST/Synopsys 3.x MAC. Ring = next-pointer zinciri.
 *                 SMI = MACMIIAR/MACMIIDR.
 * ========================================================================== */

#if defined(ETH_TARGET_STM32H563)
  #include "stm32h5xx.h"
  #define ETH_PORT_EQOS        1
  #define ETH_PORT_GMAC        0
  #define ETH_HAS_DCACHE       1
  #define ETH_RMII_VIA_SBS     1        /* SBS->PMCR */
  #define ETH_GPIO_RCC_REG     (RCC->AHB2ENR)
  #define ETH_DEVICE_NAME      "STM32H563"

#elif defined(ETH_TARGET_STM32H743)
  #include "stm32h7xx.h"
  #define ETH_PORT_EQOS        1
  #define ETH_PORT_GMAC        0
  #define ETH_HAS_DCACHE       1
  #define ETH_RMII_VIA_SYSCFG_PMCR 1    /* SYSCFG->PMCR EPIS_SEL */
  #define ETH_GPIO_RCC_REG     (RCC->AHB4ENR)
  #define ETH_DEVICE_NAME      "STM32H743"
  #if (ETH_DESC_REGION_BASE >= 0x20000000UL) && (ETH_DESC_REGION_BASE < 0x24000000UL)
    #error "H7'de descriptor bolgesi DTCM'de olamaz. D2 SRAM kullanin (0x30000000)."
  #endif

#elif defined(ETH_TARGET_STM32F407)
  #include "stm32f4xx.h"
  #define ETH_PORT_EQOS        0
  #define ETH_PORT_GMAC        1
  #define ETH_HAS_DCACHE       0
  #define ETH_RMII_VIA_SYSCFG_PMC 1     /* SYSCFG->PMC MII_RMII_SEL */
  #define ETH_GPIO_RCC_REG     (RCC->AHB1ENR)
  #define ETH_DEVICE_NAME      "STM32F407"

#elif defined(ETH_TARGET_STM32F767)
  #include "stm32f7xx.h"
  #define ETH_PORT_EQOS        0
  #define ETH_PORT_GMAC        1
  #define ETH_HAS_DCACHE       1
  #define ETH_RMII_VIA_SYSCFG_PMC 1
  #define ETH_GPIO_RCC_REG     (RCC->AHB1ENR)
  #define ETH_DEVICE_NAME      "STM32F767"
#endif

/* ===== Descriptor section adi ========================================== */
#define ETH_DESC_SECTION       ".eth_desc"

/* ===== Saglik kontrolleri ============================================== */
#if (ETH_RX_DESC_COUNT & (ETH_RX_DESC_COUNT - 1U)) != 0U
  #error "ETH_RX_DESC_COUNT 2'nin kuvveti olmali."
#endif
#if (ETH_TX_DESC_COUNT & (ETH_TX_DESC_COUNT - 1U)) != 0U
  #error "ETH_TX_DESC_COUNT 2'nin kuvveti olmali."
#endif
#if (ETH_BUFFER_SIZE < 1524U) || ((ETH_BUFFER_SIZE % 4U) != 0U)
  #error "ETH_BUFFER_SIZE >= 1524 ve 4'un kati olmali."
#endif
#if ETH_HAS_DCACHE && !ETH_USE_MPU_NONCACHEABLE
  #warning "D-Cache'li hedefte MPU non-cacheable kapali: DMA verisi bozulacak."
#endif

/* Descriptor + buffer'larin ayrilan bolgeye sigdigini derleme aninda dogrula */
#define ETH_DESC_FOOTPRINT_ ( (ETH_RX_DESC_COUNT + ETH_TX_DESC_COUNT) * 32U + \
                              (ETH_RX_DESC_COUNT + ETH_TX_DESC_COUNT) * ETH_BUFFER_SIZE )

/* Buradaki ETH_DESC_FOOTPRINT değeri 32KB'den büyük olmamalı */
#if ETH_DESC_FOOTPRINT_ > ETH_DESC_REGION_SIZE      
  #error "Descriptor+buffer toplami ETH_DESC_REGION_SIZE'i asiyor."
#endif

#endif /* ETH_DEVICE_H */
