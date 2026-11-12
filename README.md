# CL Power Control

Integrazione Home Assistant per la gestione intelligente e prioritaria dei carichi elettrici, con supporto a fotovoltaico, rete e batteria.

## Beta 0.4.1-beta.1: riconoscimento SENEC / Solarman

La beta aggiunge in **Impostazioni installatore → Rileva automaticamente SENEC / Solarman** una scansione locale del registro entità e dei sensori disponibili. Riconosce singolarmente sensori W/kW di casa, rete bidirezionale, FV, batteria e SOC; propone solo sensori con unità compatibili appartenenti alla stessa integrazione/dispositivo. **È necessario il PIN installatore e confermare il salvataggio.** Il riconoscimento non abilita da solo Energy Control o Power Control, non modifica soglie, distacchi o PIN. Le associazioni già valide sono mantenute, salvo l'esplicita scelta di sostituirle; quelle circolari verso CL Power Control vengono corrette solo con conferma dell'installatore.

**SENEC:** rileva `senec_house_power`, `senec_grid_state_power`, `senec_solar_generated_power`, `senec_battery_state_power`, `senec_battery_charge_percent`. La direzione SENEC di rete nota è positiva quando si preleva; l'inversione viene disabilitata quando si associa questo sensore, ma la convenzione batteria deve essere verificata dall'installatore.

**Solarman:** identifica i sensori disponibili attraverso la piattaforma dell'integrazione e le denominazioni normalizzate; esclude sensori per singola fase, MPPT, import-only ed export-only dalla rete bidirezionale. In assenza di un sensore di rete bidirezionale non lo inventa. Chiede di verificare il segno sul campo. Le unità kW vengono convertite in W in fase di lettura dal motore.

**Sicurezza:** nessun sensore `sensor.cl_power_control_*` può essere selezionato come origine, prevenendo riferimenti circolari. Tutti i dati energetici sono letti senza modificare entità o impostazioni di Home Assistant.

## Versione stabile 0.4.0

La 0.4.0 promuove a stabile il ramo sviluppato e validato fino alla `0.4.0-beta.5`.

### Funzioni principali

- Gestione automatica dei carichi in base alla potenza disponibile.
- Priorità configurabili: **Priorità 1 = carico più importante**, ultimo a essere distaccato e primo a essere riattivato.
- Supporto comandi per `switch`, `light` e `climate`.
- Ripristino della modalità HVAC dopo un distacco Power Control.
- Dashboard dedicata con sezioni Panoramica, Power Control, Energy Control e Installatore.
- Modalità installatore protetta da PIN con sessione temporanea di 15 minuti.
- Configurazione avanzata dei carichi direttamente dalla dashboard e dalle opzioni integrazione.
- Storico persistente degli interventi di distacco e riattivazione.
- Preavviso cliente con notifiche Home Assistant Companion prima del distacco.
- Energy Control con sensori di rete, fotovoltaico, batteria e SOC.
- Calcolo di consumo casa, import/export rete, surplus, carica/scarica batteria e margine contatore.
- Modalità **Compensa Power Control con rete/FV**: il controllo può usare lo scambio reale con la rete come riferimento, permettendo alla produzione locale di aumentare dinamicamente la potenza utilizzabile senza superare il limite configurato del contatore.
- Sensori dedicati per potenza di controllo, limite dinamico equivalente e margine disponibile.
- Classificazione dei carichi energetici: Normale, Flessibile e Solo surplus.
- Predisposizione delle azioni energetiche per ON/OFF, Climate comfort, aumento temperatura e carico ausiliario.

> Le azioni automatiche Energy Control sui carichi flessibili/surplus restano separate dal motore Power Control e saranno abilitate solo dopo la relativa logica di sicurezza e stabilizzazione.

## Installazione con HACS

Aggiungere come repository personalizzato:

`https://github.com/climpianti/CL-Power-Control`

Categoria: **Integration**.

Dopo il download, riavviare Home Assistant e aggiungere l'integrazione da **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL Power Control**.

## Aggiornamento manuale

Sostituire la cartella:

`/config/custom_components/cl_power_control/`

con quella contenuta nel pacchetto e riavviare completamente Home Assistant.

## Architettura

CL Power Control rimane il backend tecnico per:

- gestione priorità e distacchi;
- compensazione rete/FV;
- sensori e metriche energetiche;
- storico tecnico degli interventi.

La presentazione utente finale più evoluta delle statistiche energetiche può essere realizzata da **CL Control**, usando le entità esposte da CL Power Control e le statistiche native di Home Assistant.
