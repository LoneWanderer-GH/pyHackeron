/**
 * corelec_decoder.c — Décodage des trames Corelec.
 *
 * Layouts vérifiés avec ctypes_frames.py (source de vérité Python) :
 *
 *   Frame 77 (mesures) :
 *     bytes[2-3]  ph           uint16 BE  ÷100
 *     bytes[4-5]  redox        uint16 BE
 *     bytes[6-7]  temp         uint16 BE  ÷10
 *     bytes[8-9]  sel          uint16 BE  ÷10
 *     byte[10]    alarme
 *     byte[11]    warning[3:0] | alarm_rdx[7:4]
 *     byte[12]    pump_flags   bit6=pompe_moins_active  bit5=regulation_active
 *     byte[13]    sensor_flags bit3=config_capteur_sel_actif  bit7=pompes_forcees
 *
 *   Frame 83 (consignes pH) :
 *     bytes[2-3]  ph_consigne  uint16 BE  ÷100
 *     bytes[10-11] err_max     uint16 BE  ÷100
 *     bytes[12-13] err_min     uint16 BE  ÷100
 *
 *   Frame 69 (consigne Redox) :
 *     bytes[2-3]  redox_consigne uint16 BE
 *
 *   Frame 65 (électrolyse) :
 *     byte[2]      electrolyse_percent
 *     bytes[3-4]   boost_remaining_min  uint16 BE
 *     bytes[5-6]   inversion_period_min uint16 BE
 *     bytes[7-8]   inversion_timer_min  uint16 BE
 *     byte[9]      shutter_mode_electrolyse_percent
 *     byte[10]     io_flags  bit4=volet_actif  bit3=volet_force  bits5+6=flux alarm
 *     byte[12]     elx_fault_code  (0=OK 7=arrêt flux 3=transitoire)
 *     flow_switch = (io_flags & 0x60) == 0
 */
#include "corelec_decoder.h"
#include <string.h>

/* Lecture uint16 big-endian */
static inline uint16_t u16be(const uint8_t *p)
{
    return (uint16_t)((p[0] << 8) | p[1]);
}

void corelec_decoded_init(corelec_decoded_t *out)
{
    memset(out, 0, sizeof(*out));
}

bool corelec_decode(const corelec_frame_t *frame, corelec_decoded_t *out)
{
    if (!frame || !out) return false;
    const uint8_t *r = frame->raw;   /* raccourci */
    uint8_t type = r[1];

    switch (type) {

    /* ── Trame 77 : mesures temps réel ──────────────────────────────────── */
    case CORELEC_FRAME_TYPE_77: {
        uint16_t raw_ph   = u16be(&r[2]);
        uint16_t raw_rdx  = u16be(&r[4]);
        uint16_t raw_temp = u16be(&r[6]);
        uint16_t raw_sel  = u16be(&r[8]);

        float ph   = raw_ph   / 100.0f;
        float temp = raw_temp / 10.0f;
        float sel  = raw_sel  / 10.0f;

        out->has_ph   = (ph   >= 3.5f && ph   <= 9.5f);
        out->ph       = ph;
        out->has_redox = (raw_rdx >= 350 && raw_rdx <= 1000);
        out->redox    = (int32_t)raw_rdx;
        out->has_temp = (temp >= 0.0f && temp <= 50.0f);
        out->temp     = temp;
        out->has_sel  = (sel >= 0.0f && sel <= 10.0f);
        out->sel      = sel;

        out->alarme           = r[10];
        out->warning          = r[11] & 0x0Fu;
        out->alarm_rdx        = r[11] >> 4;
        out->pompe_moins_active      = (r[12] & (1u << 6)) != 0;
        out->regulation_active        = (r[12] & (1u << 5)) != 0;
        out->config_capteur_sel_actif = (r[13] & (1u << 3)) != 0;
        out->pompes_forcees           = (r[13] & (1u << 7)) != 0;
        return true;
    }

    /* ── Trame 83 : consignes pH ─────────────────────────────────────────── */
    case CORELEC_FRAME_TYPE_83:
        out->has_ph_consigne = true;
        out->ph_consigne     = u16be(&r[2]) / 100.0f;
        out->has_err_max     = true;
        out->err_max         = u16be(&r[10]) / 100.0f;
        out->has_err_min     = true;
        out->err_min         = u16be(&r[12]) / 100.0f;
        return true;

    /* ── Trame 69 : consigne Redox ───────────────────────────────────────── */
    case CORELEC_FRAME_TYPE_69:
        out->has_redox_consigne = true;
        out->redox_consigne     = (int32_t)u16be(&r[2]);
        return true;

    /* ── Trame 65 : électrolyse / boost / volet ─────────────────────────── */
    case CORELEC_FRAME_TYPE_65: {
        out->has_elx = true;
        out->current_electrolyse_percent    = r[2];
        out->boost_remaining_min            = (int32_t)u16be(&r[3]);
        out->boost_active                   = out->boost_remaining_min > 0;
        out->inversion_period_min           = (int32_t)u16be(&r[5]);
        out->inversion_timer_min            = (int32_t)u16be(&r[7]);
        out->shutter_mode_electrolyse_percent = r[9];
        uint8_t io = r[10];
        out->flow_switch   = (io & 0x60u) == 0u;
        out->volet_actif   = (io & (1u << 4)) != 0;
        out->volet_force   = (io & (1u << 3)) != 0;
        out->elx_fault_code = r[12];
        return true;
    }

    default:
        return false;
    }
}
