/**
  ******************************************************************************
  * @file    eth_iap.h
  * @brief   IAP (In-Application Programming) bootloader sozlesmesi.
  *
  * Opsiyonel modul (ETH_ENABLE_IAP). eth_app.c, E-AETIS uzerinden gelen
  * START_IAP / FW_DATA / END_IAP komutlarini bu 4 fonksiyona devreder.
  ******************************************************************************
  */
#ifndef ETH_IAP_H
#define ETH_IAP_H

#include "eth_driver.h"
#include <stdint.h>

/** @brief Yeni firmware yuklemesini baslatir. Bekleneni sifirlar.
 *  @param total_size Gelecek toplam bayt (ETH_IAP_MAX_SIZE'i asamaz)
 *  @param expected_crc32 Tum firmware uzerinden CRC32 (butunluk kontrolu)
 *  @retval ETH_OK, ETH_ERR_PARAM (boyut siniri asildi) */
ETH_Status_t ETH_IAP_Begin(uint32_t total_size, uint32_t expected_crc32);

/** @brief Bir firmware parcasini sirali olarak flash'a yazar.
 *  @param seq  Parca sira numarasi (kayip/tekrar tespiti icin)
 *  @param data Ham binary veri (en fazla ETH_IAP_CHUNK_SIZE bayt)
 *  @retval ETH_OK, ETH_ERR_PARAM, ETH_ERR_FLASH */
ETH_Status_t ETH_IAP_WriteChunk(uint32_t seq, const uint8_t *data, uint16_t len);

/** @brief Yuklemeyi kapatir; CRC32 dogrulamasi yapar.
 *  @retval ETH_OK (dogrulandi), ETH_ERR_PARAM (CRC uyusmuyor / eksik veri) */
ETH_Status_t ETH_IAP_Finish(void);

/** @brief Yeni uygulamaya (ETH_IAP_APP_BASE_ADDR) atlar. Geri donmez. */
void ETH_IAP_JumpToApplication(void);

#endif /* ETH_IAP_H */
