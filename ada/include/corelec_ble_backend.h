#ifndef CORELEC_BLE_BACKEND_H
#define CORELEC_BLE_BACKEND_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CORELEC_BLE_BACKEND_NONE = 0,
    CORELEC_BLE_BACKEND_BLUEZ = 1,
    CORELEC_BLE_BACKEND_WINRT = 2,
    CORELEC_BLE_BACKEND_NIMBLE = 3,
    CORELEC_BLE_BACKEND_BTSTACK = 4
} corelec_ble_backend_kind_t;

typedef struct {
    uint8_t state;
    char message[128];
    unsigned elapsed;
    unsigned remaining;
    unsigned timeout;
    unsigned retry_count;
    uint8_t should_retry;
    uint8_t stop_requested;
} corelec_ble_status_t;

typedef void (*corelec_ble_on_status_fn)(const corelec_ble_status_t *status);
typedef void (*corelec_ble_on_notification_fn)(const uint8_t *data, unsigned length);

typedef struct corelec_ble_backend corelec_ble_backend_t;

corelec_ble_backend_t *corelec_ble_backend_create(
    corelec_ble_backend_kind_t backend,
    const char *address,
    unsigned timeout_seconds,
    corelec_ble_on_status_fn on_status,
    corelec_ble_on_notification_fn on_notification);

void corelec_ble_backend_destroy(corelec_ble_backend_t *backend);
int corelec_ble_backend_connect(corelec_ble_backend_t *backend);
int corelec_ble_backend_disconnect(corelec_ble_backend_t *backend);
int corelec_ble_backend_restart(corelec_ble_backend_t *backend);
int corelec_ble_backend_poll(corelec_ble_backend_t *backend);
int corelec_ble_backend_send_ask(corelec_ble_backend_t *backend, uint8_t cmd);

#ifdef __cplusplus
}
#endif

#endif