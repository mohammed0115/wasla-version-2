# Dockerfile for WASLA Frontend (React + Vite)
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy source code
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/vite.config.ts frontend/tsconfig.json ./
COPY frontend/tailwind.config.js frontend/postcss.config.js ./

# Build application
RUN yarn build

# Production image
FROM node:18-alpine

WORKDIR /app

# Install serve to run static files
RUN npm install -g serve

# Copy built assets from builder
COPY --from=builder /app/dist ./dist

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

# Start application
CMD ["serve", "-s", "dist", "-l", "3000"]
