# CL Power Control

## Gestione intelligente dei carichi elettrici per Home Assistant

CL Power Control è una custom integration per Home Assistant dedicata al controllo automatico e prioritario dei carichi elettrici.

**Versione corrente: 0.2.6**

### Funzioni principali

- Dashboard automatica CL Power Control con branding CL Impianti.
- Potenza attuale, disponibile e sospesa.
- Grafico della potenza e storico dei distacchi.
- Controllo automatico dei carichi e gestione delle priorità.
- Priorità 1 = carico più importante: ultimo a essere distaccato e primo a essere riattivato.
- Accesso installatore temporaneo protetto da PIN salvato in forma hash.
- Configurazione guidata tramite config flow di Home Assistant.

## Installazione tramite HACS

1. Aprire **HACS**.
2. Selezionare **Custom repositories**.
3. Inserire `https://github.com/climpianti/CL-Power-Control`.
4. Selezionare **Category: Integration**.
5. Fare clic su **Download**.
6. Riavviare Home Assistant.
7. Aprire **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**.
8. Cercare **CL Power Control** e completare la configurazione.

## Installazione manuale

Copiare la cartella `custom_components/cl_power_control` nella directory `/config/custom_components/` di Home Assistant e riavviare completamente Home Assistant.
