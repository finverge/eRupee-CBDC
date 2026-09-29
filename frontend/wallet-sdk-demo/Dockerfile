# Build context must be the repo root — this app imports ../../sdk/wallet-sdk/src
# directly (no separate npm package/build step for the SDK).
FROM node:20-alpine AS build
WORKDIR /repo
COPY sdk/wallet-sdk ./sdk/wallet-sdk
COPY frontend/wallet-sdk-demo ./frontend/wallet-sdk-demo
# The SDK is source-only (no build step of its own), but tsc still needs
# to resolve "react" types for files under it when it's type-checked as
# part of this app's build — install its own (dev-only) deps for that.
WORKDIR /repo/sdk/wallet-sdk
RUN npm install
WORKDIR /repo/frontend/wallet-sdk-demo
RUN npm install
RUN npm run build

FROM nginx:alpine
COPY --from=build /repo/frontend/wallet-sdk-demo/dist /usr/share/nginx/html
COPY frontend/wallet-sdk-demo/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
