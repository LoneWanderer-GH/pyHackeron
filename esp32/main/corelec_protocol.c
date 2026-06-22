/**
 * corelec_protocol.c — Implémentation du CRC, parsing et ASK.
 */
#include "corelec_protocol.h"
#include <string.h>
#include <assert.h>

/* ── CRC ────────────────────────────────────────────────────────────────────*/

uint8_t corelec_crc(const uint8_t *data, size_t len)
{
    uint8_t c = 0;
    for (size_t i = 0; i < len; i++) {
        c ^= data[i];
    }
    return c;
}

/* ── Validation de trame ────────────────────────────────────────────────────*/

bool corelec_parse_frame(const uint8_t *buf, corelec_frame_t *out)
{
    if (!buf || !out) return false;
    if (buf[0] != CORELEC_SYNC) return false;
    if (buf[CORELEC_FRAME_LEN - 1] != CORELEC_SYNC) return false;
    /* CRC = XOR octets 0-14, stocké en [15] */
    if (corelec_crc(buf, 15) != buf[15]) return false;
    memcpy(out->raw, buf, CORELEC_FRAME_LEN);
    return true;
}

/* ── Construction des paquets ASK ───────────────────────────────────────────*/

void corelec_build_ask(uint8_t cmd, uint8_t out[CORELEC_ASK_LEN])
{
    out[0] = 0x2A;
    out[1] = 0x52;
    out[2] = 0x3F;
    out[3] = cmd;
    out[4] = corelec_crc(out, 4);   /* XOR des octets 0-3 */
    out[5] = 0x2A;
}

/* ── Parseur de flux fragmenté ──────────────────────────────────────────────*/

void corelec_stream_init(corelec_stream_t *s)
{
    s->len = 0;
}

int corelec_stream_feed(corelec_stream_t *s,
                        const uint8_t   *data, size_t data_len,
                        corelec_frame_t *frames, int max_frames)
{
    /* Eviter débordement */
    size_t space = CORELEC_STREAM_BUF_LEN - s->len;
    if (data_len > space) data_len = space;
    memcpy(s->buf + s->len, data, data_len);
    s->len += data_len;

    int found = 0;

    while (found < max_frames) {
        if (s->len < CORELEC_FRAME_LEN) break;

        /* Chercher le prochain octet sync 0x2A */
        size_t start = (size_t)-1;
        for (size_t i = 0; i < s->len; i++) {
            if (s->buf[i] == CORELEC_SYNC) { start = i; break; }
        }
        if (start == (size_t)-1) {
            s->len = 0;
            break;
        }
        if (start + CORELEC_FRAME_LEN > s->len) break;

        const uint8_t *candidate = s->buf + start;

        if (candidate[CORELEC_FRAME_LEN - 1] == CORELEC_SYNC) {
            if (corelec_parse_frame(candidate, &frames[found])) {
                found++;
            }
            /* Consommer les 17 octets même si le CRC est mauvais */
            size_t consumed = start + CORELEC_FRAME_LEN;
            memmove(s->buf, s->buf + consumed, s->len - consumed);
            s->len -= consumed;
        } else {
            /* Sync de fin absent : avancer d'un octet pour éviter boucle infinie */
            size_t skip = start + 1;
            memmove(s->buf, s->buf + skip, s->len - skip);
            s->len -= skip;
        }
    }

    return found;
}
