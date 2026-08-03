/**
  ******************************************************************************
  * @file    eth_config.h
  * @brief   E-AETIS / Ethernet_BSP - Kullanici Konfigurasyonu
  *
  * >>> KULLANICININ DUZENLEDIGI TEK DOSYA BUDUR. <<<
  ******************************************************************************
  */
#ifndef ETH_CONFIG_H
#define ETH_CONFIG_H

/* ===== 1) HEDEF ISLEMCI (sadece birini birakin) ========================== */
#define ETH_TARGET_STM32H563
/* #define ETH_TARGET_STM32H743 */
/* #define ETH_TARGET_STM32F407 */
/* #define ETH_TARGET_STM32F767 */

/* ===== 2) PHY CIPI (sadece birini birakin) ============================== */
#define ETH_PHY_LAN8720A
/* #define ETH_PHY_LAN8742A */
/* #define ETH_PHY_KSZ8081  */

/* ===== 3) AG KIMLIGI ==================================================== */
/* MAC: locally-administered olmasi icin ilk baytin 2. biti 1 olmali. */
#define ETH_MAC_ADDR0            0x02U
#define ETH_MAC_ADDR1            0x00U
#define ETH_MAC_ADDR2            0x00U
#define ETH_MAC_ADDR3            0x00U
#define ETH_MAC_ADDR4            0x00U
#define ETH_MAC_ADDR5            0x01U

#define ETH_IP_ADDR0             192U
#define ETH_IP_ADDR1             168U
#define ETH_IP_ADDR2             1U
#define ETH_IP_ADDR3             50U

#define ETH_NETMASK0             255U
#define ETH_NETMASK1             255U
#define ETH_NETMASK2             255U
#define ETH_NETMASK3             0U

#define ETH_GATEWAY0             192U
#define ETH_GATEWAY1             168U
#define ETH_GATEWAY2             1U
#define ETH_GATEWAY3             1U

/* ===== 4) PHY AYARLARI ================================================== */
#define PHY_ADDRESS              0x00U   /* Bilmiyorsaniz ETH_PHY_ScanAddress() */

/* PHY donanim reset pini. Kullanmiyorsaniz ETH_PHY_HW_RESET'i 0 yapin. */
#define ETH_PHY_HW_RESET         0U
#define ETH_PHY_RESET_PORT       GPIOA
#define ETH_PHY_RESET_PIN        5U
#define ETH_PHY_RESET_ACTIVE_LOW 1U
#define ETH_PHY_RESET_HOLD_MS    30U

/* 0 = auto-negotiation kapali, 100/Full zorlanir. */
#define ETH_AUTONEG_TIMEOUT_MS   3000U

/* ===== 5) RMII PIN HARITASI ============================================= */
/* NUCLEO-H563ZI tipik atamalari. KENDI SEMANIZDAN DOGRULAYIN. */
#define ETH_AF_NUMBER            11U

#define ETH_PIN_REF_CLK_PORT     GPIOA
#define ETH_PIN_REF_CLK_NUM      1U
#define ETH_PIN_MDIO_PORT        GPIOA
#define ETH_PIN_MDIO_NUM         2U
#define ETH_PIN_CRS_DV_PORT      GPIOA
#define ETH_PIN_CRS_DV_NUM       7U
#define ETH_PIN_MDC_PORT         GPIOC
#define ETH_PIN_MDC_NUM          1U
#define ETH_PIN_RXD0_PORT        GPIOC
#define ETH_PIN_RXD0_NUM         4U
#define ETH_PIN_RXD1_PORT        GPIOC
#define ETH_PIN_RXD1_NUM         5U
#define ETH_PIN_TX_EN_PORT       GPIOG
#define ETH_PIN_TX_EN_NUM        11U
#define ETH_PIN_TXD0_PORT        GPIOG
#define ETH_PIN_TXD0_NUM         13U
#define ETH_PIN_TXD1_PORT        GPIOG
#define ETH_PIN_TXD1_NUM         12U

/* Kullanilan GPIO portlarinin clock'unu acmak icin bit maskesi.
 * A=0, B=1, C=2 ... H=7 seklinde bit pozisyonu. Yukaridaki haritada
 * A, C ve G kullanildigi icin: (1<<0)|(1<<2)|(1<<6) */
#define ETH_GPIO_CLOCK_MASK      ((1UL << 0) | (1UL << 2) | (1UL << 6))

/* ===== 6) DMA / BELLEK ================================================== */
#define ETH_RX_DESC_COUNT        8U      /* 2'nin kuvveti olmali */
#define ETH_TX_DESC_COUNT        4U      /* 2'nin kuvveti olmali */
#define ETH_BUFFER_SIZE          1536U   /* 4'un kati, >= 1524   */

/* Descriptor bolgesi. Linker script'te .eth_desc section'i buraya
 * yerlesmeli. H7'de DTCM KULLANMAYIN - ETH DMA oraya erisemez. */
#define ETH_DESC_REGION_BASE     0x20000000UL
#define ETH_DESC_REGION_SIZE     (32U * 1024U)
#define ETH_MPU_REGION_NUMBER    0U
#define ETH_USE_MPU_NONCACHEABLE 1U

/* HCLK frekansi - MDC bolucusu bundan hesaplanir. */
#define ETH_HCLK_HZ              250000000UL

/* ===== 7) OZELLIK ANAHTARLARI ========================================== */
#define ETH_ENABLE_ARP           1U
#define ETH_ENABLE_ICMP          1U
#define ETH_ENABLE_UDP           1U
#define ETH_ENABLE_STATS         1U
#define ETH_ENABLE_EAETIS_CMD    1U

/* Kullanici tanimli komutlar (LED, sensor vb.) ve telemetri gonderimi.
 * BSP kullanicinin donanimini BILMEZ; sadece komutu ona yonlendirir. */
#define ETH_ENABLE_USER_CMD      1U
#define ETH_USER_CMD_MAX_LEN     24U    /* Komut adi tampon boyutu   */
#define ETH_USER_ARGS_MAX_LEN    112U   /* Argüman tampon boyutu     */
#define ETH_USER_RESP_MAX_LEN    256U   /* Yanit tampon boyutu       */
#define ETH_ENABLE_IAP           0U      /* Flash yazma yetkisi verir! */

/* E-AETIS GUI tek port kullanir (ethernet_test_gui.py varsayilani 5000). */
#define ETH_EAETIS_PORT          5000U

/* Telemetri: kullanicinin kendi degiskenlerini (sensor, LED, sayac) arayuze
 * acmasini saglar. Kullanici ETH_BSP_RegisterVar() ile kaydeder; cekirdek
 * dosyalara HICBIR SEKILDE dokunulmaz. */
#define ETH_ENABLE_TELEMETRY     1U
#define ETH_MAX_VARIABLES        16U

/* IAP ayarlari (ETH_ENABLE_IAP=1 ise gecerli) */
#define ETH_IAP_APP_BASE_ADDR    0x08020000UL  /* Uygulama basi (bootloader sonrasi) */
#define ETH_IAP_MAX_SIZE         (256U * 1024U)
#define ETH_IAP_CHUNK_SIZE       512U

/* ARP cache girdi sayisi */
#define ETH_ARP_CACHE_SIZE       4U

/* ===== 8) HATA AYIKLAMA ================================================ */
#define ETH_DEBUG_ENABLE         0U

#endif /* ETH_CONFIG_H */
