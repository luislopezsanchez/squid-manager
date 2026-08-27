FROM node:20-slim AS build

WORKDIR /app
COPY package.json package-lock.json* ./

# Un proxy corporativo que cachea o trunca las respuestas del registry deja a
# npm con metadata incompleta, y falla con un conflicto de peer dependencies
# que no existe ("Found: vite@undefined"). Reintentar da margen a las
# descargas grandes.
ENV NPM_CONFIG_FETCH_RETRIES=5     NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000

# Con package-lock.json se instala exactamente lo que dice el lock, sin
# resolver nada por la red: es lo que hace el build reproducible y lo que
# evita que dos maquinas obtengan arboles de dependencias distintos.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]