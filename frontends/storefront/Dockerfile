FROM node:22-alpine AS build
WORKDIR /build
COPY frontends/storefront/package.json frontends/storefront/package-lock.json* ./
RUN npm install
COPY frontends/storefront/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /build/dist /usr/share/nginx/html
COPY frontends/storefront/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
