/*
 * btstack_config.h – configuration minimale pour un client GATT BLE central.
 *
 * Placé dans backends/btstack/include/ afin d'être trouvé avant les
 * en-têtes systèmes pendant la compilation.  Ajustez selon vos besoins.
 *
 * Référence : https://bluekitchen-gmbh.com/btstack/develop/porting/
 */

#ifndef BTSTACK_CONFIG_H
#define BTSTACK_CONFIG_H

/* ── Rôle : Central BLE (GATT Client) ─────────────────────────────────── */
#define ENABLE_BLE
#define ENABLE_LE_CENTRAL           /* scan + connexion sortante             */
/* #define ENABLE_LE_PERIPHERAL */  /* désactivé : pas de rôle serveur       */

/* Connexions sécurisées LE (SM) */
#define ENABLE_LE_SECURE_CONNECTIONS

/* ── Désactiver la pile Classic BT ───────────────────────────────────────
   Réduit significativement la taille de l'objet final.                    */
/* #define ENABLE_CLASSIC */

/* ── Buffers HCI ──────────────────────────────────────────────────────── */
#define HCI_ACL_PAYLOAD_SIZE             255
#define HCI_INCOMING_PRE_BUFFER_SIZE     14

/* ── Connexions / mémoire ─────────────────────────────────────────────── */
#define MAX_NR_HCI_CONNECTIONS           1
#define MAX_NR_WHITELIST_ENTRIES         4
#define MAX_NR_LE_DEVICE_DB_ENTRIES      8

/* ── Security Manager ─────────────────────────────────────────────────── */
#define MAX_NR_SM_LOOKUP_ENTRIES         3

/* ── Client GATT ──────────────────────────────────────────────────────── */
#define MAX_NR_GATT_CLIENTS              1

/* ── ATT ──────────────────────────────────────────────────────────────── */
#define ATT_REQUEST_BUFFER_SIZE          255

/* ── Timers ───────────────────────────────────────────────────────────── */
/* Nombre maximal de timers BTstack en attente simultanément.             */
#define MAX_NR_BTSTACK_LINK_KEY_DB_MEMORY_ENTRIES  4

/* ── Logging ──────────────────────────────────────────────────────────── */
/* Décommenter pour activer les logs de débogage.                         */
/* #define ENABLE_LOG_INFO  */
/* #define ENABLE_LOG_DEBUG */
/* #define ENABLE_LOG_ERROR */

/* ── Transport HCI ────────────────────────────────────────────────────── */
/* Les implémentations concrètes (H4, WinUSB…) sont sélectionnées
   à l'initialisation dans corelec_ble_btstack.c, pas ici.               */

#endif /* BTSTACK_CONFIG_H */
