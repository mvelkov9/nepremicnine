# ── Base stage ──────────────────────────────
FROM node:24-alpine AS base

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# ── Dev stage ───────────────────────────────
FROM base AS dev

ENV NODE_ENV=development

COPY . .

# ── Build stage ─────────────────────────────
FROM base AS builder

# Set explicit build dirs so nuxt prepare and nuxt build are consistent
ENV NUXT_BUILD_DIR=.nuxt-build
ENV NUXT_OUTPUT_DIR=.output-build

COPY . .

# Generate .nuxt-dev/tsconfig.json (required by tsconfig.json extends)
# This step needs nuxt.config.ts present — done after COPY . .
RUN NUXT_BUILD_DIR=.nuxt-dev pnpm exec nuxt prepare

# Full production build → artefacts land in .nuxt-build + .output-build
RUN pnpm build

# ── Production stage ────────────────────────
FROM node:24-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NITRO_HOST=0.0.0.0
ENV NITRO_PORT=3000
ENV PORT=3000

# Copy from .output-build (matches NUXT_OUTPUT_DIR in builder stage)
COPY --from=builder /app/.output-build /app/.output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
