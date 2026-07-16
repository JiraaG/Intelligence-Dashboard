# ─── 1. Build Stage (Node.js) ───────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Installa le dipendenze usando legacy-peer-deps come richiesto dalle regole ECC
COPY package*.json ./
RUN npm ci --legacy-peer-deps

# Copia il resto del codice; fetch+verify GeoJSON (gitignored) poi build
COPY . .
RUN node scripts/verify-geojson.mjs --fetch
RUN npm run build

# ─── 2. Nginx Production Server ────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Rimuovi configurazione default di Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copia la configurazione custom
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia la build Angular compilata dallo stage builder con la proprietà corretta
COPY --from=builder --chown=nginx:nginx /app/dist/radar-frontend/browser /usr/share/nginx/html

# Configura le directory necessarie per l'esecuzione non privilegiata di Nginx
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /var/run /usr/share/nginx/html

# Passa all'utente unprivileged
USER nginx

# Healthcheck Nginx
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/health || exit 1

# Porta esposta
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
