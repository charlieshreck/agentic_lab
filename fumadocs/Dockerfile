# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first
COPY package.json ./
RUN npm install --legacy-peer-deps

# Copy source files
COPY . .

# Set environment for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Build - skip linting for faster builds
RUN npm run build || (echo "Build failed, checking logs..." && cat .next/trace 2>/dev/null || true && exit 1)

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Copy public directory if it exists
RUN mkdir -p ./public
COPY --from=builder /app/public ./public/

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
