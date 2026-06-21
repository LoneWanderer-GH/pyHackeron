/*
 * corelec_ble_btstack.c
 * Backend BLE BTstack (BlueKitchen) – multi-plateforme embarqué
 *
 * TODO: implémenter les appels GATT client BTstack
 *       (gap_connect, gatt_client_discover_primary_services,
 *        gatt_client_write_value_of_characteristic, …)
 *
 * Compilation : BTstack src/ et platform/ doivent être dans le include path.
 */

#include "corelec_ble_backend.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── Inclusions BTstack (à activer selon le SDK) ───────────────
#include "btstack.h"
#include "hci.h"
#include "l2cap.h"
#include "ble/gatt_client.h"
#include "ble/sm.h"
 ────────────────────────────────────────────────────────────── */

/* ── Structure interne ───────────────────────────────────────── */

struct corelec_ble_backend {
    char     address[64];    /* adresse BLE "AA:BB:CC:DD:EE:FF" */
    unsigned timeout_seconds;

    corelec_ble_on_status_fn       on_status;
    corelec_ble_on_notification_fn on_notification;

    /* TODO: bd_addr_t      peer_addr;
             hci_con_handle_t conn_handle;
             gatt_client_characteristic_t notify_char;
             gatt_client_characteristic_t write_char;
             btstack_packet_callback_registration_t hci_reg;
             btstack_packet_callback_registration_t sm_reg;  */
};

/* ── Création / destruction ──────────────────────────────────── */

corelec_ble_backend_t *corelec_ble_backend_create(
    corelec_ble_backend_kind_t backend,
    const char                *address,
    unsigned                   timeout_seconds,
    corelec_ble_on_status_fn   on_status,
    corelec_ble_on_notification_fn on_notification)
{
    if (backend != CORELEC_BLE_BACKEND_BTSTACK)
        return NULL;

    corelec_ble_backend_t *b = calloc(1, sizeof(*b));
    if (!b) return NULL;

    strncpy(b->address, address, sizeof(b->address) - 1);
    b->timeout_seconds = timeout_seconds;
    b->on_status       = on_status;
    b->on_notification = on_notification;

    /* TODO: sscanf(address, ...) → bd_addr_t
             enregistrer les callbacks HCI/SM/GATT */

    return b;
}

void corelec_ble_backend_destroy(corelec_ble_backend_t *b)
{
    if (!b) return;
    /* TODO: gap_disconnect si connecté, désenregistrer callbacks */
    free(b);
}

/* ── Cycle de vie ────────────────────────────────────────────── */

int corelec_ble_backend_connect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: gap_connect(b->peer_addr, BD_ADDR_TYPE_LE_PUBLIC/RANDOM)
             puis découverte de services et activation des notifications */
    fprintf(stderr, "[btstack] connect(%s) – non implémenté\n", b->address);
    return -1;
}

int corelec_ble_backend_disconnect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: gap_disconnect(b->conn_handle) */
    return -1;
}

int corelec_ble_backend_restart(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    corelec_ble_backend_disconnect(b);
    return corelec_ble_backend_connect(b);
}

int corelec_ble_backend_poll(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* BTstack est événementiel ; le run loop est géré par btstack_run_loop_execute()
       ou btstack_run_loop_embedded_execute_once() selon la plateforme. */
    return 0;
}

int corelec_ble_backend_send_ask(corelec_ble_backend_t *b, uint8_t cmd)
{
    if (!b) return -1;
    /* TODO: gatt_client_write_value_of_characteristic_without_response(
                 NULL, b->conn_handle, b->write_char.value_handle,
                 sizeof(cmd), &cmd) */
    (void)cmd;
    return -1;
}
