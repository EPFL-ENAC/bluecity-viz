FROM node:22-alpine AS build-stage
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY public ./public
COPY src ./src
COPY index.html ./
COPY *.ts ./
COPY *.json ./
COPY vite.config.ts ./

# Build the app
RUN npm run build

FROM nginx:stable-alpine AS production-stage

RUN mkdir -p /app

COPY --from=build-stage /app/dist /app
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]