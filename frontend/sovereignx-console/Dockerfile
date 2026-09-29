# Build context must be the repo root — this app imports
# ../../shared/theme/*.css, which is outside its own folder.
FROM node:20-alpine AS build
WORKDIR /repo
COPY frontend/shared ./frontend/shared
COPY frontend/sovereignx-console ./frontend/sovereignx-console
WORKDIR /repo/frontend/sovereignx-console
RUN npm install
RUN npm run build

FROM nginx:alpine
COPY --from=build /repo/frontend/sovereignx-console/dist /usr/share/nginx/html
COPY frontend/sovereignx-console/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
