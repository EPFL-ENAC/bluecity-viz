FROM node:22-alpine AS build-stage
WORKDIR /app

# pnpm, pinned by the packageManager field in package.json
RUN corepack enable

# Copy package files (separate layer for better caching)
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Install dependencies (cached unless package files change)
RUN pnpm install --frozen-lockfile

# Copy source files (changes here won't invalidate dependency cache)
COPY public ./public
COPY src ./src
COPY index.html ./
COPY vite.config.ts tsconfig*.json env.d.ts ./

# Build the app
RUN pnpm run build-only

FROM nginx:stable-alpine AS production-stage

RUN mkdir -p /app

COPY --from=build-stage /app/dist /app
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]