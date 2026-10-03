# TTTS PoC Web

React public scoreboard and ASP.NET Core API for the TTTS demo tournament.

## Local development

```sh
npm ci
dotnet run --project api --urls http://localhost:5080
```

In another terminal, run `npm run dev`. Vite proxies `/api` to the local API. The local API uses seeded in-memory matches; Cloud Run uses Firestore. Firebase Auth settings for local admin sign-in belong in an untracked `.env.local` file based on [.env.example](.env.example).

Create a production build with `npm run build`. The output is written to `dist/` and deployed to Firebase Hosting.

## Deployment

Pull requests to `main` build the web and run API unit tests. A push to `main` deploys the API to Cloud Run and the web to Firebase Hosting. GitHub Actions uses Workload Identity Federation; setup instructions are in [docs/deployment.md](docs/deployment.md).