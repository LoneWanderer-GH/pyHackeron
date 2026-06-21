/*
 * corelec_ble_winrt.cpp
 * Backend BLE WinRT (Windows 10+) – Windows.Devices.Bluetooth
 *
 * TODO: implémenter les appels WinRT asynchrones
 *       (BluetoothLEDevice, GattCharacteristic, etc.)
 *
 * Compilation : MSVC ou clang-cl, /std:c++17, lien avec windowsapp.lib
 */

#include "corelec_ble_backend.h"

#include <cstdlib>
#include <cstring>
#include <cstdio>

/* ── Inclusions WinRT (à activer après configuration SDK) ──────
#include <winrt/Windows.Devices.Bluetooth.h>
#include <winrt/Windows.Devices.Bluetooth.GenericAttributeProfile.h>
#include <winrt/Windows.Foundation.h>
using namespace winrt;
using namespace Windows::Devices::Bluetooth;
using namespace Windows::Devices::Bluetooth::GenericAttributeProfile;
 ────────────────────────────────────────────────────────────── */

extern "C" {

/* ── Structure interne ───────────────────────────────────────── */

struct corelec_ble_backend {
    char     address[64];
    unsigned timeout_seconds;

    corelec_ble_on_status_fn       on_status;
    corelec_ble_on_notification_fn on_notification;

    /* TODO: BluetoothLEDevice device;
             GattCharacteristic tx_char;
             GattCharacteristic rx_char; */
};

/* ── Création / destruction ──────────────────────────────────── */

corelec_ble_backend_t *corelec_ble_backend_create(
    corelec_ble_backend_kind_t backend,
    const char                *address,
    unsigned                   timeout_seconds,
    corelec_ble_on_status_fn   on_status,
    corelec_ble_on_notification_fn on_notification)
{
    if (backend != CORELEC_BLE_BACKEND_WINRT)
        return nullptr;

    auto *b = static_cast<corelec_ble_backend_t *>(
        std::calloc(1, sizeof(corelec_ble_backend_t)));
    if (!b) return nullptr;

    std::strncpy(b->address, address, sizeof(b->address) - 1);
    b->timeout_seconds = timeout_seconds;
    b->on_status       = on_status;
    b->on_notification = on_notification;

    /* TODO: init_apartment(apartment_type::single_threaded);
             résoudre l'adresse MAC → BluetoothLEDevice::FromBluetoothAddressAsync */

    return b;
}

void corelec_ble_backend_destroy(corelec_ble_backend_t *b)
{
    if (!b) return;
    /* TODO: fermer device WinRT, révoquer handlers */
    std::free(b);
}

/* ── Cycle de vie ────────────────────────────────────────────── */

int corelec_ble_backend_connect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: BluetoothLEDevice::FromBluetoothAddressAsync → GetGattServicesAsync
             → GetCharacteristicsAsync → WriteClientCharacteristicConfigurationDescriptorAsync */
    std::fprintf(stderr, "[winrt] connect(%s) – non implémenté\n", b->address);
    return -1;
}

int corelec_ble_backend_disconnect(corelec_ble_backend_t *b)
{
    if (!b) return -1;
    /* TODO: close() device WinRT */
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
    /* Les notifications WinRT arrivent par callback → poll sans effet ici */
    return 0;
}

int corelec_ble_backend_send_ask(corelec_ble_backend_t *b, uint8_t cmd)
{
    if (!b) return -1;
    /* TODO: GattCharacteristic::WriteValueAsync */
    (void)cmd;
    return -1;
}

} /* extern "C" */
