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

# Copia la build Angular compilata dallo stage builder
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html

# Healthcheck Nginx
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# Porta esposta
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
