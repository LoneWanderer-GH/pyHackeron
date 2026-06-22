# Protocole BLE Corelec — Layout des trames

Référence de rétro-ingénierie du régulateur de piscine **Corelec**.  
Données collectées sur un appareil réel via BLE. Les informations marquées ❓ sont des hypothèses
ou restent inexpliquées — contributions bienvenues.

---

## Format général (17 octets, toutes trames)

```
 B0   B1   B2 … B14   B15   B16
 2A   TYP  <payload>   CRC   2A
```

| Octet | Rôle          | Valeur                                  |
|-------|---------------|-----------------------------------------|
| 0     | Sync start    | `0x2A` (42) — fixe                      |
| 1     | Type          | 65 / 69 / 77 / 83                       |
| 2–14  | Payload       | Spécifique au type (voir ci-dessous)    |
| 15    | CRC           | XOR de tous les octets 0–14             |
| 16    | Sync end      | `0x2A` (42) — fixe                      |

**Octet 14 — constante fixe par type** (❓ rôle inconnu) :  
vérifié sur >5000 trames que cette valeur ne varie jamais.  
Peut être un identifiant de sous-type, version de firmware, ou adresse de canal.

| Type | Octet 14 (hex) | Octet 14 (dec) |
|------|----------------|----------------|
| 65   | `0x49`         | 73             |
| 69   | `0x61`         | 97             |
| 77   | `0x82`         | 130            |
| 83   | `0x03`         | 3              |

**Polling** : l'hôte BLE demande chaque trame via une écriture GATT sur la caractéristique
`e7add780-b042-4876-aae1-112855353cc1`. Séquence : 77 → 83 → 65 → 69, toutes les ~2 s.

---

## Frame 77 — pH / Redox / Temp / Sel / Alarmes / Pompes

> Type byte : `0x4D` (77)

| Offset | Taille | Nom                    | Type        | Formule       | Statut | Notes                                         |
|--------|--------|------------------------|-------------|---------------|--------|-----------------------------------------------|
| 0      | 1      | sync                   | uint8       | —             | ✅     | `0x2A` fixe                                   |
| 1      | 1      | type                   | uint8       | —             | ✅     | `77`                                          |
| 2–3    | 2      | ph                     | uint16 BE   | ÷ 100         | ✅     | ex. `0x02BC` → 7.08                           |
| 4–5    | 2      | redox                  | uint16 BE   | valeur brute  | ✅     | mV, plage attendue 350–1000                   |
| 6–7    | 2      | temp                   | uint16 BE   | ÷ 10          | ✅     | °C, ex. `0x00F0` → 24.0°C                     |
| 8–9    | 2      | sel                    | uint16 BE   | ÷ 10          | ✅     | g/L                                           |
| 10     | 1      | alarme                 | uint8       | —             | ✅     | Code Exx affiché sur le contrôleur. 0 = OK    |
| 11     | 1      | warning / alarm_rdx    | uint8       | —             | ⚙️     | bits [7:4] = alarm_rdx, bits [3:0] = warning  |
| 12     | 1      | pump_flags             | bitfield    | —             | ⚙️     | voir détail bits ci-dessous                   |
| 13     | 1      | sensor_config_flags    | bitfield    | —             | ⚙️     | voir détail bits ci-dessous                   |
| 14     | 1      | frame_const            | uint8       | —             | ❓     | `0x82` — constante, rôle inconnu             |
| 15     | 1      | crc                    | uint8       | XOR(B0–B14)   | ✅     |                                               |
| 16     | 1      | sync end               | uint8       | —             | ✅     | `0x2A` fixe                                   |

### Détail bits — octet 12 `pump_flags`

| Bit | Masque | Nom                  | Statut | Notes                                                                                      |
|-----|--------|----------------------|--------|--------------------------------------------------------------------------------------------|
| 0   | `0x01` | ?                    | ❓     | Toujours 1 dans les données observées                                                      |
| 1   | `0x02` | ?                    | ❓     | Toujours 1 dans les données observées                                                      |
| 2   | `0x04` | ?                    | ❓     |                                                                                            |
| 3   | `0x08` | ?                    | ❓     |                                                                                            |
| 4   | `0x10` | ?                    | ❓     |                                                                                            |
| 5   | `0x20` | `regulation_active`  | ✅     | 0 quand écoulement coupé **ou** quand `pompes_forcees` actif                               |
| 6   | `0x40` | `pompe_moins_active` | ✅     | 1 = pompe pH− en cours (mode AUTO uniquement). Toujours 0 en mode forcé                   |
| 7   | `0x80` | ?                    | ❓     |                                                                                            |

### Détail bits — octet 13 `sensor_config_flags`

| Bit | Masque | Nom                         | Statut | Notes                                                                                |
|-----|--------|-----------------------------|--------|--------------------------------------------------------------------------------------|
| 0   | `0x01` | ?                           | ❓     | Observé à 1 dans la valeur de base `0x11`                                            |
| 1   | `0x02` | ?                           | ❓     |                                                                                      |
| 2   | `0x04` | ?                           | ❓     |                                                                                      |
| 3   | `0x08` | `config_capteur_sel_actif`  | ✅     | 1 = capteur SEL activé. Observé : `0x19` → `0x11` lors de la désactivation          |
| 4   | `0x10` | ?                           | ❓     | Observé à 1 dans la valeur de base `0x11`                                            |
| 5   | `0x20` | ?                           | ❓     |                                                                                      |
| 6   | `0x40` | ?                           | ❓     |                                                                                      |
| 7   | `0x80` | `pompes_forcees`            | ✅     | 1 = forçage manuel actif. `0x11` → `0x91` lors du forçage pompe pH− pendant ~1 min  |

---

## Frame 65 — Électrolyse / Boost / Inversion de polarité / Volet / Flow

> Type byte : `0x41` (65)

| Offset | Taille | Nom                    | Type        | Formule      | Statut | Notes                                                        |
|--------|--------|------------------------|-------------|--------------|--------|--------------------------------------------------------------|
| 0      | 1      | sync                   | uint8       | —            | ✅     | `0x2A` fixe                                                  |
| 1      | 1      | type                   | uint8       | —            | ✅     | `65`                                                         |
| 2      | 1      | electrolyse            | uint8       | %            | ✅     | Puissance d'électrolyse courante (0–100 %)                   |
| 3–4    | 2      | boost_remain           | uint16 BE   | minutes      | ✅     | 0 = pas de boost. Confirmé : 6 h = 360 = `0x0168`           |
| 5–6    | 2      | inversion_period       | uint16 BE   | minutes      | ✅     | Période configurée d'inversion de polarité. Défaut : 240 min |
| 7–8    | 2      | inversion_timer        | uint16 BE   | minutes      | ✅     | Compteur écoulé dans le cycle d'inversion courant            |
| 9      | 1      | shutter_mode           | uint8       | %            | ✅     | Consigne volet (shutter_mode_electrolyse_percent)            |
| 10     | 1      | io_flags               | bitfield    | —            | ⚙️     | voir détail bits ci-dessous                                  |
| 11     | 1      | ?                      | uint8       | —            | ❓     | Inconnu — varie                                              |
| 12     | 1      | elx_fault_code         | uint8       | —            | ✅     | 0=normal, 3=transitoire, 7=arrêt défaut flux                 |
| 13     | 1      | ?                      | uint8       | —            | ❓     | Inconnu — varie                                              |
| 14     | 1      | frame_const            | uint8       | —            | ❓     | `0x49` — constante, rôle inconnu                            |
| 15     | 1      | crc                    | uint8       | XOR(B0–B14)  | ✅     |                                                              |
| 16     | 1      | sync end               | uint8       | —            | ✅     | `0x2A` fixe                                                  |

### Détail bits — octet 10 `io_flags`

| Bit  | Masque | Nom           | Statut | Notes                                                                          |
|------|--------|---------------|--------|--------------------------------------------------------------------------------|
| 0    | `0x01` | ?             | ❓     |                                                                                |
| 1    | `0x02` | ?             | ❓     |                                                                                |
| 2    | `0x04` | ?             | ❓     | Toujours 1 dans les données observées                                          |
| 3    | `0x08` | `volet_force` | ⚙️     | Hypothèse : volet en position forcée. Non vérifié expérimentalement            |
| 4    | `0x10` | `volet_actif` | ⚙️     | Hypothèse : volet actif. Non vérifié expérimentalement                         |
| 5    | `0x20` | `flow_alarm`  | ✅     | bits 5+6 simultanément à 1 = alarme défaut écoulement (+ `elx_fault_code`=7)  |
| 6    | `0x40` | `flow_alarm`  | ✅     | (idem bit 5 — les deux passent ensemble)                                       |
| 7    | `0x80` | ?             | ❓     |                                                                                |

---

## Frame 83 — Consigne pH / Plages d'erreur

> Type byte : `0x53` (83)

| Offset | Taille | Nom          | Type       | Formule     | Statut | Notes                                            |
|--------|--------|--------------|------------|-------------|--------|--------------------------------------------------|
| 0      | 1      | sync         | uint8      | —           | ✅     | `0x2A` fixe                                      |
| 1      | 1      | type         | uint8      | —           | ✅     | `83`                                             |
| 2–3    | 2      | ph_consigne  | uint16 BE  | ÷ 100       | ✅     | ex. `0x02BC` → 7.08                              |
| 4      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 5      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 6      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 7      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 8      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 9      | 1      | ?            | uint8      | —           | ❓     | Inconnu                                          |
| 10–11  | 2      | err_max      | uint16 BE  | ÷ 100       | ✅     | Seuil haut de la plage de tolérance pH           |
| 12–13  | 2      | err_min      | uint16 BE  | ÷ 100       | ✅     | Seuil bas de la plage de tolérance pH            |
| 14     | 1      | frame_const  | uint8      | —           | ❓     | `0x03` — constante, rôle inconnu                |
| 15     | 1      | crc          | uint8      | XOR(B0–B14) | ✅     |                                                  |
| 16     | 1      | sync end     | uint8      | —           | ✅     | `0x2A` fixe                                      |

> **Hypothèse octets 4–9** : ces 6 octets pourraient contenir les paramètres de régulation pH
> (gain, bande morte, temps d'impulsion pompe…). La trame 83 ne varie quasiment pas entre
> sessions — une corrélation avec les réglages menu du régulateur serait nécessaire.

---

## Frame 69 — Consigne Redox

> Type byte : `0x45` (69)

| Offset | Taille | Nom              | Type       | Formule     | Statut | Notes                                                 |
|--------|--------|------------------|------------|-------------|--------|-------------------------------------------------------|
| 0      | 1      | sync             | uint8      | —           | ✅     | `0x2A` fixe                                           |
| 1      | 1      | type             | uint8      | —           | ✅     | `69`                                                  |
| 2–3    | 2      | redox_consigne   | uint16 BE  | valeur brute| ✅     | mV. Même format que le champ `redox` de la trame 77  |
| 4      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 5      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 6      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 7      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 8      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 9      | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 10     | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 11     | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 12     | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 13     | 1      | ?                | uint8      | —           | ❓     | Inconnu                                               |
| 14     | 1      | frame_const      | uint8      | —           | ❓     | `0x61` — constante, rôle inconnu                     |
| 15     | 1      | crc              | uint8      | XOR(B0–B14) | ✅     |                                                       |
| 16     | 1      | sync end         | uint8      | —           | ✅     | `0x2A` fixe                                           |

> **Hypothèse octets 4–13** : symétrie probable avec la trame 83 (consigne pH). Les octets 4–9
> pourraient contenir les paramètres de régulation Redox (gain, temps d'injection, bande morte…).
> Les octets 10–13 pourraient être des seuils d'erreur analogues à `err_max`/`err_min` de la
> trame 83, mais en mV (sans ÷100). Nécessite des mesures avec plusieurs configurations Redox.

---

## Récapitulatif de couverture

| Trame | Octets connus | Octets inconnus | Couverture |
|-------|---------------|-----------------|------------|
| 77    | 14 / 17       | 3 (bits dans B12/B13, B14) | ~82 % |
| 65    | 13 / 17       | 4 (B11, B13, B14, bits B10) | ~76 % |
| 83    | 9 / 17        | 8 (B4–B9, B14)  | ~53 %      |
| 69    | 4 / 17        | 13 (B4–B13, B14)| ~24 %      |

---

## Méthode de rétro-ingénierie

Le panneau **Rétro-ingénierie** de l'UI permet de :
1. Sélectionner un ou deux octets adjacents (clic ou shift+clic dans la table)
2. Cliquer droit → interpréter comme `uint16 BE/LE`, `int16`, `float16`, ASCII, bitmask
3. Cocher « Plot » pour tracer la valeur dans le graphe libre en fonction du temps

### Approche recommandée pour les octets inconnus

1. **Corréler avec les actions menu** — changer un paramètre dans le menu du régulateur
   et observer quel octet change dans les trames suivantes.
2. **Comparer Frame 69 et Frame 83** — ces deux trames ont une structure très similaire
   (consigne en B2-B3, constante en B14, CRC en B15) ; les octets 4–13 pourraient suivre
   le même pattern (paramètres de régulation + seuils).
3. **Hypothèse frame_const (B14)** — essayer d'envoyer une trame modifiée sans ce byte
   pour voir si le régulateur accepte la commande (requiert reverse de la direction montante).

### Outils disponibles dans le repo

```
corelec/ReverseEngineering/ctypes_frames.py   Structures ctypes par type de trame
corelec/UI/reverse_ui.py                       Panneau RE (table, graphe, interprétations)
corelec/Analyse/database.py                    Accès SQLite — raw_frames + decoded_frames
```

Pour analyser en masse depuis la base existante :
```python
import sqlite3
conn = sqlite3.connect("pool.db")
# Toutes les trames 69 (consigne Redox) — octets en colonne
rows = conn.execute(
    "SELECT frame_hex FROM raw_frames WHERE frame_type=69 ORDER BY id DESC LIMIT 500"
).fetchall()
for (h,) in rows[:5]:
    b = bytes.fromhex(h)
    print(" ".join(f"B{i}={b[i]:3d}(0x{b[i]:02X})" for i in range(17)))
```
