/**
 * corelec_decoder.h — Décodage des trames Corelec (65 / 69 / 77 / 83).
 */
#pragma once
#include "corelec_types.h"
#include <stdbool.h>

/**
 * Décode la trame brute raw et met à jour *out.
 *
 * Chaque appel ne modifie que les champs correspondant au type de trame :
 *   - type 77 : ph, redox, temp, sel, alarme, warning, pompes…
 *   - type 83 : ph_consigne, err_max, err_min
 *   - type 69 : redox_consigne
 *   - type 65 : électrolyse, boost, inversion, flow_switch…
 *
 * @return true si le type est connu et le décodage réussi.
 */
bool corelec_decode(const corelec_frame_t *frame, corelec_decoded_t *out);

/** Initialise tous les champs de *out à zéro / false. */
void corelec_decoded_init(corelec_decoded_t *out);
