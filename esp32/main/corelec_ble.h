/**
 * corelec_ble.h — Client GATT NimBLE pour le régulateur Corelec.
 *
 * Machine d'état :
 *   IDLE → SCANNING → CONNECTING → DISCOVERING → SUBSCRIBING → POLLING
 *   (reconnexion automatique en cas de déconnexion)
 *
 * UUID de la caractéristique : e7add780-b042-4876-aae1-112855353cc1
 * Séquence de polling : [77, 83, 65, 69] toutes les 2 s, 500 ms entre chaque.
 * Timeout inactivité  : 60 s sans notification → reconnexion.
 */
#pragma once
#include "corelec_types.h"

/**
 * Initialise le stack NimBLE et démarre la recherche du régulateur.
 *
 * @param target_addr  Adresse MAC BLE au format "AA:BB:CC:DD:EE:FF".
 *                     Configurable via menuconfig (CONFIG_CORELEC_BLE_DEVICE_ADDR).
 * @param on_decoded   Callback appelé dans le contexte du host task NimBLE.
 * @param user_ctx     Pointeur opaque transmis à on_decoded.
 */
void corelec_ble_init(const char *target_addr,
                      corelec_on_decoded_fn on_decoded, void *user_ctx);
