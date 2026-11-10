# TTTS PoC Web

React public scoreboard and ASP.NET Core API for the TTTS demo tournament.

## Local development

```sh
npm ci
dotnet run --project api --urls http://localhost:5080
```

In another terminal, run `npm run dev`. Vite proxies `/api` to the local API. The local API uses seeded in-memory matches; Cloud Run uses Firestore. Firebase Auth settings for local admin sign-in belong in an untracked `.env.local` file based on [.env.example](.env.example).

The historical results POC uses a separate FastAPI service and a seeded SQLite database. Install its dependencies, create the seed, and run it in another terminal:

```powershell
python -m pip install -r history_api/requirements-dev.txt
python -m history_api.seed
python -m uvicorn history_api.main:app --reload --port 8000
```

Open `/history` in the Vite app to browse the seeded players, tournaments, and 200 historical matches. The history API is proxied separately from the existing `/api` routes. In the Cloud Run image, the SQLite database is built from the same seed and included read-only as demo data; no Cloud SQL instance is needed for this POC.

Run the API tests with `python -m unittest history_api.test_api -v`.

Create a production build with `npm run build`. The output is written to `dist/` and deployed to Firebase Hosting.

## Deployment

Pull requests to `main` build the web and run API unit tests. A push to `main` deploys the API to Cloud Run and the web to Firebase Hosting. GitHub Actions uses Workload Identity Federation; setup instructions are in [docs/deployment.md](docs/deployment.md).