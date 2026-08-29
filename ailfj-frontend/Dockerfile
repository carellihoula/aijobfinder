FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes env vars into the bundle at build time - .env is gitignored/dockerignored
# (it's not a secret, but keeping the pattern consistent with backend/.env), so this
# has to come in as a build arg instead, sourced from the root .env docker compose
# auto-loads (see FLOWER_BASIC_AUTH for the same mechanism).
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80