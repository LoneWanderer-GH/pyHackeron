/*
 * corelec_ble_nimble.c
 * Backend BLE Apache NimBLE (ESP32 / Zephyr / RIOT)
 *
 * TODO: implémenter les appels GATT client NimBLE
 *       (ble_gap_connect, ble_gattc_disc_all_chrs, ble_gattc_write, …)
 *
 * Compilation : toolchain ESP-IDF ou Zephyr avec NimBLE activé.
 */

#include "corelec_ble_backend.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── Inclusions NimBLE (à activer selon le SDK) ────────────────
#include "nimble/ble.h"
#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
 ────────────────────────────────────────────────────────────── */

/* ── Structure interne ───────────────────────────────────────── */

struct corelec_ble_backend {
    char     address[64];   /* adresse BLE (chaîne "AA:BB:CC:DD:EE:FF") */
    unsigned timeout_seconds;

    corelec_ble_on_status_fn       on_status;
    corelec_ble_on_notification_fn on_notification;

    /* TODO: ble_addr_t        peer_addr;
             uint16_t          conn_handle;
             uint16_t          notify_handle;
             uint16_t          write_handle;  */
};

/* ── Création / destruction ──────────────────────────────────── */

corelec_ble_backend_t *corelec_ble_backend_create(
    corelec_ble_backend_kind_t backend,
    const char                *address,
    unsigned                   timeout_seconds,
    corelec_ble_on_status_fn   on_status,
    corelec_ble_on_notification_fn on_notification)
{
    if (backend != CORELEC_BLE_BACKEND_NIMBLE)
        return NULL;

    corelec_ble_backend_t *b = calloc(1, sizeof(*b));
    if (!b) return NULL;

    strncpy(b->address, address, sizeof(b->address) - 1);
    b->timeout_seconds = timeout_seconds;
    b->on_status       = on_status;
    b->on_notification = on_notification;

    /* TODO: convertir b->address en ble_addr_t (ble_addr_from_str) */

    return b;
}

void corelec_ble_backend_destroy(corelec_ble_backend_t *b)
{
    if (!b) return;
    /* TODO: déconnecter si connecté, libérer handles */
    free(b);
}

/* ── Cycle de vie ────────────────────────────────────────────── */

int corelec_ble_backend_connect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: ble_gap_connect → découverte services → activation notifications */
    fprintf(stderr, "[nimble] connect(%s) – non implémenté\n", b->address);
    return -1;
}

int corelec_ble_backend_disconnect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: ble_gap_terminate(b->conn_handle, BLE_ERR_REM_USER_CONN_TERM) */
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
    /* NimBLE est piloté par events ; un appel à nimble_port_run() ou
       os_eventq_run() est géré au niveau système, pas ici. */
    return 0;
}

int corelec_ble_backend_send_ask(corelec_ble_backend_t *b, uint8_t cmd)
{
    if (!b) return -1;
    /* TODO: construire le paquet et appeler ble_gattc_write_no_rsp_flat
             (b->conn_handle, b->write_handle, &cmd, sizeof(cmd)) */
    (void)cmd;
    return -1;
}
