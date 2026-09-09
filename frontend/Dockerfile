FROM node:20.18-slim AS build

WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci, no npm install: respeta el lockfile al pie de la letra -con
# install, dos builds de la misma etiqueta de git pueden producir bundles
# distintos, que es justo lo que el lockfile existe para evitar. El CI ya
# usa "npm ci" (valida un arbol de dependencias que esta imagen no
# reproducia). El lockfile ya esta copiado arriba, asi que "ci" funciona
# tal cual (auditoria 2026-09-09, hallazgo 06-002).
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]