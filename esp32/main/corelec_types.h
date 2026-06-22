/**
 * corelec_types.h — Types partagés du protocole Corelec BLE.
 *
 * Format d'une trame : 17 octets
 *   [0]    sync start = 0x2A (42)
 *   [1]    type (65 / 69 / 77 / 83)
 *   [2-14] payload spécifique au type
 *   [15]   CRC = XOR des octets 0-14
 *   [16]   sync end = 0x2A (42)
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>

#define CORELEC_FRAME_LEN       17u
#define CORELEC_SYNC            0x2Au
#define CORELEC_FRAME_TYPE_65   65u
#define CORELEC_FRAME_TYPE_69   69u
#define CORELEC_FRAME_TYPE_77   77u
#define CORELEC_FRAME_TYPE_83   83u

/** Trame brute validée (sync + CRC). */
typedef struct {
    uint8_t raw[CORELEC_FRAME_LEN];
} corelec_frame_t;

/** Valeurs décodées — agrège tous les types de trame. */
typedef struct {
    /* --- Frame 77 : mesures temps réel --- */
    bool    has_ph;
    float   ph;                      /* ÷100 sur uint16 BE bytes[2-3] */
    bool    has_redox;
    int32_t redox;                   /* uint16 BE bytes[4-5] */
    bool    has_temp;
    float   temp;                    /* ÷10  sur uint16 BE bytes[6-7] */
    bool    has_sel;
    float   sel;                     /* ÷10  sur uint16 BE bytes[8-9] */
    uint8_t alarme;                  /* byte[10] */
    uint8_t warning;                 /* byte[11] & 0x0F */
    uint8_t alarm_rdx;               /* byte[11] >> 4  */
    bool    pompe_moins_active;      /* byte[12] bit6  */
    bool    regulation_active;       /* byte[12] bit5  */
    bool    config_capteur_sel_actif;/* byte[13] bit3  */
    bool    pompes_forcees;          /* byte[13] bit7  */

    /* --- Frame 83 : consignes pH --- */
    bool    has_ph_consigne;
    float   ph_consigne;             /* ÷100 sur uint16 BE bytes[2-3] */
    bool    has_err_max;
    float   err_max;                 /* ÷100 sur uint16 BE bytes[10-11] */
    bool    has_err_min;
    float   err_min;                 /* ÷100 sur uint16 BE bytes[12-13] */

    /* --- Frame 69 : consigne Redox --- */
    bool    has_redox_consigne;
    int32_t redox_consigne;          /* uint16 BE bytes[2-3] */

    /* --- Frame 65 : électrolyse --- */
    bool    has_elx;
    uint8_t current_electrolyse_percent; /* byte[2] */
    int32_t boost_remaining_min;     /* uint16 BE bytes[3-4] */
    bool    boost_active;
    int32_t inversion_period_min;    /* uint16 BE bytes[5-6] */
    int32_t inversion_timer_min;     /* uint16 BE bytes[7-8] */
    uint8_t shutter_mode_electrolyse_percent; /* byte[9] */
    bool    flow_switch;             /* (byte[10] & 0x60) == 0 */
    bool    volet_actif;             /* byte[10] bit4 */
    bool    volet_force;             /* byte[10] bit3 */
    uint8_t elx_fault_code;          /* byte[12] : 0=OK 7=flux 3=transitoire */
} corelec_decoded_t;

/** Callback appelé lors de la réception d'une trame valide décodée. */
typedef void (*corelec_on_decoded_fn)(const corelec_decoded_t *decoded, void *user_ctx);
