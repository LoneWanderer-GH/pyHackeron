/**
 * main.c — Point d'entrée de l'application Corelec ESP32.
 *
 * Séquence d'initialisation :
 *   1. NVS flash
 *   2. esp_netif / event loop
 *   3. WiFi STA (SSID / mdp depuis menuconfig)
 *   4. Attente IP (événement IP_EVENT_STA_GOT_IP)
 *   5. MQTT (broker depuis menuconfig)
 *   6. BLE NimBLE → client GATT → polling
 *   7. Callback on_decoded → publication MQTT
 */
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "nvs_flash.h"

#include "corelec_ble.h"
#include "corelec_mqtt.h"
#include "corelec_types.h"

#include "sdkconfig.h"

static const char *TAG = "corelec_main";

/* ── WiFi ────────────────────────────────────────────────────────────────────*/

#define WIFI_CONNECTED_BIT  BIT0
#define WIFI_FAIL_BIT       BIT1

static EventGroupHandle_t s_wifi_event_group;

static void wifi_event_handler(void *arg,
                                esp_event_base_t base, int32_t id,
                                void *data)
{
    (void)arg; (void)data;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi déconnecté — reconnexion…");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = data;
        ESP_LOGI(TAG, "IP obtenue : " IPSTR, IP2STR(&ev->ip_info.ip));
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t inst_any, inst_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &inst_any));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &inst_ip));

    wifi_config_t wifi_cfg = {
        .sta = {
            .ssid     = CONFIG_CORELEC_WIFI_SSID,
            .password = CONFIG_CORELEC_WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());

    ESP_LOGI(TAG, "Connexion WiFi à « %s »…", CONFIG_CORELEC_WIFI_SSID);

    /* Attendre l'IP (indéfiniment, reconnexion automatique) */
    xEventGroupWaitBits(s_wifi_event_group,
                        WIFI_CONNECTED_BIT, pdFALSE, pdTRUE,
                        portMAX_DELAY);
}

/* ── Callback frames décodées ────────────────────────────────────────────────*/

static void on_decoded(const corelec_decoded_t *d, void *ctx)
{
    (void)ctx;
    corelec_mqtt_publish(d);
}

/* ── app_main ────────────────────────────────────────────────────────────────*/

void app_main(void)
{
    /* NVS — requis par WiFi */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    /* 1. WiFi → IP */
    wifi_init_sta();

    /* 2. MQTT */
    corelec_mqtt_init(CONFIG_CORELEC_MQTT_BROKER_URL);

    /* 3. BLE NimBLE */
    corelec_ble_init(CONFIG_CORELEC_BLE_DEVICE_ADDR, on_decoded, NULL);

    /* app_main peut revenir — les tâches FreeRTOS continuent */
    ESP_LOGI(TAG, "Corelec ESP32 démarré — BLE addr=%s MQTT=%s",
             CONFIG_CORELEC_BLE_DEVICE_ADDR,
             CONFIG_CORELEC_MQTT_BROKER_URL);
}
