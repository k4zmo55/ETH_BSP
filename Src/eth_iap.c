/**
  ******************************************************************************
  * @file    eth_app.c
  * @brief   Uygulama cekirdegi: ARP / ICMP / UDP ayrıstirma, E-AETIS komutlari.
  *
  * TASARIM ILKESI: Bu dosyadaki her parser fonksiyonu, girdinin TAMAMEN
  * dusmanca oldugunu varsayar. E-AETIS fuzzing testi tam olarak burayi
  * hedefliyor. Uzunluk kontrolu yapilmadan tek bir bayt bile okunmaz.
  ******************************************************************************
  */

#include "eth_app.h"
#include "eth_driver.h"
#include "eth_phy.h"
#include "eth_iap.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* ===== Protokol sabitleri ============================================== */

#define ETH_HDR_LEN         14U
#define ETHERTYPE_IPV4      0x0800U
#define ETHERTYPE_ARP       0x0806U

#define ARP_HTYPE_ETH       0x0001U
#define ARP_OP_REQUEST      0x0001U
#define ARP_OP_REPLY        0x0002U
#define ARP_PACKET_LEN      28U

#define IP_PROTO_ICMP       1U
#define IP_PROTO_UDP        17U
#define IP_MIN_HDR_LEN      20U
#define IP_FLAG_MF          0x2000U
#define IP_FRAG_OFF_MASK    0x1FFFU

#define ICMP_ECHO_REQUEST   8U
#define ICMP_ECHO_REPLY     0U
#define UDP_HDR_LEN         8U

/* ===== Modul durumu ==================================================== */

static const uint8_t my_mac[6] = { ETH_MAC_ADDR0, ETH_MAC_ADDR1, ETH_MAC_ADDR2,
                                   ETH_MAC_ADDR3, ETH_MAC_ADDR4, ETH_MAC_ADDR5 };
static const uint8_t my_ip[4]  = { ETH_IP_ADDR0, ETH_IP_ADDR1,
                                   ETH_IP_ADDR2, ETH_IP_ADDR3 };
static const uint8_t bcast_mac[6] = { 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF };

typedef struct {
    uint8_t  ip[4];
    uint8_t  mac[6];
    uint32_t last_seen;
    bool     valid;
} arp_entry_t;

static arp_entry_t arp_cache[ETH_ARP_CACHE_SIZE];

/* Son gelen UDP paketinin kaynagi - ETH_BSP_ReplyUDP icin */
static struct {
    uint8_t  src_mac[6];
    uint8_t  src_ip[4];
    uint16_t src_port;
    uint16_t dst_port;
    bool     valid;
} last_udp;

static uint16_t           user_port;
static ETH_UDP_Callback_t user_cb;

#if ETH_ENABLE_USER_CMD
static ETH_UserCmdHandler_t user_cmd_handler;

/* Telemetri abonesi: "TELEMETRY_SUB" gonderen arayuzun adresi. */
static uint8_t  telem_ip[4];
static uint16_t telem_port;
static bool     telem_valid;
#endif

static uint16_t ip_ident_counter = 1U;

/* ===== Bayt sirasi yardimcilari ======================================== */
/* DMA buffer'i 4-bayt hizali olsa da IP basligi icindeki 16/32-bit alanlar
 * hizali olmayabilir. Her zaman bayt bayt okuyoruz. */

static inline uint16_t rd16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] << 8 | p[1]);
}
static inline uint32_t rd32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
         | ((uint32_t)p[2] << 8)  |  (uint32_t)p[3];
}
static inline void wr16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v;
}

/* ===== Internet checksum (RFC 1071) ==================================== */

static uint16_t inet_checksum(const uint8_t *data, uint16_t len, uint32_t seed)
{
    uint32_t sum = seed;
    uint16_t i;

    for (i = 0U; (uint16_t)(i + 1U) < len; i += 2U) {
        sum += ((uint32_t)data[i] << 8) | data[i + 1U];
    }
    if (i < len) {                       /* Tek bayt kaldiysa */
        sum += (uint32_t)data[i] << 8;
    }
    while (sum >> 16) {
        sum = (sum & 0xFFFFU) + (sum >> 16);
    }
    return (uint16_t)(~sum);
}

/* ===== ARP cache ======================================================= */

static void arp_cache_put(const uint8_t ip[4], const uint8_t mac[6])
{
    uint32_t oldest_idx = 0U;
    uint32_t oldest_t   = 0xFFFFFFFFUL;

    for (uint32_t i = 0U; i < ETH_ARP_CACHE_SIZE; i++) {
        if (arp_cache[i].valid && memcmp(arp_cache[i].ip, ip, 4) == 0) {
            memcpy(arp_cache[i].mac, mac, 6);
            arp_cache[i].last_seen = ETH_GetTick();
            return;
        }
        if (!arp_cache[i].valid) { oldest_idx = i; oldest_t = 0U; }
        else if (arp_cache[i].last_seen < oldest_t) {
            oldest_t = arp_cache[i].last_seen; oldest_idx = i;
        }
    }
    memcpy(arp_cache[oldest_idx].ip,  ip,  4);
    memcpy(arp_cache[oldest_idx].mac, mac, 6);
    arp_cache[oldest_idx].last_seen = ETH_GetTick();
    arp_cache[oldest_idx].valid = true;
}

static bool arp_cache_get(const uint8_t ip[4], uint8_t mac[6])
{
    for (uint32_t i = 0U; i < ETH_ARP_CACHE_SIZE; i++) {
        if (arp_cache[i].valid && memcmp(arp_cache[i].ip, ip, 4) == 0) {
            memcpy(mac, arp_cache[i].mac, 6);
            return true;
        }
    }
    return false;
}

/* ===== Frame olusturma yardimcilari ==================================== */

static uint16_t build_eth_header(uint8_t *buf, const uint8_t dst_mac[6],
                                 uint16_t ethertype)
{
    memcpy(&buf[0], dst_mac, 6);
    memcpy(&buf[6], my_mac,  6);
    wr16(&buf[12], ethertype);
    return ETH_HDR_LEN;
}

/**
 * @brief IPv4 basligi yaz. Checksum'i da hesaplar.
 * @return Baslik uzunlugu (20)
 */
static uint16_t build_ip_header(uint8_t *ip, const uint8_t dst_ip[4],
                                uint8_t proto, uint16_t payload_len)
{
    memset(ip, 0, IP_MIN_HDR_LEN);
    ip[0] = 0x45U;                                   /* v4, IHL=5 */
    ip[1] = 0x00U;                                   /* DSCP/ECN  */
    wr16(&ip[2], (uint16_t)(IP_MIN_HDR_LEN + payload_len));
    wr16(&ip[4], ip_ident_counter++);
    wr16(&ip[6], 0x4000U);                           /* Don't Fragment */
    ip[8]  = 64U;                                    /* TTL */
    ip[9]  = proto;
    /* [10..11] checksum - once sifir kalir */
    memcpy(&ip[12], my_ip,  4);
    memcpy(&ip[16], dst_ip, 4);

    uint16_t csum = inet_checksum(ip, IP_MIN_HDR_LEN, 0U);
    wr16(&ip[10], csum);
    return IP_MIN_HDR_LEN;
}

/* ===== ARP ============================================================= */

#if ETH_ENABLE_ARP

static void arp_send_request(const uint8_t target_ip[4])
{
    uint8_t *buf;
    if (ETH_ClaimTxBuffer(&buf) != ETH_OK) return;

    uint16_t o = build_eth_header(buf, bcast_mac, ETHERTYPE_ARP);
    uint8_t *a = &buf[o];

    wr16(&a[0], ARP_HTYPE_ETH);
    wr16(&a[2], ETHERTYPE_IPV4);
    a[4] = 6U; a[5] = 4U;
    wr16(&a[6], ARP_OP_REQUEST);
    memcpy(&a[8],  my_mac, 6);
    memcpy(&a[14], my_ip,  4);
    memset(&a[18], 0, 6);                 /* Hedef MAC bilinmiyor */
    memcpy(&a[24], target_ip, 4);

    (void)ETH_CommitTxBuffer((uint16_t)(o + ARP_PACKET_LEN));
}

static void arp_handle(const uint8_t *frame, uint16_t len)
{
    if (len < (uint16_t)(ETH_HDR_LEN + ARP_PACKET_LEN)) return;

    const uint8_t *a = &frame[ETH_HDR_LEN];

    if (rd16(&a[0]) != ARP_HTYPE_ETH)   return;
    if (rd16(&a[2]) != ETHERTYPE_IPV4)  return;
    if (a[4] != 6U || a[5] != 4U)       return;

    uint16_t op = rd16(&a[6]);

    /* Gonderenin bilgisini her durumda cache'e al. */
    arp_cache_put(&a[14], &a[8]);

    if (op != ARP_OP_REQUEST) return;
    if (memcmp(&a[24], my_ip, 4) != 0) return;    /* Bize sorulmamis */

    uint8_t *buf;
    if (ETH_ClaimTxBuffer(&buf) != ETH_OK) return;

    uint16_t o = build_eth_header(buf, &a[8], ETHERTYPE_ARP);
    uint8_t *r = &buf[o];

    wr16(&r[0], ARP_HTYPE_ETH);
    wr16(&r[2], ETHERTYPE_IPV4);
    r[4] = 6U; r[5] = 4U;
    wr16(&r[6], ARP_OP_REPLY);
    memcpy(&r[8],  my_mac, 6);
    memcpy(&r[14], my_ip,  4);
    memcpy(&r[18], &a[8],  6);
    memcpy(&r[24], &a[14], 4);

    (void)ETH_CommitTxBuffer((uint16_t)(o + ARP_PACKET_LEN));
}

#endif /* ETH_ENABLE_ARP */

/* ===== ICMP ============================================================ */

#if ETH_ENABLE_ICMP

static void icmp_handle(const uint8_t *frame, const uint8_t *ip_hdr,
                        uint16_t ip_hdr_len, uint16_t payload_len)
{
    const uint8_t *icmp = &ip_hdr[ip_hdr_len];

    if (payload_len < 8U) return;
    if (icmp[0] != ICMP_ECHO_REQUEST) return;

    /* Yanit, gelen payload'i aynen geri gonderir. Buffer'a sigmali. */
    uint16_t total = (uint16_t)(ETH_HDR_LEN + IP_MIN_HDR_LEN + payload_len);
    if (total > ETH_BUFFER_SIZE) return;

    uint8_t *buf;
    if (ETH_ClaimTxBuffer(&buf) != ETH_OK) return;

    uint16_t o = build_eth_header(buf, &frame[6], ETHERTYPE_IPV4);
    o += build_ip_header(&buf[o], &ip_hdr[12], IP_PROTO_ICMP, payload_len);

    memcpy(&buf[o], icmp, payload_len);
    buf[o + 0U] = ICMP_ECHO_REPLY;
    buf[o + 1U] = 0U;
    buf[o + 2U] = 0U;                    /* Checksum sifirlanip yeniden hesaplanir */
    buf[o + 3U] = 0U;
    wr16(&buf[o + 2U], inet_checksum(&buf[o], payload_len, 0U));

    (void)ETH_CommitTxBuffer((uint16_t)(o + payload_len));
}

#endif /* ETH_ENABLE_ICMP */

/* ===== UDP gonderme ==================================================== */

#if ETH_ENABLE_UDP

static ETH_Status_t udp_send_to_mac(const uint8_t dst_mac[6], const uint8_t dst_ip[4],
                                    uint16_t dst_port, uint16_t src_port,
                                    const void *data, uint16_t len)
{
    uint16_t udp_len = (uint16_t)(UDP_HDR_LEN + len);
    uint16_t total   = (uint16_t)(ETH_HDR_LEN + IP_MIN_HDR_LEN + udp_len);

    if (total > ETH_BUFFER_SIZE) return ETH_ERR_TOO_LARGE;

    uint8_t *buf;
    ETH_Status_t st = ETH_ClaimTxBuffer(&buf);
    if (st != ETH_OK) return st;

    uint16_t o = build_eth_header(buf, dst_mac, ETHERTYPE_IPV4);
    uint8_t *ip = &buf[o];
    o += build_ip_header(ip, dst_ip, IP_PROTO_UDP, udp_len);

    uint8_t *udp = &buf[o];
    wr16(&udp[0], src_port);
    wr16(&udp[2], dst_port);
    wr16(&udp[4], udp_len);
    wr16(&udp[6], 0U);                   /* Checksum: IPv4'te opsiyonel */

    if (len > 0U && data != NULL) {
        memcpy(&udp[UDP_HDR_LEN], data, len);
    }

    return ETH_CommitTxBuffer((uint16_t)(o + udp_len));
}

ETH_Status_t ETH_BSP_SendUDP(const uint8_t dst_ip[4], uint16_t dst_port,
                             uint16_t src_port, const void *data, uint16_t len)
{
    uint8_t dst_mac[6];

    if (dst_ip == NULL) return ETH_ERR_PARAM;

    /* Broadcast IP -> broadcast MAC, ARP gerekmez. */
    if (dst_ip[0] == 255U && dst_ip[1] == 255U &&
        dst_ip[2] == 255U && dst_ip[3] == 255U) {
        memcpy(dst_mac, bcast_mac, 6);
    } else if (!arp_cache_get(dst_ip, dst_mac)) {
#if ETH_ENABLE_ARP
        arp_send_request(dst_ip);
#endif
        return ETH_ERR_NO_DATA;          /* Cozum bekleniyor, tekrar deneyin */
    }

    return udp_send_to_mac(dst_mac, dst_ip, dst_port, src_port, data, len);
}

ETH_Status_t ETH_BSP_ReplyUDP(const void *data, uint16_t len)
{
    if (!last_udp.valid) return ETH_ERR_PARAM;

    return udp_send_to_mac(last_udp.src_mac, last_udp.src_ip,
                           last_udp.src_port, last_udp.dst_port, data, len);
}

#endif /* ETH_ENABLE_UDP */

/* ===== E-AETIS komut isleyici ========================================== */

#if ETH_ENABLE_EAETIS_CMD



/* ==========================================================================
 * TELEMETRI KAYIT DEFTERI
 *
 * Kullanici kendi degiskenlerini main.c'den kaydeder; bu dosyaya asla
 * dokunmaz. Arayuz GET_VARS ile listeyi kesfeder ve tabloyu kendisi kurar.
 * ========================================================================== */

#if ETH_ENABLE_TELEMETRY

static const ETH_Var_t *var_table[ETH_MAX_VARIABLES];
static uint32_t         var_count;

ETH_Status_t ETH_BSP_RegisterVar(const ETH_Var_t *var)
{
    if (var == NULL || var->name == NULL)          return ETH_ERR_PARAM;
    if (var_count >= ETH_MAX_VARIABLES)            return ETH_ERR_PARAM;
    if (var->ptr == NULL && var->getter == NULL)   return ETH_ERR_PARAM;
    if (var->writable && var->ptr == NULL && var->setter == NULL) return ETH_ERR_PARAM;

    /* Ad protokol ayiricilarini icermemeli, yoksa yanit ayristirilamaz. */
    for (const char *c = var->name; *c != '\0'; c++) {
        if (*c == '|' || *c == ':' || *c == ' ') return ETH_ERR_PARAM;
    }

    /* Ayni ad iki kez kaydedilemez. */
    for (uint32_t i = 0U; i < var_count; i++) {
        if (strcmp(var_table[i]->name, var->name) == 0) return ETH_ERR_PARAM;
    }

    var_table[var_count++] = var;
    return ETH_OK;
}

uint32_t ETH_BSP_GetVarCount(void) { return var_count; }

static const char *var_type_name(ETH_VarType_t t)
{
    switch (t) {
        case ETH_VAR_U8:  return "u8";
        case ETH_VAR_I32: return "i32";
        case ETH_VAR_U32: return "u32";
        case ETH_VAR_F32: return "f32";
        default:          return "?";
    }
}

static float var_get(const ETH_Var_t *v)
{
    if (v->getter != NULL) return v->getter();
    if (v->ptr    == NULL) return 0.0f;

    switch (v->type) {
        case ETH_VAR_U8:  return (float)(*(volatile uint8_t  *)v->ptr);
        case ETH_VAR_I32: return (float)(*(volatile int32_t  *)v->ptr);
        case ETH_VAR_U32: return (float)(*(volatile uint32_t *)v->ptr);
        case ETH_VAR_F32: return          *(volatile float    *)v->ptr;
        default:          return 0.0f;
    }
}

static void var_set(const ETH_Var_t *v, float value)
{
    if (v->setter != NULL) { v->setter(value); return; }
    if (v->ptr    == NULL) return;

    switch (v->type) {
        case ETH_VAR_U8:  *(volatile uint8_t  *)v->ptr = (uint8_t)value;  break;
        case ETH_VAR_I32: *(volatile int32_t  *)v->ptr = (int32_t)value;  break;
        case ETH_VAR_U32: *(volatile uint32_t *)v->ptr = (uint32_t)value; break;
        case ETH_VAR_F32: *(volatile float    *)v->ptr = value;           break;
        default: break;
    }
}

/**
 * @brief Float'i 3 ondalikli metne cevir.
 * @note  snprintf("%f") newlib'de float printf destegi ister
 *        (-u _printf_float, ~8-10 KB flash). Gomulu tarafta bunu odemek
 *        gereksiz; sabit noktali bicimlendirme yapiyoruz.
 */
static int var_fmt(char *out, int cap, float v)
{
    bool neg = false;

    if (v != v) return snprintf(out, cap, "nan");        /* NaN kontrolu */
    if (v < 0.0f) { neg = true; v = -v; }
    if (v > 2000000.0f) v = 2000000.0f;                  /* tasma korumasi */

    uint32_t scaled = (uint32_t)((v * 1000.0f) + 0.5f);
    return snprintf(out, cap, "%s%lu.%03lu", neg ? "-" : "",
                    (unsigned long)(scaled / 1000U),
                    (unsigned long)(scaled % 1000U));
}

/** @brief "ANAHTAR:" sonrasindaki metni '|' veya sona kadar kopyala. */
static bool eaetis_parse_str(const uint8_t *d, uint16_t len, const char *key,
                             char *out, uint16_t cap)
{
    uint16_t klen = (uint16_t)strlen(key);
    if (len < klen || cap == 0U) return false;

    for (uint16_t i = 0U; (uint16_t)(i + klen) <= len; i++) {
        if (memcmp(&d[i], key, klen) != 0) continue;

        uint16_t j = (uint16_t)(i + klen), o = 0U;
        while (j < len && d[j] != '|' && o < (uint16_t)(cap - 1U)) {
            out[o++] = (char)d[j++];
        }
        out[o] = '\0';
        return o > 0U;
    }
    return false;
}

/** @brief "ANAHTAR:" sonrasindaki ondalikli sayiyi oku (strtof kullanmadan). */
static bool eaetis_parse_float(const uint8_t *d, uint16_t len,
                               const char *key, float *out)
{
    char buf[32];
    if (!eaetis_parse_str(d, len, key, buf, sizeof(buf))) return false;

    const char *p = buf;
    bool neg = false;
    if (*p == '-') { neg = true; p++; }
    else if (*p == '+') { p++; }

    float v = 0.0f;
    bool any = false;
    while (*p >= '0' && *p <= '9') { v = v * 10.0f + (float)(*p - '0'); p++; any = true; }

    if (*p == '.') {
        p++;
        float scale = 0.1f;
        while (*p >= '0' && *p <= '9') {
            v += (float)(*p - '0') * scale;
            scale *= 0.1f;
            p++; any = true;
        }
    }
    if (!any) return false;

    *out = neg ? -v : v;
    return true;
}

static const ETH_Var_t *var_find(const char *name)
{
    for (uint32_t i = 0U; i < var_count; i++) {
        if (strcmp(var_table[i]->name, name) == 0) return var_table[i];
    }
    return NULL;
}

#endif /* ETH_ENABLE_TELEMETRY */

/** @brief "ANAHTAR:" sonrasindaki sayiyi oku. Sinir disina TASMAZ.
 *  @param base 0 = otomatik (0x oneki hex demek), 10 = ondalik */
static bool eaetis_parse_uint(const uint8_t *d, uint16_t len,
                              const char *key, int base, uint32_t *out)
{
    uint16_t klen = (uint16_t)strlen(key);
    if (len < klen) return false;

    for (uint16_t i = 0U; (uint16_t)(i + klen) <= len; i++) {
        if (memcmp(&d[i], key, klen) != 0) continue;

        uint16_t j = (uint16_t)(i + klen);
        uint32_t v = 0U;
        bool hex = false, any = false;

        if ((base == 0 || base == 16) && (uint16_t)(j + 1U) < len &&
            d[j] == '0' && (d[j + 1U] == 'x' || d[j + 1U] == 'X')) {
            hex = true; j += 2U;
        } else if (base == 16) {
            hex = true;
        }

        for (; j < len; j++) {
            uint8_t c = d[j];
            uint32_t dig;
            if      (c >= '0' && c <= '9') dig = (uint32_t)(c - '0');
            else if (hex && c >= 'a' && c <= 'f') dig = (uint32_t)(c - 'a' + 10);
            else if (hex && c >= 'A' && c <= 'F') dig = (uint32_t)(c - 'A' + 10);
            else break;
            v = v * (hex ? 16U : 10U) + dig;
            any = true;
        }
        if (any) { *out = v; return true; }
    }
    return false;
}

/** GUI'nin bekledigi format: BASLIK|ANAHTAR:DEGER|ANAHTAR:DEGER... */
static void eaetis_send_stats(void)
{
    char out[320];
    ETH_LinkState_t link;
    ETH_Stats_t     st;

    (void)ETH_GetLinkState(&link);
    ETH_GetStats(&st);

    int n = snprintf(out, sizeof(out),
        "PHY_STATS|BCR:0x%04X|BSR:0x%04X|LINK:%s|SPEED:%u Mbps|DUPLEX:%s"
        "|DMA_RX_ERR:%lu|DMA_TX_ERR:%lu",
        link.bcr, link.bsr,
        link.link_up ? "UP" : "DOWN",
        (unsigned)link.speed_mbps,
        link.full_duplex ? "Full" : "Half",
        (unsigned long)(st.rx_missed_hw + st.rx_dropped),
        (unsigned long)st.tx_no_desc);

    if (n > 0) {
        (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
    }
}

/** @return true = paket islendi, kullanici callback'ine dusmesin */
static bool eaetis_handle(const uint8_t *data, uint16_t len)
{
    /* --- Discovery --- */
    if (len >= 18U && memcmp(data, "DISCOVER_STM32_REQ", 18) == 0) {
        char out[64];
        int n = snprintf(out, sizeof(out), "STM32_ACK|DEV:%s|PHY:%s",
                         ETH_DEVICE_NAME, ETH_PHY_GetName());
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- PHY / DMA teshis --- */
    if (len >= 17U && memcmp(data, "GET_PHY_DMA_STATS", 17) == 0) {
        eaetis_send_stats();
        return true;
    }

    /* --- Benchmark: echo --- */
    if (len >= 10U && memcmp(data, "PERF_TEST_", 10) == 0) {
        (void)ETH_BSP_ReplyUDP(data, len);
        return true;
    }


    /* --- Tam istatistik dokumu --- */
    if (len >= 9U && memcmp(data, "GET_STATS", 9) == 0) {
        char out[288];
        ETH_Stats_t st;
        ETH_GetStats(&st);
        int n = snprintf(out, sizeof(out),
            "STATS|RX_FRAMES:%lu|TX_FRAMES:%lu|RX_BYTES:%lu|TX_BYTES:%lu"
            "|RX_DROP:%lu|RX_MISS:%lu|CRC_ERR:%lu|TX_NODESC:%lu|DMA_ERR:%lu",
            (unsigned long)st.rx_frames,  (unsigned long)st.tx_frames,
            (unsigned long)st.rx_bytes,   (unsigned long)st.tx_bytes,
            (unsigned long)st.rx_dropped, (unsigned long)st.rx_missed_hw,
            (unsigned long)st.rx_crc_errors, (unsigned long)st.tx_no_desc,
            (unsigned long)st.dma_errors);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    if (len >= 11U && memcmp(data, "RESET_STATS", 11) == 0) {
        ETH_ResetStats();
        (void)ETH_BSP_ReplyUDP("STATS_RESET", 11U);
        return true;
    }

    /* --- Ham PHY register erisimi: PHY_READ|REG:n --- */
    if (len >= 8U && memcmp(data, "PHY_READ", 8) == 0) {
        uint32_t reg = 0U;
        char out[64];
        if (!eaetis_parse_uint(data, len, "REG:", 10, &reg) || reg > 31U) {
            (void)ETH_BSP_ReplyUDP("ERR|BAD_REG", 11U);
            return true;
        }
        uint16_t val = 0U;
        if (ETH_PHY_Read(PHY_ADDRESS, (uint8_t)reg, &val) != ETH_OK) {
            (void)ETH_BSP_ReplyUDP("ERR|SMI_TIMEOUT", 15U);
            return true;
        }
        int n = snprintf(out, sizeof(out), "PHY_REG|REG:%lu|VAL:0x%04X",
                         (unsigned long)reg, val);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- PHY_WRITE|REG:n|VAL:0xXXXX --- */
    if (len >= 9U && memcmp(data, "PHY_WRITE", 9) == 0) {
        uint32_t reg = 0U, val = 0U;
        char out[64];
        if (!eaetis_parse_uint(data, len, "REG:", 10, &reg) ||
            !eaetis_parse_uint(data, len, "VAL:", 0,  &val) ||
            reg > 31U || val > 0xFFFFU) {
            (void)ETH_BSP_ReplyUDP("ERR|BAD_ARGS", 12U);
            return true;
        }
        if (ETH_PHY_Write(PHY_ADDRESS, (uint8_t)reg, (uint16_t)val) != ETH_OK) {
            (void)ETH_BSP_ReplyUDP("ERR|SMI_TIMEOUT", 15U);
            return true;
        }
        int n = snprintf(out, sizeof(out), "PHY_WOK|REG:%lu", (unsigned long)reg);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- SMI adres taramasi: yanlis PHY_ADDRESS'i teshis eder --- */
    if (len >= 8U && memcmp(data, "PHY_SCAN", 8) == 0) {
        uint8_t found = 0U;
        char out[64];
        int n;
        if (ETH_PHY_ScanAddress(&found) == ETH_OK) {
            n = snprintf(out, sizeof(out), "PHY_SCAN|ADDR:%u|CONFIGURED:%u",
                         (unsigned)found, (unsigned)PHY_ADDRESS);
        } else {
            n = snprintf(out, sizeof(out), "PHY_SCAN|ADDR:NONE");
        }
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- Dahili PHY loopback: kablosuz TX/RX yolu testi --- */
    if (len >= 8U && memcmp(data, "LOOPBACK", 8) == 0) {
        uint32_t en = 0U;
        char out[48];
        (void)eaetis_parse_uint(data, len, "EN:", 10, &en);
        if (ETH_PHY_SetLoopback(PHY_ADDRESS, en != 0U) != ETH_OK) {
            (void)ETH_BSP_ReplyUDP("ERR|SMI_TIMEOUT", 15U);
            return true;
        }
        int n = snprintf(out, sizeof(out), "LOOPBACK|EN:%lu", (unsigned long)en);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- Genel echo: ECHO|<veri> --- */
    if (len >= 5U && memcmp(data, "ECHO|", 5) == 0) {
        (void)ETH_BSP_ReplyUDP(&data[5], (uint16_t)(len - 5U));
        return true;
    }


#if ETH_ENABLE_TELEMETRY
    /* --- Degisken listesini kesfet: GET_VARS --------------------------
     * Yanit: VARS|COUNT:n|V0:ad:tip:erisim:birim|V1:... */
    if (len >= 8U && memcmp(data, "GET_VARS", 8) == 0) {
        char out[512];
        int o = snprintf(out, sizeof(out), "VARS|COUNT:%lu",
                         (unsigned long)var_count);

        for (uint32_t i = 0U; i < var_count && o > 0 && o < (int)sizeof(out) - 48; i++) {
            const ETH_Var_t *v = var_table[i];
            int n = snprintf(&out[o], sizeof(out) - (size_t)o,
                             "|V%lu:%s:%s:%s:%s",
                             (unsigned long)i, v->name,
                             var_type_name(v->type),
                             v->writable ? "rw" : "ro",
                             (v->unit != NULL) ? v->unit : "-");
            if (n < 0) break;
            o += n;
        }
        if (o > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)o);
        return true;
    }

    /* --- Tum degerleri tek pakette oku: READ_ALL ---------------------- */
    if (len >= 8U && memcmp(data, "READ_ALL", 8) == 0) {
        char out[512];
        int o = snprintf(out, sizeof(out), "VALS");

        for (uint32_t i = 0U; i < var_count && o > 0 && o < (int)sizeof(out) - 48; i++) {
            const ETH_Var_t *v = var_table[i];
            char num[24];
            (void)var_fmt(num, sizeof(num), var_get(v));

            int n = snprintf(&out[o], sizeof(out) - (size_t)o, "|%s:%s", v->name, num);
            if (n < 0) break;
            o += n;
        }
        if (o > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)o);
        return true;
    }

    /* --- Tek degisken oku: READ|VAR:ad -------------------------------- */
    if (len >= 5U && memcmp(data, "READ|", 5) == 0) {
        char name[40], num[24], out[80];
        if (!eaetis_parse_str(data, len, "VAR:", name, sizeof(name))) {
            (void)ETH_BSP_ReplyUDP("ERR|NO_VAR_NAME", 15U);
            return true;
        }
        const ETH_Var_t *v = var_find(name);
        if (v == NULL) {
            (void)ETH_BSP_ReplyUDP("ERR|UNKNOWN_VAR", 15U);
            return true;
        }
        (void)var_fmt(num, sizeof(num), var_get(v));
        int n = snprintf(out, sizeof(out), "VAL|%s:%s", v->name, num);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- Degisken yaz: WRITE|VAR:ad|VAL:sayi -------------------------- */
    if (len >= 6U && memcmp(data, "WRITE|", 6) == 0) {
        char name[40], num[24], out[80];
        float value = 0.0f;

        if (!eaetis_parse_str(data, len, "VAR:", name, sizeof(name)) ||
            !eaetis_parse_float(data, len, "VAL:", &value)) {
            (void)ETH_BSP_ReplyUDP("ERR|BAD_ARGS", 12U);
            return true;
        }
        const ETH_Var_t *v = var_find(name);
        if (v == NULL) {
            (void)ETH_BSP_ReplyUDP("ERR|UNKNOWN_VAR", 15U);
            return true;
        }
        if (!v->writable) {
            (void)ETH_BSP_ReplyUDP("ERR|READ_ONLY", 13U);
            return true;
        }

        var_set(v, value);

        /* Yazdiktan sonra GERI OKUYUP donuyoruz: arayuz boylece istedigi
         * degerin degil, donanimda fiilen olusan degerin dogrulamasini alir. */
        (void)var_fmt(num, sizeof(num), var_get(v));
        int n = snprintf(out, sizeof(out), "WOK|%s:%s", v->name, num);
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }
#endif /* ETH_ENABLE_TELEMETRY */

#if ETH_ENABLE_IAP
    /* --- IAP: START_IAP|SIZE:n|CRC:0x... --- */
    if (len >= 9U && memcmp(data, "START_IAP", 9) == 0) {
        uint32_t size = 0U, crc = 0U;
        char tmp[128];
        uint16_t cl = (len < sizeof(tmp) - 1U) ? len : (uint16_t)(sizeof(tmp) - 1U);
        memcpy(tmp, data, cl);
        tmp[cl] = '\0';

        const char *p_size = strstr(tmp, "SIZE:");
        const char *p_crc  = strstr(tmp, "CRC:");
        if (p_size == NULL || p_crc == NULL) {
            (void)ETH_BSP_ReplyUDP("IAP_ERR|BAD_HEADER", 18U);
            return true;
        }
        size = (uint32_t)strtoul(p_size + 5, NULL, 10);
        crc  = (uint32_t)strtoul(p_crc  + 4, NULL, 0);

        if (ETH_IAP_Begin(size, crc) == ETH_OK) {
            (void)ETH_BSP_ReplyUDP("IAP_READY", 9U);
        } else {
            (void)ETH_BSP_ReplyUDP("IAP_ERR|BEGIN_FAILED", 20U);
        }
        return true;
    }

    /* --- IAP: FW_DATA|SEQ:i|LEN:n|<binary> --- */
    if (len >= 7U && memcmp(data, "FW_DATA", 7) == 0) {
        /* Ucuncu '|' isaretinden sonrasi ham binary. Basligi metin olarak
         * ayristirirken binary kisma ASLA string fonksiyonu uygulamiyoruz. */
        uint16_t bars = 0U, i;
        uint32_t seq = 0U, dlen = 0U;

        for (i = 0U; i < len && bars < 3U; i++) {
            if (data[i] == '|') {
                bars++;
                if (bars == 1U) {
                    if ((uint16_t)(i + 5U) < len && memcmp(&data[i + 1U], "SEQ:", 4) == 0) {
                        seq = 0U;
                        for (uint16_t k = i + 5U; k < len && data[k] >= '0' && data[k] <= '9'; k++)
                            seq = seq * 10U + (uint32_t)(data[k] - '0');
                    }
                } else if (bars == 2U) {
                    if ((uint16_t)(i + 5U) < len && memcmp(&data[i + 1U], "LEN:", 4) == 0) {
                        dlen = 0U;
                        for (uint16_t k = i + 5U; k < len && data[k] >= '0' && data[k] <= '9'; k++)
                            dlen = dlen * 10U + (uint32_t)(data[k] - '0');
                    }
                }
            }
        }

        if (bars != 3U || dlen == 0U || dlen > ETH_IAP_CHUNK_SIZE ||
            (uint32_t)(i + dlen) > (uint32_t)len) {
            (void)ETH_BSP_ReplyUDP("IAP_ERR|BAD_CHUNK", 17U);
            return true;
        }

        if (ETH_IAP_WriteChunk(seq, &data[i], (uint16_t)dlen) == ETH_OK) {
            char ack[24];
            int n = snprintf(ack, sizeof(ack), "ACK:%lu", (unsigned long)seq);
            if (n > 0) (void)ETH_BSP_ReplyUDP(ack, (uint16_t)n);
        } else {
            (void)ETH_BSP_ReplyUDP("IAP_ERR|WRITE_FAILED", 20U);
        }
        return true;
    }

    /* --- IAP: END_IAP --- */
    if (len >= 7U && memcmp(data, "END_IAP", 7) == 0) {
        if (ETH_IAP_Finish() == ETH_OK) {
            (void)ETH_BSP_ReplyUDP("FLASH_SUCCESS|JUMP_OK", 21U);
            /* Yanitin hatta cikmasi icin kisa bekleme, sonra atla. */
            uint32_t t = ETH_GetTick();
            while ((ETH_GetTick() - t) < 100U) { __NOP(); }
            ETH_IAP_JumpToApplication();
        } else {
            (void)ETH_BSP_ReplyUDP("IAP_ERR|CRC_MISMATCH", 20U);
        }
        return true;
    }
#endif /* ETH_ENABLE_IAP */

#if ETH_ENABLE_USER_CMD
    /* --- Telemetri abonelik: TELEMETRY_SUB|PORT:n  (PORT:0 = abonelikten cik) --- */
    if (len >= 13U && memcmp(data, "TELEMETRY_SUB", 13) == 0) {
        uint32_t port = 0U;
        char out[64];
        int n;

        (void)eaetis_parse_uint(data, len, "PORT:", 10, &port);

        if (port == 0U || port > 65535U) {
            telem_valid = false;
            n = snprintf(out, sizeof(out), "TELEMETRY|SUB:0");
        } else {
            memcpy(telem_ip, last_udp.src_ip, 4);
            telem_port = (uint16_t)port;
            telem_valid = true;
            n = snprintf(out, sizeof(out), "TELEMETRY|SUB:1|PORT:%lu",
                         (unsigned long)port);
        }
        if (n > 0) (void)ETH_BSP_ReplyUDP(out, (uint16_t)n);
        return true;
    }

    /* --- Kullanici tanimli komutlar (LED, sensor, role...) ---
     * BSP'nin tanimadigi her komut buraya duser. Handler kayitli degilse
     * veya "benim degil" derse paket sessizce yok sayilir. */
    if (user_cmd_handler != NULL && len > 0U) {
        char cmd[ETH_USER_CMD_MAX_LEN];
        char args[ETH_USER_ARGS_MAX_LEN];
        char resp[ETH_USER_RESP_MAX_LEN];
        uint16_t i = 0U, a = 0U;

        /* Komut adi: ilk '|' isaretine kadar. Tampon sinirini ASLA asmaz. */
        while (i < len && data[i] != '|' && i < (uint16_t)(sizeof(cmd) - 1U)) {
            cmd[i] = (char)data[i];
            i++;
        }
        cmd[i] = '\0';

        /* Komut adi tampona sigmadiysa bizim komutumuz degil - reddet. */
        if (i == (uint16_t)(sizeof(cmd) - 1U) && i < len && data[i] != '|') {
            return false;
        }

        if (i < len && data[i] == '|') {
            i++;
            while (i < len && a < (uint16_t)(sizeof(args) - 1U)) {
                args[a++] = (char)data[i++];
            }
        }
        args[a] = '\0';

        resp[0] = '\0';
        int n = user_cmd_handler(cmd, args, resp, (uint16_t)sizeof(resp));

        if (n > 0) {
            if (n > (int)sizeof(resp)) n = (int)sizeof(resp);
            (void)ETH_BSP_ReplyUDP(resp, (uint16_t)n);
            return true;
        }
    }
#endif /* ETH_ENABLE_USER_CMD */

    return false;
}

#endif /* ETH_ENABLE_EAETIS_CMD */

/* ===== IPv4 ayrıstirma ================================================= */

static void ipv4_handle(const uint8_t *frame, uint16_t frame_len)
{
    if (frame_len < (uint16_t)(ETH_HDR_LEN + IP_MIN_HDR_LEN)) return;

    const uint8_t *ip = &frame[ETH_HDR_LEN];

    if ((ip[0] >> 4) != 4U) return;                   /* IPv4 degil */

    uint16_t ihl = (uint16_t)((ip[0] & 0x0FU) * 4U);
    if (ihl < IP_MIN_HDR_LEN) return;
    if ((uint16_t)(ETH_HDR_LEN + ihl) > frame_len) return;

    uint16_t total_len = rd16(&ip[2]);
    if (total_len < ihl) return;
    if ((uint16_t)(ETH_HDR_LEN + total_len) > frame_len) return;

    /* PARCALANMIS PAKETLERI DUSUR.
     * E-AETIS fault-injection testi 2048 baytlik UDP gonderiyor; bu IP
     * katmaninda parcalanir. Reassembly desteklemiyoruz - sessizce atmak
     * dogru davranis, GUI'nin timeout almasi beklenen sonuctur. */
    uint16_t frag = rd16(&ip[6]);
    if ((frag & IP_FLAG_MF) || (frag & IP_FRAG_OFF_MASK)) return;

    /* Bize mi? (broadcast'e izin veriyoruz - discovery icin) */
    bool to_me    = (memcmp(&ip[16], my_ip, 4) == 0);
    bool to_bcast = (ip[16] == 255U && ip[17] == 255U &&
                     ip[18] == 255U && ip[19] == 255U);
    if (!to_me && !to_bcast) return;

    /* Gonderenin ARP bilgisini ogren - yanit verirken ARP beklemeyelim. */
    arp_cache_put(&ip[12], &frame[6]);

    uint16_t payload_len = (uint16_t)(total_len - ihl);

    switch (ip[9]) {
#if ETH_ENABLE_ICMP
        case IP_PROTO_ICMP:
            if (to_me) icmp_handle(frame, ip, ihl, payload_len);
            break;
#endif
#if ETH_ENABLE_UDP
        case IP_PROTO_UDP: {
            if (payload_len < UDP_HDR_LEN) return;

            const uint8_t *udp = &ip[ihl];
            uint16_t src_port = rd16(&udp[0]);
            uint16_t dst_port = rd16(&udp[2]);
            uint16_t udp_len  = rd16(&udp[4]);

            if (udp_len < UDP_HDR_LEN || udp_len > payload_len) return;

            uint16_t dlen = (uint16_t)(udp_len - UDP_HDR_LEN);
            const uint8_t *dp = &udp[UDP_HDR_LEN];

            memcpy(last_udp.src_mac, &frame[6], 6);
            memcpy(last_udp.src_ip,  &ip[12],   4);
            last_udp.src_port = src_port;
            last_udp.dst_port = dst_port;
            last_udp.valid    = true;

#if ETH_ENABLE_EAETIS_CMD
            if (dst_port == ETH_EAETIS_PORT) {
                if (eaetis_handle(dp, dlen)) return;
            }
#endif
            if (user_cb != NULL && dst_port == user_port) {
                user_cb(&ip[12], src_port, dp, dlen);
            }
            break;
        }
#endif
        default:
            break;
    }
}

/* ===== Genel API ======================================================= */

ETH_Status_t ETH_BSP_Init(void)
{
    /* NOT: Degisken kayit defterine DOKUNMUYORUZ. Kullanici degiskenlerini
     * ETH_BSP_Init() oncesinde de sonrasinda da kaydedebilir. */
    memset(arp_cache, 0, sizeof(arp_cache));
    memset(&last_udp, 0, sizeof(last_udp));
    user_cb   = NULL;
    user_port = 0U;
#if ETH_ENABLE_USER_CMD
    user_cmd_handler = NULL;
    telem_valid      = false;
    telem_port       = 0U;
#endif

    return ETH_Driver_Init();
}

uint32_t ETH_BSP_ProcessEvents(void)
{
    uint8_t *frame = NULL;
    uint16_t len   = 0U;
    uint32_t processed = 0U;

    if (!ETH_Driver_IsReady()) return 0U;

    /* Ring'i bir turda BOSALTMIYORUZ: en fazla RX_DESC_COUNT paket isleyip
     * kontrolu kullaniciya iade ediyoruz. Aksi halde yogun trafikte bu
     * fonksiyon hicbir zaman geri donmez ve kullanicinin ana dongusu ac kalir. */
    for (uint32_t guard = 0U; guard < ETH_RX_DESC_COUNT; guard++) {

        if (ETH_ReceiveFrame(&frame, &len) != ETH_OK) break;

        if (len >= ETH_HDR_LEN) {
            /* Hedef MAC bize mi yoksa broadcast'e mi? */
            bool for_me = (memcmp(frame, my_mac, 6) == 0);
            bool for_bc = (memcmp(frame, bcast_mac, 6) == 0);

            if (for_me || for_bc) {
                switch (rd16(&frame[12])) {
#if ETH_ENABLE_ARP
                    case ETHERTYPE_ARP:  arp_handle(frame, len);  break;
#endif
                    case ETHERTYPE_IPV4: ipv4_handle(frame, len); break;
                    default: break;    /* VLAN, IPv6 vb.: sessizce yok say */
                }
            }
        }

        ETH_ReleaseRxFrame();
        processed++;
    }

    return processed;
}

void ETH_BSP_RegisterUDPCallback(uint16_t listen_port, ETH_UDP_Callback_t cb)
{
    user_port = listen_port;
    user_cb   = cb;
}

ETH_Status_t ETH_BSP_GetLinkState(ETH_LinkState_t *state)
{
    return ETH_GetLinkState(state);
}

void ETH_BSP_GetStats(ETH_Stats_t *stats)
{
    ETH_GetStats(stats);
}

#if ETH_ENABLE_USER_CMD

void ETH_BSP_RegisterCommandHandler(ETH_UserCmdHandler_t handler)
{
    user_cmd_handler = handler;
}

bool ETH_BSP_TelemetryReady(void)
{
    return telem_valid;
}

ETH_Status_t ETH_BSP_SendTelemetry(const char *text)
{
    if (text == NULL)  return ETH_ERR_PARAM;
    if (!telem_valid)  return ETH_ERR_NO_DATA;   /* Henuz abone yok */

    size_t l = strlen(text);
    if (l == 0U || l > 1400U) return ETH_ERR_PARAM;

    return ETH_BSP_SendUDP(telem_ip, telem_port, ETH_EAETIS_PORT,
                           text, (uint16_t)l);
}

#endif /* ETH_ENABLE_USER_CMD */

void ETH_BSP_GetIPAddress(uint8_t ip[4])
{
    if (ip != NULL) memcpy(ip, my_ip, 4);
}
