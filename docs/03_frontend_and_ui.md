# 🎨 Frontend e Interfaccia Utente (UI)

Il frontend di **Radar Informativo Globale** è una Single Page Application (SPA) costruita con **Angular 21** e **Standalone Components**, progettata per offrire un'esperienza visiva fluida e in tempo reale degna di un software di intelligence in stile Palantir.

---

## Lo Stack UI

- **Framework**: Angular 21
- **Mappa**: Leaflet 1.9 + plugin MarkerCluster
- **Componenti**: PrimeNG 17 (Carosello, Sidebar, Dropdown)
- **Stato (State Management)**: Segnali (`Signal`), `computed` e il moderno sistema `rxResource` di Angular.
- **Styling**: SCSS (CSS nativo) basato su Variabili CSS, con design "Glassmorphism" (sfondi translucidi, blur). Nessun utility-first framework come Tailwind.

---

## 1. La Mappa Globale e il Clustering

Il cuore visivo è il componente `RadarMapComponent` che disegna la plancia geografica. 
La visualizzazione reagisce al livello di Zoom dell'utente.

### Zoom OUT (Hatching delle Nazioni)
A livelli di zoom distanti (Zoom < 5), i marker vengono nascosti. 
La mappa disegna i confini fisici dei vari stati tramite file GeoJSON (`countries.geo.json`).
I paesi che presentano degli allarmi (articoli registrati) vengono colorati usando un effetto di **Hatching SVG** (strisce diagonali) iniettato a runtime dalla direttiva `leaflet-hatch.directive.ts`. 

### Zoom IN (Marker e Spiderfy)
Aspirando a livelli di dettaglio maggiori (Zoom ≥ 5), compaiono i **Marker**. 
- Se ci sono più notizie in un raggio ristretto, interviene **MarkerCluster**. 
- Un singolo cluster raggruppa spazialmente le notizie raggruppandole in un'icona "ad anello": se il cluster contiene articoli di diverse categorie, vedrai anelli frammentati nei vari colori (es. rosso per Nucleare, verde per Ambiente) con un contatore centrale.
- Se effettui uno zoom profondo, il cluster si "espande" in una struttura a ragnatela (Spiderfy), mostrando i pin individuali.

> [!NOTE]
> Per gestire l'allineamento dei bounding box di nazioni che attraversano la linea di cambio data (Antimeridiano, es. Stati Uniti o Russia), il codice imposta dei confini geografici *Mainland* pre-calcolati per evitare che la telecamera si blocchi.

---

## 2. Il Sistema dei Colori (10 Categorie Geopolitiche)

L'intero frontend si appoggia su un rigoroso vocabolario visivo a 10 categorie per decodificare gli eventi a colpo d'occhio. I colori sono centralizzati in `styles.scss` tramite variabili native CSS (es. `--color-nucleare`):

| Categoria | Colore | Significato |
|-----------|--------|-------------|
| ☢️ **Nucleare** | Rosso neon (`#ff4d4d`) | Centrali, Incidenti, Smaltimento. |
| ⚡ **Energia** | Arancio (`#ffa64d`) | Oil & Gas, Rinnovabili. |
| 🏗️ **Infrastrutture** | Grigio Blu (`#b3c6ff`) | Strade, Ponti, Dighe. |
| 🌐 **Geopolitica** | Giallo (`#ffff66`) | Accordi di pace, Tensioni di confine. |
| 💰 **Economia** | Verde Brillante (`#66ff66`) | Mercati, Materie prime, Sanzioni. |
| 💻 **Tecnologia** | Ciano (`#4dffff`) | Data center, IA, Cyberattacchi. |
| 🚀 **Spazio** | Viola/Rosa (`#ff66ff`) | Satelliti, Lanci, Ricerca spaziale. |
| 🌲 **Ambiente** | Verde Smeraldo (`#00cc99`) | Alluvioni, Siccità, Incendi. |
| 🏥 **Salute** | Bianco Puro (`#ffffff`) | Pandemie, Crisi sanitarie. |
| 🛡️ **Sicurezza** | Rosso Scuro (`#cc0000`) | Eserciti, Ribellioni, Attentati. |

---

## 3. L'Interfaccia Utente

### Toolbar Superiore (Glassmorphism)
Sospesa sopra la mappa, permette di filtrare i dati visualizzati:
- Selezione per data (Calendario).
- Selezione per Sentiment (Positivo, Negativo, Neutrale).
- Selezione Rapida per Paese (Drop-down).
- Filtri per Categoria (Chip/Badge).

### Split-Screen Sidebar
Cliccando su un paese o su un cluster della mappa, l'interfaccia si suddivide automaticamente in un rapporto 70/30 (Mappa a sinistra, Sidebar a destra). 

La Sidebar ospita un **Carosello (PrimeNG)** che permette di scorrere orizzontalmente/verticalmente gli articoli, visualizzando:
- Il grado di rilevanza dell'articolo (Stelle o Gauge).
- Il Badge colorato del sentiment.
- Il Box con le **Entità Infrastrutturali** coinvolte e le **Aziende**.
- Il link sorgente ("Leggi la fonte originale").

> [!TIP]
> Tutti i box informativi (come la dicitura della testata d'origine) utilizzano regole `flexbox` con troncamento visivo (`white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`) per garantire che i testi lunghi estratti dal RSS non spezzino l'allineamento dei pulsanti laterali.
