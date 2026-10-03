# TTTS PoC Web

React web application for the public TTTS tournament overview.

## Local development

```sh
npm ci
npm run dev
```

Create a production build with `npm run build`. The output is written to `dist/` and deployed to Firebase Hosting.

## Deployment

Pull requests to `main` run the production build. A push to `main` deploys the site to the `ttts-poc` Firebase project. GitHub Actions uses Workload Identity Federation; setup instructions are in [docs/deployment.md](docs/deployment.md).