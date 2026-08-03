/* ============================================================================
 * Ethernet_BSP - Linker Script Eklentisi
 *
 * .eth_desc section'i, ETH DMA'nin erisebildigi ve MPU tarafindan
 * non-cacheable ilan edilen bolgeye yerlesmelidir.
 *
 * ADIM 1: MEMORY blogunda descriptor bolgesini ayirin.
 * ADIM 2: SECTIONS icine asagidaki blogu ekleyin.
 * ADIM 3: eth_config.h'deki ETH_DESC_REGION_BASE ile ADRESI ESLESTIRIN.
 * ========================================================================= */

/* --- STM32H563 ornegi --- */
/*
MEMORY
{
  FLASH    (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
  RAM_DESC (rw)  : ORIGIN = 0x20000000, LENGTH = 32K     <-- ETH bolgesi
  RAM      (rw)  : ORIGIN = 0x20008000, LENGTH = 608K
}
*/

/* --- STM32H743 ornegi ---
 * DIKKAT: DTCM (0x20000000) KULLANILAMAZ - ETH DMA oraya erisemez.
 *         D2 domain SRAM (0x30000000) kullanin.
 */
/*
MEMORY
{
  FLASH    (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
  DTCMRAM  (rw)  : ORIGIN = 0x20000000, LENGTH = 128K
  RAM_D1   (rw)  : ORIGIN = 0x24000000, LENGTH = 512K
  RAM_DESC (rw)  : ORIGIN = 0x30000000, LENGTH = 32K     <-- ETH bolgesi
}
*/

/* --- SECTIONS icine eklenecek --- */
/*
  .eth_desc (NOLOAD) :
  {
    . = ALIGN(32);
    *(.eth_desc)
    *(.eth_desc*)
    . = ALIGN(32);
  } >RAM_DESC
*/

/* MPU bolge boyutu 32 bayta hizali olmali (ARMv8-M) veya 2'nin kuvveti
 * olmali (ARMv7-M). ETH_DESC_REGION_SIZE'i buna gore secin. */
