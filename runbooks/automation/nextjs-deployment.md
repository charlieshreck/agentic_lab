# Next.js Application Deployment Pattern

## Overview

Pattern for deploying Next.js frontend applications to the agentic cluster with GitHub Actions CI/CD.

## Location
- Cluster: Agentic (10.20.0.0/24)
- Namespace: `ai-platform`
- Image Registry: ghcr.io/charlieshreck/agentic_lab/

## Pattern: GitHub Actions + Docker + ArgoCD

### Prerequisites

1. Next.js project with `output: 'standalone'` in next.config.mjs
2. GitHub Actions workflow for building Docker images
3. ArgoCD Application manifest

## Project Structure

```
<app-name>/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Homepage
│   ├── layout.tsx         # Root layout
│   └── api/               # API routes
├── public/
│   └── .gitkeep           # REQUIRED: Ensure directory tracked
├── package.json
├── next.config.mjs
├── Dockerfile
├── tailwind.config.ts
├── tsconfig.json
└── postcss.config.js
```

## Key Configuration Files

### next.config.mjs
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // REQUIRED for Docker
  eslint: {
    ignoreDuringBuilds: true,  // Optional: for rapid iteration
  },
  typescript: {
    ignoreBuildErrors: true,   // Optional: for rapid iteration
  },
  env: {
    // Runtime environment variables
    API_URL: process.env.API_URL || 'http://default.url',
  },
};

export default nextConfig;
```

### Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (better caching)
COPY package.json ./
RUN npm install --legacy-peer-deps

# Copy source files
COPY . .

# Set environment for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Build
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Copy public directory (create if needed)
RUN mkdir -p ./public
COPY --from=builder /app/public ./public/

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### package.json (Minimal)
```json
{
  "name": "app-name",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "20.14.0",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0",
    "typescript": "5.4.5",
    "tailwindcss": "3.4.4",
    "postcss": "8.4.38",
    "autoprefixer": "10.4.19",
    "eslint": "8.57.0",
    "eslint-config-next": "14.2.5"
  }
}
```

## GitHub Actions Workflow

Create `.github/workflows/<app-name>.yml`:

```yaml
name: Build <App Name>

on:
  push:
    branches: [main]
    paths:
      - '<app-name>/**'
      - '.github/workflows/<app-name>.yml'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/<image-name>

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=latest
            type=sha,prefix=

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./<app-name>
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Kubernetes Manifests

### deployment.yaml
```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app-name>
  namespace: ai-platform
  labels:
    app: <app-name>
spec:
  replicas: 1
  selector:
    matchLabels:
      app: <app-name>
  template:
    metadata:
      labels:
        app: <app-name>
    spec:
      containers:
        - name: <app-name>
          image: ghcr.io/charlieshreck/agentic_lab/<image-name>:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 3000
              name: http
          env:
            - name: API_URL
              value: "http://service.namespace.svc.cluster.local:port"
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: <app-name>
  namespace: ai-platform
  labels:
    app: <app-name>
spec:
  type: NodePort
  ports:
    - port: 3000
      targetPort: 3000
      nodePort: 31XXX  # Choose available port
      protocol: TCP
  selector:
    app: <app-name>
```

### kustomization.yaml
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: ai-platform
resources:
  - deployment.yaml
```

### ArgoCD Application
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app-name>
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/agentic_lab.git
    targetRevision: main
    path: kubernetes/applications/<app-name>
  destination:
    server: https://10.20.0.40:6443
    namespace: ai-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Deployment Steps

### 1. Create Application Directory
```bash
mkdir -p /home/agentic_lab/<app-name>
cd /home/agentic_lab/<app-name>

# Create all required files (package.json, next.config.mjs, Dockerfile, etc.)
```

### 2. Create public/.gitkeep
```bash
mkdir -p public
echo "# Keep this directory in git" > public/.gitkeep
```

### 3. Create GitHub Actions Workflow
```bash
mkdir -p /home/agentic_lab/.github/workflows
# Create workflow file as shown above
```

### 4. Create Kubernetes Manifests
```bash
mkdir -p /home/agentic_lab/kubernetes/applications/<app-name>
# Create deployment.yaml, kustomization.yaml
```

### 5. Create ArgoCD Application
```bash
# Create /home/agentic_lab/kubernetes/argocd-apps/<app-name>-app.yaml
```

### 6. Initial Deployment (Image Not Built Yet)
Set replicas to 0 initially to avoid ErrImagePull:
```yaml
spec:
  replicas: 0  # Scale to 1 after image is built
```

### 7. Commit and Push
```bash
cd /home/agentic_lab
git add .
git commit -m "feat: add <app-name> frontend"
git push
```

### 8. Apply ArgoCD Application
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/<app-name>-app.yaml
```

### 9. Monitor GitHub Actions Build
```bash
# Via API (when gh CLI unavailable)
curl -s "https://api.github.com/repos/charlieshreck/agentic_lab/actions/runs?per_page=5" | \
  jq -r '.workflow_runs[] | "\(.name) \(.status) \(.conclusion)"'
```

### 10. Scale Up After Build Succeeds
```bash
# Edit deployment.yaml: replicas: 1
git add . && git commit -m "feat: scale <app-name> to 1 replica" && git push
```

### 11. Verify Deployment
```bash
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n ai-platform -l app=<app-name>

# Test endpoint
curl -s http://10.20.0.40:31XXX/
```

## Common Issues

### npm ci Fails (No package-lock.json)
**Fix**: Use `npm install --legacy-peer-deps` instead of `npm ci`

### Empty public Directory Not Tracked
**Fix**: Add `public/.gitkeep`

### TypeScript/ESLint Build Errors
**Fix**: Add `ignoreDuringBuilds: true` to next.config.mjs

### ErrImagePull
**Fix**: Check image path matches GitHub Actions workflow output

### Dockerfile COPY Fails for Empty Directory
**Fix**: Add `RUN mkdir -p ./public` before COPY

## NodePort Allocation

| Port | Application |
|------|-------------|
| 31099 | fumadocs (Kernow Knowledge UI) |

Reserve ports in 31090-31100 range for frontend applications.

## References

- [Next.js Standalone Output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- Lessons Learned: `/home/agentic_lab/runbooks/lessons-learned/fumadocs-deployment-2026-01.md`
