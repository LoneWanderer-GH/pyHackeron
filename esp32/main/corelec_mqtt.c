/**
 * corelec_mqtt.c — Client MQTT pour l'ESP32.
 *
 * Topics publiés (QoS 0, retained) :
 *   corelec/connection         "connected" | "disconnected"
 *   corelec/ph                 float, ex. "7.25"
 *   corelec/redox              int,   ex. "720"
 *   corelec/temp               float, ex. "26.4"
 *   corelec/sel                float, ex. "4.1"
 *   corelec/alarme             uint, ex. "0"
 *   corelec/warning            uint
 *   corelec/alarm_rdx          uint
 *   corelec/pompe_moins_active "0" | "1"
 *   corelec/regulation_active  "0" | "1"
 *   corelec/config_capteur_sel_actif "0" | "1"
 *   corelec/pompes_forcees     "0" | "1"
 *   corelec/ph_consigne        float
 *   corelec/err_max            float
 *   corelec/err_min            float
 *   corelec/redox_consigne     int
 *   corelec/current_electrolyse_percent uint
 *   corelec/boost_remaining_min         int
 *   corelec/boost_active       "0" | "1"
 *   corelec/inversion_period_min        int
 *   corelec/inversion_timer_min         int
 *   corelec/flow_switch        "0" | "1"
 *   corelec/volet_actif        "0" | "1"
 *   corelec/volet_force        "0" | "1"
 *   corelec/elx_fault_code     uint
 */
#include "corelec_mqtt.h"
#include "mqtt_client.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>
#include <stdatomic.h>

static const char *TAG = "corelec_mqtt";

static esp_mqtt_client_handle_t s_client = NULL;
static atomic_bool s_connected = ATOMIC_VAR_INIT(false);

/* ── Handlers d'événements ──────────────────────────────────────────────────*/

static void mqtt_event_handler(void *arg,
                                esp_event_base_t base,
                                int32_t event_id,
                                void *event_data)
{
    (void)arg; (void)base;
    esp_mqtt_event_handle_t ev = event_data;
    switch (event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Connecté au broker MQTT");
        atomic_store(&s_connected, true);
        corelec_mqtt_publish_status("connected");
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Déconnecté du broker MQTT");
        atomic_store(&s_connected, false);
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "Erreur MQTT");
        break;
    default:
        break;
    }
    (void)ev;
}

/* ── Initialisation ─────────────────────────────────────────────────────────*/

void corelec_mqtt_init(const char *broker_url)
{
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = broker_url,
    };
    s_client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID,
                                   mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_client);
}

/* ── Publication ────────────────────────────────────────────────────────────*/

static void pub(const char *topic, const char *payload)
{
    if (!atomic_load(&s_connected)) return;
    esp_mqtt_client_publish(s_client, topic, payload, 0,
                            /* qos */ 0, /* retain */ 1);
}

static void pub_f(const char *topic, float v, int decimals)
{
    char buf[32];
    snprintf(buf, sizeof(buf), "%.*f", decimals, (double)v);
    pub(topic, buf);
}

static void pub_i(const char *topic, int32_t v)
{
    char buf[16];
    snprintf(buf, sizeof(buf), "%" PRId32, v);
    pub(topic, buf);
}

static void pub_b(const char *topic, bool v)
{
    pub(topic, v ? "1" : "0");
}

void corelec_mqtt_publish_status(const char *msg)
{
    pub("corelec/connection", msg);
}

void corelec_mqtt_publish(const corelec_decoded_t *d)
{
    if (!d) return;

    /* Frame 77 */
    if (d->has_ph)    pub_f("corelec/ph",   d->ph,   2);
    if (d->has_redox) pub_i("corelec/redox", d->redox);
    if (d->has_temp)  pub_f("corelec/temp",  d->temp, 1);
    if (d->has_sel)   pub_f("corelec/sel",   d->sel,  1);

    /* Alarmes/pompes publiées dès qu'une frame 77 a été reçue */
    if (d->has_ph || d->has_redox) {
        pub_i("corelec/alarme",   (int32_t)d->alarme);
        pub_i("corelec/warning",  (int32_t)d->warning);
        pub_i("corelec/alarm_rdx",(int32_t)d->alarm_rdx);
        pub_b("corelec/pompe_moins_active",       d->pompe_moins_active);
        pub_b("corelec/regulation_active",         d->regulation_active);
        pub_b("corelec/config_capteur_sel_actif",  d->config_capteur_sel_actif);
        pub_b("corelec/pompes_forcees",            d->pompes_forcees);
    }

    /* Frame 83 */
    if (d->has_ph_consigne) pub_f("corelec/ph_consigne", d->ph_consigne, 2);
    if (d->has_err_max)     pub_f("corelec/err_max",     d->err_max,     2);
    if (d->has_err_min)     pub_f("corelec/err_min",     d->err_min,     2);

    /* Frame 69 */
    if (d->has_redox_consigne) pub_i("corelec/redox_consigne", d->redox_consigne);

    /* Frame 65 */
    if (d->has_elx) {
        pub_i("corelec/current_electrolyse_percent",
              (int32_t)d->current_electrolyse_percent);
        pub_i("corelec/boost_remaining_min",  d->boost_remaining_min);
        pub_b("corelec/boost_active",         d->boost_active);
        pub_i("corelec/inversion_period_min", d->inversion_period_min);
        pub_i("corelec/inversion_timer_min",  d->inversion_timer_min);
        pub_b("corelec/flow_switch",          d->flow_switch);
        pub_b("corelec/volet_actif",          d->volet_actif);
        pub_b("corelec/volet_force",          d->volet_force);
        pub_i("corelec/elx_fault_code",       (int32_t)d->elx_fault_code);
    }
}
