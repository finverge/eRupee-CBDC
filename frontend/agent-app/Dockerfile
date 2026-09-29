FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/agent-app ./
RUN npm install
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/agent-app/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
