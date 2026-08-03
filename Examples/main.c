/**
  ******************************************************************************
  * @file    main.c
  * @brief   E-AETIS / Ethernet_BSP kullanim ornegi.
  *
  * Gelistiricinin yazdigi TEK kod budur. Kutuphanenin ic dosyalarina
  * hicbir sekilde dokunulmaz.
  ******************************************************************************
  */

#include "eth_app.h"     /* <-- BSP'den include edilen TEK baslik */

/* ===========================================================================
 * 1) ARAYUZE ACILACAK DEGISKENLER
 *
 * Iki yontem vardir:
 *   a) Dogrudan bellek  -> sensor degiskenleri icin (ptr)
 *   b) Fonksiyon        -> GPIO gibi yan etkisi olan seyler icin (getter/setter)
 * =========================================================================== */

/* --- (a) Sensor degeri: ana dongude guncellenen basit bir degisken --- */
static float g_temperature_c = 0.0f;
static float g_supply_voltage = 0.0f;
static uint32_t g_uptime_s = 0U;

/* --- (a2) I2C sensorden okunan deger: SHT3x ornegi (nem, %RH) ---
 * I2C okuma islemi tamamen kullanicinin donanimina ait; BSP I2C'ye
 * dokunmaz. Okunan deger asagidaki var_humidity ile arayuze acilir. */
#define SHT3X_I2C_ADDR      (0x44U << 1)   /* ADDR pini GND */
#define SHT3X_CMD_MEASURE_HI 0x2C
#define SHT3X_CMD_MEASURE_LO 0x06

extern I2C_HandleTypeDef hi2c1;   /* CubeMX tarafindan uretilir (i2c.c) */

static float g_humidity_rh = 0.0f;

static float ReadI2CHumiditySensor(void)
{
    uint8_t cmd[2]  = { SHT3X_CMD_MEASURE_HI, SHT3X_CMD_MEASURE_LO };
    uint8_t raw[6]  = { 0 };

    if (HAL_I2C_Master_Transmit(&hi2c1, SHT3X_I2C_ADDR, cmd, sizeof(cmd), 10) != HAL_OK) {
        return g_humidity_rh;   /* iletisim hatasi: son bilinen degeri koru */
    }

    HAL_Delay(15);  /* SHT3x olcum suresi (~15 ms, yuksek tekrarlanabilirlik) */

    if (HAL_I2C_Master_Receive(&hi2c1, SHT3X_I2C_ADDR, raw, sizeof(raw), 10) != HAL_OK) {
        return g_humidity_rh;
    }

    /* raw[3..4] = nem (CRC raw[5] burada kontrol edilmiyor, ornek amacli) */
    uint16_t raw_rh = ((uint16_t)raw[3] << 8) | raw[4];
    return 100.0f * ((float)raw_rh / 65535.0f);
}

/* --- (b) LED: yazma islemi GPIO'ya dokunmali, o yuzden fonksiyon --- */
static float led_get(void)
{
    return (LED_GPIO_Port->ODR & LED_Pin) ? 1.0f : 0.0f;
}

static void led_set(float v)
{
    if (v >= 0.5f) LED_GPIO_Port->BSRR = LED_Pin;
    else           LED_GPIO_Port->BSRR = (uint32_t)LED_Pin << 16;
}

/* --- Degisken tanimlari: OMRU BOYUNCA yasamali -> static const --- */
static const ETH_Var_t var_temp = {
    .name = "sicaklik", .unit = "C", .type = ETH_VAR_F32,
    .writable = false,  .ptr = &g_temperature_c
};

static const ETH_Var_t var_vbat = {
    .name = "besleme", .unit = "V", .type = ETH_VAR_F32,
    .writable = false, .ptr = &g_supply_voltage
};

static const ETH_Var_t var_uptime = {
    .name = "calisma_suresi", .unit = "s", .type = ETH_VAR_U32,
    .writable = false, .ptr = &g_uptime_s
};

static const ETH_Var_t var_humidity = {
    .name = "nem", .unit = "%RH", .type = ETH_VAR_F32,
    .writable = false, .ptr = &g_humidity_rh
};

static const ETH_Var_t var_led = {
    .name = "led", .unit = NULL, .type = ETH_VAR_U8,
    .writable = true, .ptr = NULL,
    .getter = led_get, .setter = led_set
};

/* ===========================================================================
 * 2) ANA PROGRAM
 * =========================================================================== */

int main(void)
{
    HAL_Init();
    SystemClock_Config();     /* 50 MHz RMII referans saati aktif olmali! */
    MX_GPIO_Init();
    MX_ADC1_Init();           /* Sicaklik/besleme olcumu icin (ornek) */
    MX_I2C1_Init();           /* SHT3x nem sensoru icin (ornek) */

    ETH_Status_t st = ETH_BSP_Init();

    if (st != ETH_OK) {
        /* Hata kodu dogrudan nedeni soyler:
         *   ETH_ERR_TIMEOUT   -> 50 MHz RMII referans saati gelmiyor
         *   ETH_ERR_PHY       -> PHY_ADDRESS yanlis (ScanAddress deneyin)
         *   ETH_ERR_LINK_DOWN -> kablo takili degil
         */
        uint8_t found;
        if (st == ETH_ERR_PHY && ETH_PHY_ScanAddress(&found) == ETH_OK) {
            /* found degerini eth_config.h'deki PHY_ADDRESS yapin. */
        }
        while (1) { }
    }

    /* --- Degiskenleri arayuze ac --- */
    (void)ETH_BSP_RegisterVar(&var_temp);
    (void)ETH_BSP_RegisterVar(&var_vbat);
    (void)ETH_BSP_RegisterVar(&var_uptime);
    (void)ETH_BSP_RegisterVar(&var_led);
    (void)ETH_BSP_RegisterVar(&var_humidity);

    uint32_t last_sample = 0U;

    while (1)
    {
        /* Gelen paketleri isle. Bloklamaz, isledigi paket sayisini doner. */
        (void)ETH_BSP_ProcessEvents();

        /* --- Kullanicinin kendi uygulama kodu --- */
        uint32_t now = HAL_GetTick();
        if ((now - last_sample) >= 100U) {
            last_sample = now;

            /* Sensor degerlerini guncelle. Arayuz bunlari otomatik okur;
             * ayrica bir sey gondermeye gerek yok. */
            g_temperature_c  = ReadTemperatureSensor();
            g_supply_voltage = ReadSupplyVoltage();
            g_uptime_s       = now / 1000U;
            g_humidity_rh    = ReadI2CHumiditySensor();   /* I2C -> arayuz */
        }
    }
}
