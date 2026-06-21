/*
 * corelec_ble_bluez.c
 * Backend BLE BlueZ 5.x (Linux) – implémentation via D-Bus
 *
 * TODO: remplacer les stubs par les appels D-Bus réels
 *       (org.bluez.Device1, GattCharacteristic1, etc.)
 */

#include "corelec_ble_backend.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── Structure interne ───────────────────────────────────────── */

struct corelec_ble_backend {
    char     address[64];
    unsigned timeout_seconds;

    corelec_ble_on_status_fn       on_status;
    corelec_ble_on_notification_fn on_notification;

    /* TODO: GDBusConnection *dbus;
             char            *object_path;
             GMainContext    *ctx;          */
};

/* ── Création / destruction ──────────────────────────────────── */

corelec_ble_backend_t *corelec_ble_backend_create(
    corelec_ble_backend_kind_t backend,
    const char                *address,
    unsigned                   timeout_seconds,
    corelec_ble_on_status_fn   on_status,
    corelec_ble_on_notification_fn on_notification)
{
    if (backend != CORELEC_BLE_BACKEND_BLUEZ)
        return NULL;

    corelec_ble_backend_t *b = calloc(1, sizeof(*b));
    if (!b) return NULL;

    strncpy(b->address, address, sizeof(b->address) - 1);
    b->timeout_seconds = timeout_seconds;
    b->on_status       = on_status;
    b->on_notification = on_notification;

    /* TODO: ouvrir connexion D-Bus système et préparer l'objet BlueZ */

    return b;
}

void corelec_ble_backend_destroy(corelec_ble_backend_t *b)
{
    if (!b) return;
    /* TODO: libérer ressources D-Bus / GLib */
    free(b);
}

/* ── Cycle de vie ────────────────────────────────────────────── */

int corelec_ble_backend_connect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: org.bluez.Adapter1.StartDiscovery → ConnectDevice → Connect */
    fprintf(stderr, "[bluez] connect(%s) – non implémenté\n", b->address);
    return -1;
}

int corelec_ble_backend_disconnect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: org.bluez.Device1.Disconnect */
    return -1;
}

int corelec_ble_backend_restart(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    (void)corelec_ble_backend_disconnect(b);
    return corelec_ble_backend_connect(b);
}

int corelec_ble_backend_poll(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: itération GMainContext (g_main_context_iteration) */
    return -1;
}

int corelec_ble_backend_send_ask(corelec_ble_backend_t *b, uint8_t cmd)
{
    if (!b) return -1;
    /* TODO: écriture GATT sur la caractéristique de commande (WriteValue) */
    (void)cmd;
    return -1;
}
