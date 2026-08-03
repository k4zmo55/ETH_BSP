/**
  ******************************************************************************
  * @file    eth_app.h
  * @brief   E-AETIS / Ethernet_BSP - KULLANICI API'SI
  *
  * Uygulama gelistiricisinin main.c icinde include ettigi TEK basliktir.
  ******************************************************************************
  */
#ifndef ETH_APP_H
#define ETH_APP_H

#include "eth_driver.h"
#include <stdint.h>
#include <stdbool.h>

/* ===== Baslatma ======================================================= */

/** @brief BSP'yi baslat. Ayarlari eth_config.h'den ceker.
 *  @retval ETH_OK, ETH_ERR_TIMEOUT (RMII saati yok?),
 *          ETH_ERR_PHY (PHY_ADDRESS yanlis?), ETH_ERR_LINK_DOWN (kablo?) */
ETH_Status_t ETH_BSP_Init(void);

/** @brief ANA DONGUDE SUREKLI CAGRILMALI.
 *  Gelen paketleri isler, ARP/ICMP/UDP yanitlarini basar,
 *  E-AETIS komutlarini cevaplar. Bloklamaz.
 *  @retval Bu cagride islenen paket sayisi. */
uint32_t ETH_BSP_ProcessEvents(void);

/* ===== Gonderme ======================================================= */

/** @brief Hedefe UDP datagram gonder. ARP cozumu otomatik yapilir.
 *  @note  MAC adresi cache'de yoksa ARP request basar ve
 *         ETH_ERR_NO_DATA doner; birkac ms sonra tekrar deneyin. */
ETH_Status_t ETH_BSP_SendUDP(const uint8_t dst_ip[4], uint16_t dst_port,
                             uint16_t src_port, const void *data, uint16_t len);

/** @brief Son gelen UDP paketinin kaynagina yanit gonder. */
ETH_Status_t ETH_BSP_ReplyUDP(const void *data, uint16_t len);

/* ===== Kullanici geri cagirmasi ======================================= */

/** @brief Kendi UDP portunuza gelen veriyi almak icin kaydolun.
 *  E-AETIS ve IAP portlari BSP tarafindan islenir, callback'e dusmez. */
typedef void (*ETH_UDP_Callback_t)(const uint8_t src_ip[4], uint16_t src_port,
                                   const uint8_t *data, uint16_t len);
void ETH_BSP_RegisterUDPCallback(uint16_t listen_port, ETH_UDP_Callback_t cb);

/* ===== Kullanici komut genisletmesi ====================================
 * E-AETIS arayuzunden gelen ve BSP'nin tanimadigi her komut buraya duser.
 * Kendi donaniminizi (LED, sensor, role...) boylece test edebilirsiniz.
 * BSP sizin donaniminizi bilmez; sadece komutu iletir.
 *
 * Ornek: GUI "LED|ID:1|SET:1" gonderirse handler'a
 *        cmd = "LED", args = "ID:1|SET:1" gelir.
 *
 * Tampon boyutlari: eth_config.h -> ETH_USER_*_MAX_LEN
 *
 * @return Yazilan yanit uzunlugu (>0) veya 0 = "bu komut bana ait degil".
 */
typedef int (*ETH_UserCmdHandler_t)(const char *cmd, const char *args,
                                    char *resp, uint16_t resp_size);

void ETH_BSP_RegisterCommandHandler(ETH_UserCmdHandler_t handler);

/* ===== Push telemetri (karttan arayuze kendiliginden veri) =============
 * Arayuz "TELEMETRY_SUB|PORT:n" gonderdiginde kart, o arayuzun IP'sini ve
 * portunu kaydeder. Sonrasinda ana dongunuzden istediginiz zaman veri
 * basabilirsiniz - istek beklemeden.
 *
 * Bu, asagidaki ETH_BSP_RegisterVar mekanizmasinin ALTERNATIFIDIR:
 *   - RegisterVar : arayuz sorar, kart cevaplar (pull). Sabit periyot.
 *   - SendTelemetry: kart kendi karar verir (push). Olay tabanli veri icin.
 * Ikisi ayni anda kullanilabilir.
 *
 * Format serbest, ancak arayuz "ANAHTAR:DEGER|..." bicimini otomatik
 * ayristirip grafige dokuyor. Ornek:
 *     ETH_BSP_SendTelemetry("TEMP:36.5|VBAT:3.72|UPTIME:120");
 */
ETH_Status_t ETH_BSP_SendTelemetry(const char *text);

/** @brief Bir arayuz abone oldu mu? Abone yoksa gondermeye calismayin. */
bool ETH_BSP_TelemetryReady(void);

/* ===== Telemetri: kendi degiskenlerinizi arayuze acin ==================
 *
 * Karttaki bir sensor degerini arayuzde gormek veya arayuzden bir LED/role
 * kontrol etmek icin kullanilir. BSP sizin donaniminizi BILMEZ; sadece
 * tarif ettiginiz degiskeni okur/yazar.
 *
 * Cekirdek dosyalara dokunmadan, main.c icinde:
 *
 *     static float g_temp = 0.0f;
 *
 *     static const ETH_Var_t var_temp = {
 *         .name = "sicaklik", .unit = "C", .type = ETH_VAR_F32,
 *         .writable = false,  .ptr = &g_temp
 *     };
 *
 *     ETH_BSP_RegisterVar(&var_temp);
 *
 * Arayuz GET_VARS komutuyla listeyi otomatik kesfeder; yeni bir degisken
 * eklemek GUI'de veya protokolde hicbir degisiklik gerektirmez.
 * ====================================================================== */

typedef enum {
    ETH_VAR_U8  = 0,
    ETH_VAR_I32 = 1,
    ETH_VAR_U32 = 2,
    ETH_VAR_F32 = 3
} ETH_VarType_t;

/**
 * @brief Arayuzden okunabilen / yazilabilen bir degisken tanimi.
 *
 * Iki kullanim bicimi vardir:
 *   1) Dogrudan bellek erisimi -> `ptr` doldurulur (sensor degiskeni gibi)
 *   2) Fonksiyon uzerinden     -> `getter`/`setter` doldurulur (GPIO gibi)
 *
 * Yapi OMRU BOYUNCA gecerli kalmalidir: `static const` olarak tanimlayin.
 * BSP yapiyi kopyalamaz, isaretcisini saklar.
 */
typedef struct {
    const char   *name;       /* Arayuzde gorunen ad. '|', ':' ve bosluk YASAK */
    const char   *unit;       /* "C", "V", "rpm"... NULL olabilir              */
    ETH_VarType_t type;
    bool          writable;   /* true ise arayuzden yazilabilir                */
    void         *ptr;        /* NULL ise getter/setter kullanilir             */
    float       (*getter)(void);
    void        (*setter)(float value);
} ETH_Var_t;

/**
 * @brief Degiskeni arayuze ac. ETH_BSP_Init() oncesi veya sonrasi cagrilabilir.
 * @retval ETH_OK
 * @retval ETH_ERR_PARAM  gecersiz tanim, ayni ad zaten kayitli veya tablo dolu
 *                        (tablo boyutu: eth_config.h -> ETH_MAX_VARIABLES)
 */
ETH_Status_t ETH_BSP_RegisterVar(const ETH_Var_t *var);

/** @brief Kayitli degisken sayisi. */
uint32_t ETH_BSP_GetVarCount(void);

/* ===== Durum ========================================================== */
ETH_Status_t ETH_BSP_GetLinkState(ETH_LinkState_t *state);
void         ETH_BSP_GetStats(ETH_Stats_t *stats);

/** @brief Kendi IP adresimizi oku (4 bayt). */
void ETH_BSP_GetIPAddress(uint8_t ip[4]);

#endif /* ETH_APP_H */
