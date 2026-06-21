# Corelec Ada Library

Bibliotheque Ada 2022 pour:
- la logique de cycle connexion/deconnexion/reconnexion BLE
- le parsing et le decodage des trames Corelec
- une API C-compatible pour integration avec d'autres runtimes

## Structure

- `alire.toml`: manifeste Alire
- `corelec_ada.gpr`: projet GPR de bibliotheque
- `include/corelec_ada.h`: header C public
- `src/`: packages Ada
- `examples/`: petit harness de decode

## Build

Avec Alire:

```powershell
cd src/Ada
alr build
```

Avec gprbuild:

```powershell
cd src/Ada
gprbuild -P corelec_ada.gpr
```

Exemple de build du harness:

```powershell
cd src/Ada
gprbuild -P examples/decode_smoke.gpr
```

## Notes

La partie BLE est implementee ici comme une machine d'etat et une API de service pilotable depuis un backend externe. Cela permet de brancher plus tard un backend BlueZ, ESP-IDF, NimBLE, ou autre stack embarquee sans changer les types C ni le decodeur.

## Recherche Alire

Les recherches Alire realisees pour `bluetooth`, `ble`, `bluez` et `winrt` n'ont retourne aucun crate Ada BLE directement exploitable.

Conclusion pratique :
- garder Ada pour la logique metier, l'etat de connexion et le decodeur
- brancher un backend BLE en C via une API stable

## Strategie portable recommandee

Il n'existe pas de backend BLE unique et vraiment optimal pour Windows, Raspberry Pi et ESP32 a la fois. La strategie la plus portable est donc une facade C commune avec implementations par plateforme.

Backends recommandes :
- Windows : shim C/C++ autour de WinRT Bluetooth LE
- Raspberry Pi / Linux : shim C autour de BlueZ (D-Bus/GATT)
- ESP32 : shim C autour de NimBLE dans ESP-IDF
- Option embarquee multi-cartes : BTstack en C si le materiel et le portage conviennent

Ordre de preference pour ce projet :
1. facade C commune `corelec_ble_backend_*`
2. BlueZ pour Raspberry Pi
3. WinRT shim pour Windows
4. NimBLE/ESP-IDF pour ESP32

## Pourquoi cette strategie

- Ada reste portable et stable
- les types et services exposes au C ne changent pas
- chaque plateforme peut utiliser la pile BLE la plus native et la plus fiable
- les microcontroleurs contraints evitent une dependance a une grosse runtime Ada pour la radio elle-meme

## Candidats C a utiliser

- BlueZ : reference Linux/Raspberry Pi, mature, standard
- NimBLE : tres bon choix embarque et ESP32
- BTstack : choix interessant si l'objectif est un coeur BLE plus unifie entre embarque et certaines plateformes host

## Recommandation finale

Pour maximiser la portabilite reelle :
- conserver `Corelec.Protocol`, `Corelec.Decoder`, `Corelec.Connection` en Ada
- ajouter une couche `Corelec.BLE` comme facade abstraite
- implementer des backends C separes par plateforme

Cette approche est plus robuste qu'essayer de forcer un unique package BLE Ada ou un unique runtime BLE C sur tous les OS et MCU.
