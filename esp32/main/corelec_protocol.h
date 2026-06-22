/**
 * corelec_protocol.h — CRC, validation de trame, construction des paquets ASK,
 *                      parseur de flux BLE fragmenté.
 */
#pragma once
#include "corelec_types.h"
#include <stddef.h>

/* ── CRC ────────────────────────────────────────────────────────────────────*/

/** XOR de tous les octets de data[0..len-1]. */
uint8_t corelec_crc(const uint8_t *data, size_t len);

/* ── Validation de trame ────────────────────────────────────────────────────*/

/**
 * Valide buf[0..16] : sync, CRC, sync.
 * @return true si la trame est valide et copie les 17 octets dans *out.
 */
bool corelec_parse_frame(const uint8_t *buf, corelec_frame_t *out);

/* ── Construction des paquets ASK ───────────────────────────────────────────*/

#define CORELEC_ASK_LEN 6u

/**
 * Construit le paquet ASK pour la commande cmd.
 * Format : [0x2A, 0x52, 0x3F, cmd, XOR(0-3), 0x2A]
 */
void corelec_build_ask(uint8_t cmd, uint8_t out[CORELEC_ASK_LEN]);

/* ── Parseur de flux fragmenté ──────────────────────────────────────────────*/

#define CORELEC_STREAM_BUF_LEN 256u

typedef struct {
    uint8_t buf[CORELEC_STREAM_BUF_LEN];
    size_t  len;
} corelec_stream_t;

/** Initialise le parseur (met len à 0). */
void corelec_stream_init(corelec_stream_t *s);

/**
 * Alimente le parseur avec data[0..data_len-1].
 * Remplit frames[] avec les trames trouvées (jusqu'à max_frames).
 * @return nombre de trames trouvées.
 */
int corelec_stream_feed(corelec_stream_t *s,
                        const uint8_t   *data, size_t data_len,
                        corelec_frame_t *frames, int max_frames);
