/*
 * syscfg/syscfg.h – configuration NimBLE standalone (POSIX/Linux).
 *
 * Normalement généré par l'outil Newt (écosystème Apache Mynewt).
 * Ce fichier est une substitution manuelle pour compiler NimBLE sans Newt,
 * via GPRbuild (backends/nimble/corelec_ble_nimble.gpr).
 *
 * Ajustez les valeurs selon la RAM disponible sur la cible.
 *
 * Référence :
 *   https://github.com/apache/mynewt-nimble/tree/nimble_1_9_0_tag/porting
 */

#ifndef H_MYNEWT_SYSCFG_
#define H_MYNEWT_SYSCFG_

/* ── Helpers standard ─────────────────────────────────────────────────── */
#define MYNEWT_VAL(x)           MYNEWT_VAL_ ## x
#define MYNEWT_VAL_CHOICE(x, y) MYNEWT_VAL_ ## x ## _ ## y

/* ── Buffers HCI / ACL ────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_ACL_BUF_COUNT            24
#define MYNEWT_VAL_BLE_ACL_BUF_SIZE             255
#define MYNEWT_VAL_BLE_HCI_EVT_BUF_SIZE         70
#define MYNEWT_VAL_BLE_HCI_EVT_HI_BUF_COUNT     30
#define MYNEWT_VAL_BLE_HCI_EVT_LO_BUF_COUNT     8
#define MYNEWT_VAL_BLE_HCI_ACL_OUT_COUNT        24

/* ── Connexions ───────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_MAX_CONNECTIONS          1
#define MYNEWT_VAL_BLE_MAX_PERIODIC_SYNCS       0
#define MYNEWT_VAL_BLE_MULTI_CONN_LAN           0

/* ── Rôles ────────────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_ROLE_CENTRAL             1
#define MYNEWT_VAL_BLE_ROLE_PERIPHERAL          0
#define MYNEWT_VAL_BLE_ROLE_BROADCASTER         0
#define MYNEWT_VAL_BLE_ROLE_OBSERVER            0

/* ── GATT Client ──────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_GATT_MAX_PROCS           4
#define MYNEWT_VAL_BLE_GATT_READ_MAX_ATTRS      8
#define MYNEWT_VAL_BLE_GATT_WRITE_MAX_ATTRS     4
#define MYNEWT_VAL_BLE_GATT_FIND_INC_SVCS_MAX_SVCS  4
#define MYNEWT_VAL_BLE_ATT_SVR_MAX_PREP_ENTRIES 64

/* ── Security Manager ─────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_SM_LEGACY                1
#define MYNEWT_VAL_BLE_SM_SC                    1
#define MYNEWT_VAL_BLE_SM_MAX_PROCS             1
#define MYNEWT_VAL_BLE_SM_OUR_KEY_DIST          0x0f
#define MYNEWT_VAL_BLE_SM_THEIR_KEY_DIST        0x0f
#define MYNEWT_VAL_BLE_SM_BONDING               0
#define MYNEWT_VAL_BLE_SM_MITM                  0
#define MYNEWT_VAL_BLE_SM_IO_CAP                4  /* NoInputNoOutput */
#define MYNEWT_VAL_BLE_STORE_MAX_BONDS          3
#define MYNEWT_VAL_BLE_STORE_MAX_CCCDS          8

/* ── Publicité / Scan ─────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_MAX_ADV_INSTANCES        1
#define MYNEWT_VAL_BLE_EXT_ADV                  0
#define MYNEWT_VAL_BLE_PERIODIC_ADV             0
#define MYNEWT_VAL_BLE_LL_NUM_SCAN_RPTS_MEM     8

/* ── ATT ──────────────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_ATT_PREFERRED_MTU        256
#define MYNEWT_VAL_BLE_ATT_SVR_QUEUED_WRITE_TMO 30000   /* ms */

/* ── Host task ────────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_HOST_TASK_STACK_SIZE     512
#define MYNEWT_VAL_BLE_HOST_STOP_TIMEOUT_MS     2000

/* ── Mémoire / mbuf ───────────────────────────────────────────────────── */
#define MYNEWT_VAL_MSYS_1_BLOCK_COUNT           24
#define MYNEWT_VAL_MSYS_1_BLOCK_SIZE            110
#define MYNEWT_VAL_MSYS_2_BLOCK_COUNT           0
#define MYNEWT_VAL_MSYS_2_BLOCK_SIZE            0

/* ── Logging ──────────────────────────────────────────────────────────── */
#define MYNEWT_VAL_BLE_HS_LOG_LVL               1  /* 0=debug,1=info,2=warn,3=error */
#define MYNEWT_VAL_LOG_LEVEL                    255

/* ── Tinycrypt (crypto interne) ───────────────────────────────────────── */
#define MYNEWT_VAL_BLE_CRYPTO_STACK_MBUF_SIZE   128

/* ── Fonctionnalités désactivées ──────────────────────────────────────── */
#define MYNEWT_VAL_BLE_MESH                     0
#define MYNEWT_VAL_BLE_ISO                      0
#define MYNEWT_VAL_BLE_CS                       0   /* Channel Sounding */
#define MYNEWT_VAL_BLE_EATT                     0

/* ── NPL Linux ────────────────────────────────────────────────────────── */
#define MYNEWT_VAL_OS_CPUTIME_TIMER_NUM         0
#define MYNEWT_VAL_OS_CPUTIME_FREQ              1000000

#endif /* H_MYNEWT_SYSCFG_ */
