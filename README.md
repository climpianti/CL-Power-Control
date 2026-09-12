# CL Power Control

Integrazione Home Assistant per la gestione intelligente e prioritaria dei carichi elettrici.

## Versione di test 0.3.0-beta.6

Questa beta è la build validata localmente prima della pubblicazione stabile 0.3.0.

### Funzioni principali

- Gestione automatica dei carichi in base alla potenza assorbita.
- Priorità configurabili: **Priorità 1 = carico più importante**, ultimo a essere distaccato e primo a essere riattivato.
- Dashboard dedicata CL Power Control.
- Modalità installatore protetta da PIN con sessione temporanea di 15 minuti.
- Configurazione avanzata dei carichi direttamente dalla dashboard.
- Selettori Home Assistant con ricerca per entità comando e sensore di potenza.
- Aggiunta e rimozione dei carichi dalla dashboard installatore.
- Test ON/OFF del singolo carico.
- Gestione per carico di auto-riattivazione, mai distaccabile, potenza minima attiva e potenza stimata.
- Soglie e temporizzazioni generali modificabili dalla dashboard installatore.
- Logo dashboard CL + telecamera a colori su sfondo trasparente.

## Installazione con HACS

Aggiungere come repository personalizzato:

`https://github.com/climpianti/CL-Power-Control`

Categoria: **Integration**.

Per testare una beta, abilitare le versioni prerelease in HACS e selezionare la release desiderata.

## Aggiornamento manuale

Sostituire la cartella:

`/config/custom_components/cl_power_control/`

con quella contenuta nel pacchetto e riavviare completamente Home Assistant.

## Nota

La serie 0.3.0-beta è destinata ai test. Per installazioni cliente definitive usare una release stabile.
