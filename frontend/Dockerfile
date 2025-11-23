FROM node:22-alpine AS build-stage
WORKDIR /app

# Copy package files (separate layer for better caching)
COPY package*.json ./

# Install dependencies (cached unless package files change)
RUN npm ci

# Copy source files (changes here won't invalidate dependency cache)
COPY public ./public
COPY src ./src
COPY index.html ./
COPY vite.config.ts tsconfig*.json env.d.ts ./

# Build the app
RUN npm run build

FROM nginx:stable-alpine AS production-stage

RUN mkdir -p /app

COPY --from=build-stage /app/dist /app
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]