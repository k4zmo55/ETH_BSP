/**
  ******************************************************************************
  * @file    eth_iap.c
  * @brief   IAP (In-Application Programming) bootloader - flash yazma ve
  *          CRC32 dogrulama.
  *
  * Su an sadece STM32H563 icin yazildi (tek banka, 8 KB sektor, 128-bit
  * quad-word programlama). Baska bir hedefte ETH_ENABLE_IAP acilirsa
  * derleme #error ile durur; o zaman bu dosyaya ilgili hedefin flash
  * IP blogu icin ayri bir kod yolu eklenmelidir.
  ******************************************************************************
  */

#include "eth_device.h"

#if ETH_ENABLE_IAP

#if !defined(ETH_TARGET_STM32H563)
  #error "eth_iap.c flash mantigi su an sadece STM32H563 icin yazildi."
#endif

#include "eth_iap.h"
#include <string.h>

#define IAP_FLASH_KEY1        0x45670123UL
#define IAP_FLASH_KEY2        0xCDEF89ABUL
#define IAP_SECTOR_SIZE        (8U * 1024U)   /* H563: tek banka, 8 KB/sektor */
#define IAP_QUADWORD_SIZE      16U            /* Flash sadece 128-bit yazilabilir */
#define IAP_FLASH_OP_TIMEOUT_MS 5000U

static uint32_t iap_expected_size;
static uint32_t iap_expected_crc32;
static uint32_t iap_received_bytes;   /* Uygulamadan alinan toplam bayt      */
static uint32_t iap_write_offset;     /* Flash'a fiilen yazilan bayt (16'nin katı) */
static uint32_t iap_running_crc32;
static uint8_t  iap_qw_buf[IAP_QUADWORD_SIZE];
static uint8_t  iap_qw_fill;
static bool     iap_active;

/* ===== CRC32 (IEEE 802.3 / zlib.crc32 ile ayni polinom 0xEDB88320) ===== */

static uint32_t crc32_update(uint32_t crc, const uint8_t *data, uint32_t len)
{
    crc = ~crc;
    for (uint32_t i = 0U; i < len; i++) {
        crc ^= data[i];
        for (uint32_t b = 0U; b < 8U; b++) {
            uint32_t mask = (uint32_t)(-(int32_t)(crc & 1U));
            crc = (crc >> 1) ^ (0xEDB88320UL & mask);
        }
    }
    return ~crc;
}

/* ===== Flash denetleyici yardimcilari =================================== */

static ETH_Status_t flash_wait_ready(void)
{
    uint32_t start = ETH_GetTick();
    while (FLASH->NSSR & FLASH_NSSR_BSY) {
        if ((ETH_GetTick() - start) > IAP_FLASH_OP_TIMEOUT_MS) return ETH_ERR_TIMEOUT;
    }
    if (FLASH->NSSR & (FLASH_NSSR_WRPERR | FLASH_NSSR_PGSERR | FLASH_NSSR_STRBERR)) {
        FLASH->NSCCR |= (FLASH_NSCCR_CLR_WRPERR | FLASH_NSCCR_CLR_PGSERR
                       | FLASH_NSCCR_CLR_STRBERR | FLASH_NSCCR_CLR_EOP);
        return ETH_ERR_FLASH;
    }
    if (FLASH->NSSR & FLASH_NSSR_EOP) {
        FLASH->NSCCR |= FLASH_NSCCR_CLR_EOP;
    }
    return ETH_OK;
}

static ETH_Status_t flash_unlock(void)
{
    if ((FLASH->NSCR & FLASH_NSCR_LOCK) == 0U) return ETH_OK;

    FLASH->NSKEYR = IAP_FLASH_KEY1;
    FLASH->NSKEYR = IAP_FLASH_KEY2;

    return ((FLASH->NSCR & FLASH_NSCR_LOCK) == 0U) ? ETH_OK : ETH_ERR_FLASH;
}

static void flash_lock(void)
{
    FLASH->NSCR |= FLASH_NSCR_LOCK;
}

static ETH_Status_t flash_erase_sector(uint32_t sector)
{
    ETH_Status_t st = flash_wait_ready();
    if (st != ETH_OK) return st;

    FLASH->NSCR = (FLASH->NSCR & ~FLASH_NSCR_SNB_Msk)
                | (sector << FLASH_NSCR_SNB_Pos)
                | FLASH_NSCR_SER;
    FLASH->NSCR |= FLASH_NSCR_STRT;

    st = flash_wait_ready();
    FLASH->NSCR &= ~FLASH_NSCR_SER;
    return st;
}

static ETH_Status_t flash_program_quadword(uint32_t addr, const uint8_t qw[16])
{
    ETH_Status_t st = flash_wait_ready();
    if (st != ETH_OK) return st;

    /* qw, iap_qw_buf'tan geldigi icin zaten 4-bayt hizali. */
    const uint32_t *src = (const uint32_t *)(const void *)qw;
    volatile uint32_t *dst = (volatile uint32_t *)(uintptr_t)addr;

    FLASH->NSCR |= FLASH_NSCR_PG;
    __DMB();
    /* 128 bit tek islemde yazilmali; ara kesme girmemesi icin en kisa yoldan. */
    dst[0] = src[0];
    dst[1] = src[1];
    dst[2] = src[2];
    dst[3] = src[3];
    __DSB();

    st = flash_wait_ready();
    FLASH->NSCR &= ~FLASH_NSCR_PG;
    return st;
}

/* ===== Genel API ========================================================= */

ETH_Status_t ETH_IAP_Begin(uint32_t total_size, uint32_t expected_crc32)
{
    if (total_size == 0U || total_size > ETH_IAP_MAX_SIZE) return ETH_ERR_PARAM;

    iap_expected_size  = total_size;
    iap_expected_crc32 = expected_crc32;
    iap_received_bytes = 0U;
    iap_write_offset    = 0U;
    iap_running_crc32   = 0U;
    iap_qw_fill          = 0U;
    iap_active            = false;

    if (flash_unlock() != ETH_OK) return ETH_ERR_FLASH;

    uint32_t sectors     = (total_size + IAP_SECTOR_SIZE - 1U) / IAP_SECTOR_SIZE;
    uint32_t base_sector = (ETH_IAP_APP_BASE_ADDR - FLASH_BASE) / IAP_SECTOR_SIZE;

    for (uint32_t s = 0U; s < sectors; s++) {
        if (flash_erase_sector(base_sector + s) != ETH_OK) {
            flash_lock();
            return ETH_ERR_FLASH;
        }
    }

    iap_active = true;
    return ETH_OK;
}

ETH_Status_t ETH_IAP_WriteChunk(uint32_t seq, const uint8_t *data, uint16_t len)
{
    (void)seq;

    if (!iap_active || data == NULL || len == 0U) return ETH_ERR_PARAM;
    if ((uint32_t)len + iap_received_bytes > iap_expected_size) return ETH_ERR_PARAM;

    iap_running_crc32 = crc32_update(iap_running_crc32, data, len);
    iap_received_bytes += len;

    uint16_t i = 0U;
    while (i < len) {
        uint8_t space = (uint8_t)(IAP_QUADWORD_SIZE - iap_qw_fill);
        uint16_t take = (uint16_t)((space < (len - i)) ? space : (len - i));

        memcpy(&iap_qw_buf[iap_qw_fill], &data[i], take);
        iap_qw_fill = (uint8_t)(iap_qw_fill + take);
        i = (uint16_t)(i + take);

        if (iap_qw_fill == IAP_QUADWORD_SIZE) {
            uint32_t addr = ETH_IAP_APP_BASE_ADDR + iap_write_offset;
            if (flash_program_quadword(addr, iap_qw_buf) != ETH_OK) {
                iap_active = false;
                flash_lock();
                return ETH_ERR_FLASH;
            }
            iap_write_offset += IAP_QUADWORD_SIZE;
            iap_qw_fill = 0U;
        }
    }
    return ETH_OK;
}

ETH_Status_t ETH_IAP_Finish(void)
{
    if (!iap_active) return ETH_ERR_PARAM;

    /* Son eksik kalan quad-word'u 0xFF ile doldurup yaz (bos flash degeri). */
    if (iap_qw_fill > 0U) {
        memset(&iap_qw_buf[iap_qw_fill], 0xFF, (size_t)(IAP_QUADWORD_SIZE - iap_qw_fill));
        uint32_t addr = ETH_IAP_APP_BASE_ADDR + iap_write_offset;
        if (flash_program_quadword(addr, iap_qw_buf) != ETH_OK) {
            iap_active = false;
            flash_lock();
            return ETH_ERR_FLASH;
        }
        iap_write_offset += IAP_QUADWORD_SIZE;
        iap_qw_fill = 0U;
    }

    flash_lock();
    iap_active = false;

    if (iap_received_bytes != iap_expected_size) return ETH_ERR_PARAM;
    if (iap_running_crc32 != iap_expected_crc32)  return ETH_ERR_PARAM;

    return ETH_OK;
}

void ETH_IAP_JumpToApplication(void)
{
    typedef void (*app_reset_handler_t)(void);

    uint32_t app_msp           = *(volatile uint32_t *)ETH_IAP_APP_BASE_ADDR;
    uint32_t app_reset_vector  = *(volatile uint32_t *)(ETH_IAP_APP_BASE_ADDR + 4U);

    /* Devam eden Ethernet DMA'yi ve SysTick'i durdurmadan atlarsak, yeni
     * uygulama kendi baslatmasini yapmadan once cakisan kesme/DMA aktivitesi
     * HardFault'a yol acar. */
    ETH_Driver_DeInit();
    __disable_irq();
    SysTick->CTRL = 0U;

    /* Vektor tablosunu yeni uygulamaya tasi, ana yigin isaretcisini (MSP)
     * uygulamanin kendi degeriyle degistir, sonra Reset_Handler'a atla. */
    SCB->VTOR = ETH_IAP_APP_BASE_ADDR;
    __set_MSP(app_msp);

    app_reset_handler_t app_reset = (app_reset_handler_t)(uintptr_t)app_reset_vector;
    app_reset();

    /* Buraya asla ulasilmamali. */
    while (1) { }
}

#endif /* ETH_ENABLE_IAP */
