# ============================================================
#  Frontend container ki recipe (React -> build -> nginx se serve)
#  "Multi-stage build": Stage 1 build karta hai, Stage 2 sirf
#  final static files serve karta hai (image chhota rehta hai).
# ============================================================

# ---- Stage 1: Build (Node se React ko static files mein badlo) ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# The app calls the API through nginx's /api proxy (same origin, no CORS)
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build          # 'dist/' folder mein static HTML/JS/CSS banta hai

# ---- Stage 2: Serve (nginx se wo static files dikhao) ----
FROM nginx:alpine
# Stage 1 se bani 'dist/' ko nginx ke folder mein copy karo
COPY --from=build /app/dist /usr/share/nginx/html
# SPA routing ke liye apna nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
