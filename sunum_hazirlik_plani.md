# Staj Sunumu Hazırlık Planı

**Tarih:** 2026-09-14 Pazartesi
**Süre:** 10 dakika
**Konu:** E-AETIS / Ethernet_BSP

Hazırlık üç aşamaya bölündü, aşamalar ayrı günlerde sırayla ele alınacak.

## Aşama 1 — Tamamlandı ✅

Projenin kritik teknik noktalarını, mimarisini ve olası soru/cevaplarını içeren detaylı bir çalışma notu hazırlandı.

- Dosya: [`eaetis_sunum_notlari.html`](eaetis_sunum_notlari.html)
- Canlı sürüm: https://claude.ai/code/artifact/b70e1b35-af04-46a8-9b38-177e95e99d16
- İçerik: proje genel bakış, mimari (3 bağımsız eksen), yapılandırma katmanı, sürücü çekirdeği, port katmanı (EQOS/GMAC), PHY katmanı, uygulama protokolü, IAP bootloader, masaüstü arayüz, bilinen sınırlar
- §01: HAL_ETH / LwIP / FreeRTOS neden kullanılmadı — karşılaştırma tablosu
- §11: kategorilere ayrılmış soru bankası (tasarım kararları, donanım, bellek/DMA, ağ protokolleri, güvenlik, genel)

## Aşama 2 — Tamamlandı ✅

10 dakikalık, 12 slaytlık gerçek bir slayt destesi hazırlandı: ok tuşları/trackpad ile gezilebilir, az metin + tablo + elle çizilmiş SVG diyagramlar (mimari, DMA ring, paket akışı, IAP sequence) ağırlıklı.

- Dosya: [`eaetis_sunum_slaytlari.html`](eaetis_sunum_slaytlari.html)
- Canlı sürüm: https://claude.ai/code/artifact/261833fd-11a1-4aa6-81e3-56b7a4f48254
- Akış: Kapak → Proje ne yapıyor → Neden hazır yığın yok (tablo) → Taşınabilirlik (tablo) → Mimari (diyagram) → Çekirdek sürücü/ring (diyagram) → Paket akışı (diyagram) → IAP (sequence diyagramı) → GUI (ekran görüntüsü) → Doğrulama (tablo) → Bilinen sınırlar → Kapanış (rakamlar)

## Aşama 3 — Aşama 2'den sonra

Daha basit, kısa tanımlar içeren, kağıda geçirilip çalışılabilecek bir özet/cheat-sheet hazırlanacak.

- Aşama 1'deki detaylı içerikten süzülecek
- Terim + 1 cümlelik tanım formatında olacak
- Sunumu tekrar ederken (ezber/prova) kullanılacak
