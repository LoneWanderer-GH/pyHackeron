#ifndef CORELec_ADA_H
#define CORELec_ADA_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    CORELec_FRAME_LENGTH = 17,
    CORELec_ASK_LENGTH = 6,
    CORELec_MESSAGE_LENGTH = 128
};

typedef enum {
    CORELec_STATE_DISCONNECTED = 0,
    CORELec_STATE_CONNECTING = 1,
    CORELec_STATE_CONNECTED = 2,
    CORELec_STATE_ERROR = 3
} corelec_connection_state_t;

typedef enum {
    CORELec_KIND_UNKNOWN = 0,
    CORELec_KIND_65 = 1,
    CORELec_KIND_69 = 2,
    CORELec_KIND_77 = 3,
    CORELec_KIND_83 = 4
} corelec_decoded_kind_t;

typedef struct {
    uint8_t frame_type;
    uint8_t raw[CORELec_FRAME_LENGTH];
} corelec_frame_t;

typedef struct {
    corelec_decoded_kind_t kind;
    uint8_t frame_type;
    uint8_t valid;
    uint8_t raw[CORELec_FRAME_LENGTH];
    uint8_t has_ph;
    double ph;
    uint8_t has_redox;
    int redox;
    uint8_t has_temp;
    double temp;
    uint8_t has_sel;
    double sel;
    uint8_t has_ph_consigne;
    double ph_consigne;
    uint8_t has_err_max;
    double err_max;
    uint8_t has_err_min;
    double err_min;
    uint8_t has_redox_consigne;
    int redox_consigne;
    uint8_t has_boost_remaining_min;
    int boost_remaining_min;
    uint8_t has_current_electrolyse_percent;
    int current_electrolyse_percent;
    uint8_t has_cycle_period_min;
    int cycle_period_min;
    uint8_t has_shutter_mode_electrolyse_percent;
    int shutter_mode_electrolyse_percent;
    uint8_t has_cycle_a_min;
    int cycle_a_min;
    uint8_t has_cycle_b_min;
    int cycle_b_min;
    uint8_t alarme;
    uint8_t warning;
    uint8_t alarm_rdx;
    uint8_t pompe_moins_active;
    uint8_t regulation_active;
    uint8_t pompes_forcees;
    uint8_t boost_active;
    uint8_t flow_switch;
    uint8_t volet_actif;
    uint8_t volet_force;
} corelec_decoded_frame_t;

typedef struct {
    corelec_connection_state_t state;
    char message[CORELec_MESSAGE_LENGTH];
    unsigned elapsed;
    unsigned remaining;
    unsigned timeout;
    unsigned retry_count;
    uint8_t should_retry;
    uint8_t stop_requested;
} corelec_connection_info_t;

typedef struct corelec_connection_manager corelec_connection_manager_t;

corelec_connection_manager_t *corelec_connection_manager_create(unsigned timeout_seconds, unsigned initial_retry_count);
void corelec_connection_manager_destroy(corelec_connection_manager_t *handle);
void corelec_connection_manager_begin_connect(corelec_connection_manager_t *handle);
void corelec_connection_manager_tick_connecting(corelec_connection_manager_t *handle, unsigned elapsed_seconds);
void corelec_connection_manager_mark_connected(corelec_connection_manager_t *handle, unsigned elapsed_seconds);
void corelec_connection_manager_mark_error(corelec_connection_manager_t *handle, const char *message, unsigned elapsed_seconds);
void corelec_connection_manager_mark_disconnected(corelec_connection_manager_t *handle, const char *message);
void corelec_connection_manager_request_restart(corelec_connection_manager_t *handle);
void corelec_connection_manager_request_cancel(corelec_connection_manager_t *handle);
corelec_connection_info_t corelec_connection_manager_get_info(corelec_connection_manager_t *handle);

uint8_t corelec_crc_frame(const uint8_t raw[CORELec_FRAME_LENGTH], unsigned count);
void corelec_build_ask(uint8_t cmd, uint8_t out_packet[CORELec_ASK_LENGTH]);
int corelec_parse_frame(const uint8_t raw[CORELec_FRAME_LENGTH], corelec_frame_t *out_frame);
void corelec_decode_frame(const corelec_frame_t *frame, corelec_decoded_frame_t *out_decoded);

#ifdef __cplusplus
}
#endif

#endif
