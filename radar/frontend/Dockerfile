# ─── Nginx Production Server ────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Rimuovi configurazione default di Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copia la configurazione custom
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia la build Angular compilata localmente nella directory di serving Nginx
COPY dist/radar-frontend/browser /usr/share/nginx/html

# Healthcheck Nginx
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# Porta esposta
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
