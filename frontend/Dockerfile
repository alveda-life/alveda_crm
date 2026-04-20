# Stage 1: build
FROM node:20-alpine AS builder
WORKDIR /app
RUN npm install -g @quasar/cli
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN quasar build

# Stage 2: serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist/spa /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
