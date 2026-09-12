# Changelog

## 0.3.0-beta.6
- Ripristinato un campo Nome carico sempre visibile e affidabile nella card installatore.
- Il nome viene anche proposto automaticamente dal friendly name dell'entità comando selezionata.
- Corretto il selettore di rimozione carico usando un controllo affidabile e conferma esplicita.
- Aggiornamento automatico della dashboard dopo aggiunta o rimozione.
- Mantenuti i selettori entità Home Assistant con ricerca per comando e sensore potenza.

## 0.3.0-beta.5
- Fixed the custom load-manager card not loading and showing "Errore di configurazione".
- Frontend module is now registered through Home Assistant frontend module manager instead of writing Lovelace resource storage directly.
- Added cache-busting for the beta.5 frontend module.

## 0.3.0-beta.4
- Replaced dashboard add/remove load helpers with a dedicated CL Power Control custom card.
- Added native Home Assistant entity selectors with search for command entities and power sensors.
- Added direct backend add/remove services protected by the active installer session.
- Added confirmation dialog before removing a load.
- Kept existing load configuration controls and local test workflow.

## 0.3.0-beta.3
- Fixed dashboard add/remove controls remaining unavailable after installer unlock.
- Added command entity and power sensor selectors while creating a new load from the dashboard.
- Fixed remove-load button availability and confirmation flow.
- Load management in Home Assistant integration options is now directly accessible to administrators without an extra installer PIN.
- Advanced installer options reuse the shared 15-minute installer session opened from the dashboard or options flow.
- Kept the color transparent CL + camera dashboard logo.

## 0.3.0-beta.2
- Added installer dashboard controls to add a new load without leaving the dashboard.
- Added installer dashboard selector and protected two-step removal flow for existing loads.
- Added load-management status feedback.
- Kept the color transparent CL + camera dashboard header logo.

## 0.3.0-beta.1 (local test build)
- Extended installer configuration directly from the dashboard.
- Added editable global thresholds and timing parameters.
- Added per-load enable, auto-restart and never-shed controls.
- Added per-load minimum active power and estimated power controls.
- Added installer-only Test ON / Test OFF buttons.
- Replaced the dashboard header with the colored CL + camera logo on a transparent background, without the IMPIANTI wordmark, sized to the existing header.
- Preserved existing load IDs and integration compatibility where possible.

## 0.2.6
- Fixed installer PIN field being rendered non-editable in Lovelace.
- PIN input now permits an empty native state while keeping the actual PIN only in coordinator memory.
- Redesigned dashboard header: compact CL logo on the left, product name and subtitle on the right.
- Added a dedicated compact header logo asset while preserving the full CL Impianti brand logo for integration branding.
- Kept installer PIN backward compatibility from earlier 0.1.x/0.2.x versions.

## 0.2.5
- Installer PIN compatibility and dashboard improvements.
