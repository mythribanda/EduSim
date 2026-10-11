# =============================================================================
# EduSim_frontend Dockerfile
# Multi-stage: Node.js + npm build -> lightweight Node production serve
# =============================================================================

# --- Stage 1: Build with Node.js and npm ---
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json* ./

# Install dependencies cleanly
RUN npm ci || npm install

# Copy application source code and configuration
COPY . .

# Build the production bundle
RUN npm run build

# --- Stage 2: Production Runner ---
FROM node:22-alpine AS runner

WORKDIR /app

# Set production environment variables
ENV NODE_ENV=production \
    PORT=8080

# Create a non-root user and group
RUN addgroup -S edusim && adduser -S edusim -G edusim

# Copy required files and built artifacts from builder
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/wrangler.jsonc ./

# Set proper ownership for non-root execution
RUN chown -R edusim:edusim /app

USER edusim

EXPOSE 8080

# Serve via npx wrangler dev on port 8080 (which serves TanStack Start SSR/Worker & static assets)
CMD ["npx", "wrangler", "dev", "--config", "dist/server/wrangler.json", "--port", "8080", "--ip", "0.0.0.0"]
