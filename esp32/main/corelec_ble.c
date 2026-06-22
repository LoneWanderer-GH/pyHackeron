/**
 * corelec_ble.c — Client GATT NimBLE (ESP-IDF ≥ 5.x).
 *
 * Séquence de démarrage :
 *   1. nimble_port_init()
 *   2. ble_hs_cfg callbacks → ble_app_on_sync() → ble_gap_disc()
 *   3. Scan → trouver cible par adresse MAC → ble_gap_connect()
 *   4. Connexion → découvrir toutes les caractéristiques
 *   5. Trouver chr par UUID → découvrir son descripteur CCCD
 *   6. Écrire 0x0001 dans CCCD → activer notifications
 *   7. Démarrer tâche poll (asks toutes les 2 s)
 *   8. Réception des notifications → parseur de flux → décodage → callback
 *   9. Sur déconnexion ou timeout 60 s → relancer scan
 */
#include "corelec_ble.h"
#include "corelec_protocol.h"
#include "corelec_decoder.h"

#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "host/util/util.h"
#include "services/gap/ble_svc_gap.h"

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

#include <string.h>
#include <stdio.h>
#include <inttypes.h>

static const char *TAG = "corelec_ble";

/* ── UUID de la caractéristique ─────────────────────────────────────────────
 * e7add780-b042-4876-aae1-112855353cc1
 * En little-endian (NimBLE) : c1 3c 35 55 28 11 e1 aa 76 48 42 b0 80 d7 ad e7
 */
static const ble_uuid128_t CORELEC_CHR_UUID =
    BLE_UUID128_INIT(0xc1, 0x3c, 0x35, 0x55, 0x28, 0x11,
                     0xe1, 0xaa,
                     0x76, 0x48, 0x42, 0xb0,
                     0x80, 0xd7, 0xad, 0xe7);

/* UUID CCCD standard (0x2902) */
static const ble_uuid16_t CCCD_UUID = BLE_UUID16_INIT(0x2902);

/* ── Configuration ───────────────────────────────────────────────────────────*/
#define POLL_INTERVAL_MS      2000
#define POLL_CMD_DELAY_MS     500
#define STALE_TIMEOUT_MS      60000
#define RECONNECT_DELAY_MS    2000
#define STREAM_MAX_FRAMES     8

static const uint8_t POLL_SEQ[] = {77, 83, 65, 69};

/* ── État global ─────────────────────────────────────────────────────────────*/
typedef enum {
    BLE_STATE_IDLE,
    BLE_STATE_SCANNING,
    BLE_STATE_CONNECTING,
    BLE_STATE_DISCOVERING,
    BLE_STATE_SUBSCRIBING,
    BLE_STATE_POLLING,
} ble_state_t;

static ble_state_t         s_state          = BLE_STATE_IDLE;
static uint16_t            s_conn_handle    = BLE_HS_CONN_HANDLE_NONE;
static uint16_t            s_chr_val_handle = 0;
static uint16_t            s_cccd_handle    = 0;
static uint16_t            s_svc_end_handle = 0;  /* fin du service contenant le chr */
static uint8_t             s_own_addr_type;
static uint8_t             s_target_addr[6];       /* octets MAC, octet[0] = LSB */
static bool                s_addr_random    = false;

static corelec_on_decoded_fn s_on_decoded = NULL;
static void                *s_user_ctx    = NULL;

static corelec_stream_t    s_stream;
static corelec_decoded_t   s_decoded;       /* état accumulé */

static int64_t             s_last_notify_us = 0;  /* horodatage esp_timer_get_time() */

static TaskHandle_t        s_poll_task = NULL;
static SemaphoreHandle_t   s_poll_sem  = NULL;    /* signalé à chaque connexion réussie */

/* ── Utilitaires ─────────────────────────────────────────────────────────────*/

/** Analyse "AA:BB:CC:DD:EE:FF" → octets MAC little-endian (LSB first). */
static bool parse_mac(const char *str, uint8_t out[6])
{
    unsigned b[6];
    if (sscanf(str, "%02x:%02x:%02x:%02x:%02x:%02x",
               &b[5], &b[4], &b[3], &b[2], &b[1], &b[0]) != 6) {
        return false;
    }
    for (int i = 0; i < 6; i++) out[i] = (uint8_t)b[i];
    return true;
}

static void start_scan(void);
static void start_connecting(const ble_addr_t *addr);

/* ── Tâche de polling ────────────────────────────────────────────────────────*/

static void poll_task(void *arg)
{
    (void)arg;
    while (true) {
        /* Attendre le signal de connexion */
        xSemaphoreTake(s_poll_sem, portMAX_DELAY);

        while (s_state == BLE_STATE_POLLING) {
            /* Vérifier stale timeout */
            int64_t now_us = esp_timer_get_time();
            if (s_last_notify_us > 0 &&
                (now_us - s_last_notify_us) > (int64_t)STALE_TIMEOUT_MS * 1000LL)
            {
                ESP_LOGW(TAG, "Timeout inactivité 60 s → reconnexion");
                ble_gap_terminate(s_conn_handle, BLE_ERR_REM_USER_CONN_TERM);
                break;
            }

            /* Envoyer séquence de demandes */
            for (int i = 0; i < (int)(sizeof(POLL_SEQ)); i++) {
                if (s_state != BLE_STATE_POLLING) break;

                uint8_t pkt[CORELEC_ASK_LEN];
                corelec_build_ask(POLL_SEQ[i], pkt);

                struct os_mbuf *om = ble_hs_mbuf_from_flat(pkt, sizeof(pkt));
                if (om) {
                    int rc = ble_gattc_write_no_rsp(s_conn_handle,
                                                    s_chr_val_handle, om);
                    if (rc != 0) {
                        ESP_LOGW(TAG, "write_no_rsp failed: %d", rc);
                    }
                }
                vTaskDelay(pdMS_TO_TICKS(POLL_CMD_DELAY_MS));
            }

            /* Attendre le reste du cycle */
            vTaskDelay(pdMS_TO_TICKS(
                POLL_INTERVAL_MS - (int)(sizeof(POLL_SEQ)) * POLL_CMD_DELAY_MS));
        }
    }
}

/* ── Callbacks GATT ──────────────────────────────────────────────────────────*/

/* 3. Écriture CCCD → abonnement aux notifications terminé */
static int cccd_write_cb(uint16_t conn_handle,
                         const struct ble_gatt_error *error,
                         struct ble_gatt_attr *attr, void *arg)
{
    (void)attr; (void)arg;
    if (error->status != 0) {
        ESP_LOGE(TAG, "Échec écriture CCCD: %d", error->status);
        ble_gap_terminate(conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        return error->status;
    }
    ESP_LOGI(TAG, "Abonné aux notifications — démarrage polling");
    s_state = BLE_STATE_POLLING;
    s_last_notify_us = esp_timer_get_time();
    xSemaphoreGive(s_poll_sem);
    return 0;
}

/* 2b. Découverte des descripteurs → trouver CCCD (0x2902) */
static int desc_disc_cb(uint16_t conn_handle,
                        const struct ble_gatt_error *error,
                        uint16_t chr_val_handle,
                        const struct ble_gatt_dsc *dsc, void *arg)
{
    (void)chr_val_handle; (void)arg;
    if (error->status == BLE_HS_EDONE) {
        if (s_cccd_handle == 0) {
            ESP_LOGE(TAG, "CCCD introuvable");
            ble_gap_terminate(conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        }
        return 0;
    }
    if (error->status != 0) {
        ESP_LOGE(TAG, "Erreur découverte descripteurs: %d", error->status);
        return error->status;
    }

    if (ble_uuid_cmp(&dsc->uuid.u, &CCCD_UUID.u) == 0) {
        s_cccd_handle = dsc->handle;
        ESP_LOGI(TAG, "CCCD handle=0x%04x", s_cccd_handle);

        /* Activer les notifications */
        s_state = BLE_STATE_SUBSCRIBING;
        uint8_t val[2] = {0x01, 0x00};   /* BLE_GATT_CHR_NOTIFY_F little-endian */
        int rc = ble_gattc_write_flat(conn_handle, s_cccd_handle,
                                      val, sizeof(val), cccd_write_cb, NULL);
        if (rc != 0) {
            ESP_LOGE(TAG, "ble_gattc_write_flat CCCD: %d", rc);
        }
    }
    return 0;
}

/* 2a. Découverte des caractéristiques → chercher notre UUID */
static int chr_disc_cb(uint16_t conn_handle,
                       const struct ble_gatt_error *error,
                       const struct ble_gatt_chr *chr, void *arg)
{
    (void)arg;
    if (error->status == BLE_HS_EDONE) {
        if (s_chr_val_handle == 0) {
            ESP_LOGE(TAG, "Caractéristique Corelec introuvable");
            ble_gap_terminate(conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        }
        return 0;
    }
    if (error->status != 0) {
        ESP_LOGE(TAG, "Erreur découverte chr: %d", error->status);
        return error->status;
    }

    if (ble_uuid_cmp(&chr->uuid.u, &CORELEC_CHR_UUID.u) == 0) {
        s_chr_val_handle = chr->val_handle;
        ESP_LOGI(TAG, "Caractéristique trouvée val_handle=0x%04x", s_chr_val_handle);

        /* Découvrir les descripteurs dans la plage [val+1 .. svc_end] */
        int rc = ble_gattc_disc_all_dscs(conn_handle,
                                          s_chr_val_handle + 1,
                                          s_svc_end_handle,
                                          desc_disc_cb, NULL);
        if (rc != 0) {
            ESP_LOGE(TAG, "ble_gattc_disc_all_dscs: %d", rc);
        }
    }
    return 0;
}

/* 1. Découverte de tous les services → lancer la découverte des chars */
static int svc_disc_cb(uint16_t conn_handle,
                       const struct ble_gatt_error *error,
                       const struct ble_gatt_svc *svc, void *arg)
{
    (void)arg;
    if (error->status == BLE_HS_EDONE) {
        if (s_chr_val_handle == 0 && s_state == BLE_STATE_DISCOVERING) {
            ESP_LOGE(TAG, "Service contenant la caractéristique introuvable");
            ble_gap_terminate(conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        }
        return 0;
    }
    if (error->status != 0) return error->status;

    /* Enregistrer la fin de ce service au cas où il contient notre chr */
    s_svc_end_handle = svc->end_handle;

    /* Découvrir toutes les chars de ce service */
    int rc = ble_gattc_disc_all_chrs(conn_handle,
                                      svc->start_handle, svc->end_handle,
                                      chr_disc_cb, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_gattc_disc_all_chrs: %d", rc);
    }
    return 0;
}

/* ── Gestionnaire d'événements GAP ──────────────────────────────────────────*/

static int ble_gap_event_handler(struct ble_gap_event *event, void *arg)
{
    (void)arg;
    int rc;

    switch (event->type) {

    /* ── Résultat de scan ──────────────────────────────────────────────── */
    case BLE_GAP_EVENT_DISC: {
        const ble_addr_t *addr = &event->disc.addr;
        if (memcmp(addr->val, s_target_addr, 6) == 0) {
            uint8_t expected_type = s_addr_random
                                    ? BLE_ADDR_RANDOM : BLE_ADDR_PUBLIC;
            if (addr->type == expected_type || addr->type == BLE_ADDR_PUBLIC) {
                ESP_LOGI(TAG, "Cible trouvée — connexion en cours");
                ble_gap_disc_cancel();
                start_connecting(addr);
            }
        }
        return 0;
    }

    /* ── Connexion établie ─────────────────────────────────────────────── */
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status != 0) {
            ESP_LOGW(TAG, "Connexion échouée (%d) → rescan dans %d ms",
                     event->connect.status, RECONNECT_DELAY_MS);
            s_state = BLE_STATE_IDLE;
            vTaskDelay(pdMS_TO_TICKS(RECONNECT_DELAY_MS));
            start_scan();
            return 0;
        }
        s_conn_handle = event->connect.conn_handle;
        s_chr_val_handle = 0;
        s_cccd_handle    = 0;
        s_state = BLE_STATE_DISCOVERING;
        corelec_stream_init(&s_stream);

        ESP_LOGI(TAG, "Connecté (conn_handle=0x%04x) — découverte services",
                 s_conn_handle);
        rc = ble_gattc_disc_all_svcs(s_conn_handle, svc_disc_cb, NULL);
        if (rc != 0) {
            ESP_LOGE(TAG, "ble_gattc_disc_all_svcs: %d", rc);
            ble_gap_terminate(s_conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        }
        return 0;

    /* ── Déconnexion ───────────────────────────────────────────────────── */
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGW(TAG, "Déconnexion (raison=%d) → rescan dans %d ms",
                 event->disconnect.reason, RECONNECT_DELAY_MS);
        s_state = BLE_STATE_IDLE;
        s_conn_handle = BLE_HS_CONN_HANDLE_NONE;
        vTaskDelay(pdMS_TO_TICKS(RECONNECT_DELAY_MS));
        start_scan();
        return 0;

    /* ── Notification reçue ────────────────────────────────────────────── */
    case BLE_GAP_EVENT_NOTIFY_RX: {
        if (event->notify_rx.conn_handle != s_conn_handle) return 0;

        s_last_notify_us = esp_timer_get_time();

        /* Lire les octets reçus du mbuf */
        struct os_mbuf *om = event->notify_rx.om;
        uint8_t  chunk[128];
        uint16_t chunk_len = OS_MBUF_PKTLEN(om);
        if (chunk_len > sizeof(chunk)) chunk_len = sizeof(chunk);
        os_mbuf_copydata(om, 0, chunk_len, chunk);

        /* Alimenter le parseur de flux */
        corelec_frame_t frames[STREAM_MAX_FRAMES];
        int n = corelec_stream_feed(&s_stream, chunk, chunk_len,
                                    frames, STREAM_MAX_FRAMES);
        for (int i = 0; i < n; i++) {
            if (corelec_decode(&frames[i], &s_decoded)) {
                if (s_on_decoded) {
                    s_on_decoded(&s_decoded, s_user_ctx);
                }
            }
        }
        return 0;
    }

    /* ── Mise à jour des paramètres de connexion ───────────────────────── */
    case BLE_GAP_EVENT_CONN_UPDATE:
        return 0;

    default:
        return 0;
    }
}

/* ── Scan / connexion ────────────────────────────────────────────────────────*/

static void start_scan(void)
{
    s_state = BLE_STATE_SCANNING;
    struct ble_gap_disc_params params = {
        .itvl            = BLE_GAP_SCAN_ITVL_DEF,
        .window          = BLE_GAP_SCAN_WIN_DEF,
        .filter_policy   = BLE_HCI_SCAN_FILT_NO_WL,
        .limited         = 0,
        .passive         = 0,
        .filter_duplicates = 1,
    };
    int rc = ble_gap_disc(s_own_addr_type, BLE_HS_FOREVER, &params,
                          ble_gap_event_handler, NULL);
    if (rc != 0 && rc != BLE_HS_EALREADY) {
        ESP_LOGE(TAG, "ble_gap_disc: %d", rc);
    }
}

static void start_connecting(const ble_addr_t *addr)
{
    s_state = BLE_STATE_CONNECTING;

    /* Paramètres de connexion (valeurs par défaut ESP-IDF) */
    struct ble_gap_conn_params cp;
    ble_gap_conn_params_dflt(&cp);

    int rc = ble_gap_connect(s_own_addr_type, addr, 10000, &cp,
                             ble_gap_event_handler, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_gap_connect: %d", rc);
        s_state = BLE_STATE_IDLE;
        start_scan();
    }
}

/* ── Synchronisation du host ─────────────────────────────────────────────────*/

static void ble_on_sync(void)
{
    int rc = ble_hs_id_infer_auto(0, &s_own_addr_type);
    if (rc != 0) {
        ESP_LOGE(TAG, "ble_hs_id_infer_auto: %d", rc);
        return;
    }
    ESP_LOGI(TAG, "BLE stack prêt — démarrage scan (cible %02x:%02x:%02x:%02x:%02x:%02x)",
             s_target_addr[5], s_target_addr[4], s_target_addr[3],
             s_target_addr[2], s_target_addr[1], s_target_addr[0]);
    start_scan();
}

static void ble_on_reset(int reason)
{
    ESP_LOGW(TAG, "BLE reset (%d)", reason);
}

/* ── Tâche host NimBLE ───────────────────────────────────────────────────────*/

static void ble_host_task(void *param)
{
    (void)param;
    nimble_port_run();          /* bloque jusqu'à nimble_port_stop() */
    nimble_port_freertos_deinit();
}

/* ── Point d'entrée ──────────────────────────────────────────────────────────*/

void corelec_ble_init(const char *target_addr,
                      corelec_on_decoded_fn on_decoded, void *user_ctx)
{
    if (!parse_mac(target_addr, s_target_addr)) {
        ESP_LOGE(TAG, "Adresse MAC invalide : %s", target_addr);
        return;
    }
    s_on_decoded = on_decoded;
    s_user_ctx   = user_ctx;
    s_addr_random = false;   /* à surcharger si CONFIG_CORELEC_BLE_ADDR_TYPE_RANDOM */

    corelec_decoded_init(&s_decoded);
    corelec_stream_init(&s_stream);

    s_poll_sem = xSemaphoreCreateBinary();

    nimble_port_init();
    ble_hs_cfg.sync_cb  = ble_on_sync;
    ble_hs_cfg.reset_cb = ble_on_reset;
    ble_svc_gap_init();

    /* Tâche de polling (priorité basse, s'endort la plupart du temps) */
    xTaskCreate(poll_task, "corelec_poll", 4096, NULL, 3, &s_poll_task);

    /* Tâche host NimBLE */
    nimble_port_freertos_init(ble_host_task);
}
