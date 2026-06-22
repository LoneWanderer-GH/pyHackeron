/**
 * corelec_mqtt.h — Publication MQTT des valeurs décodées.
 *
 * Toutes les valeurs sont publiées sous le préfixe "corelec/" en QoS 0,
 * retained, au format texte décimal ou booléen ("0"/"1").
 */
#pragma once
#include "corelec_types.h"

/**
 * Initialise le client MQTT et connecte au broker.
 * Appeler une seule fois depuis app_main après que le WiFi est connecté.
 * @param broker_url  ex. "mqtt://192.168.1.100:1883"
 */
void corelec_mqtt_init(const char *broker_url);

/**
 * Publie tous les champs marqués has_* d'un frame décodé.
 * Sans effet si le client MQTT n'est pas encore connecté.
 */
void corelec_mqtt_publish(const corelec_decoded_t *d);

/** Publie un message de statut sur corelec/connection (connecté / déconnecté). */
void corelec_mqtt_publish_status(const char *msg);
