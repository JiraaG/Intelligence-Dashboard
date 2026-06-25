# Placeholder per il file GeoJSON dei confini geografici mondiali.
# 
# ISTRUZIONI PER L'INSTALLAZIONE:
# ─────────────────────────────────────────────────────────────────────────────
# Questo file NON è incluso nel repository per ragioni di dimensione (~5MB).
# 
# Scaricalo da una delle seguenti fonti ufficiali e salvalo in questa cartella
# con il nome esatto: countries.geo.json
#
# Fonti raccomandate:
# 1. Natural Earth (risoluzione 110m, consigliata per la mappa Radar):
#    https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson
#
# 2. Alternative compatta (50m, più dettagliata):
#    https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json
#    (richiede conversione con topojson → geojson prima dell'uso)
#
# DOPO il download, rinomina il file in: countries.geo.json
# e posizionalo in: frontend/src/assets/data/countries.geo.json
#
# ─────────────────────────────────────────────────────────────────────────────
# NOTA: Il file viene caricato offline dalla mappa Leaflet tramite HttpClient:
#   this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
#
# NON usare URL CDN esterni in produzione. Il file deve essere locale.
# ─────────────────────────────────────────────────────────────────────────────
