FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/ussd-simulator ./
RUN npm install
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/ussd-simulator/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
