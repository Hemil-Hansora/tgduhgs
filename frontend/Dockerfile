# Local Docker build of the SPA, served by nginx that proxies /api to the
# backend service (same-origin, so the frontend never hardcodes an API URL).

# ── Stage 1: build the static bundle ──
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: serve static files + reverse-proxy /api ──
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
