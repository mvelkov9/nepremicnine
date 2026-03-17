# ── Base stage ──────────────────────────────
FROM node:24-alpine AS base

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

COPY package.json pnpm-lock.yaml* ./
# Install dependencies once up front, but skip project lifecycle scripts until
# the full Nuxt source tree is present in later stages.
RUN pnpm install --frozen-lockfile --ignore-scripts

# ── Dev stage ───────────────────────────────
FROM base AS dev

ENV NODE_ENV=development

COPY . .
RUN pnpm install --offline --frozen-lockfile

# ── Build stage ─────────────────────────────
FROM base AS builder

COPY . .
RUN pnpm install --offline --frozen-lockfile
RUN pnpm build

# ── Production stage ───────────────────────
FROM node:24-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NITRO_HOST=0.0.0.0
ENV NITRO_PORT=3000
ENV PORT=3000

COPY --from=builder /app/.output-build /app/.output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
