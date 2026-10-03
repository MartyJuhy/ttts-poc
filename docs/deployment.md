# Nasazení TTTS PoC

## Co se nasazuje

React + Vite vytváří statické soubory v `dist/`, které Firebase Hosting servíruje na `https://ttts-poc.web.app`. ASP.NET Core API běží na Cloud Run. Veřejný endpoint čte zápasy; změna skóre vyžaduje Firebase ID token a UID jediného nakonfigurovaného admina. API používá Firestore, který při prvním čtení naplní verzovanými demo zápasy, pokud je kolekce `matches` prázdná.

Pull request do `main` buildí web a spouští API unit testy, ale nenasazuje. Push nebo merge do `main` sestaví image API, nasadí API na Cloud Run, sestaví web s URL API a publikuje web do Firebase Hosting.

Veřejný `GET /api/matches` čte scoreboard. `POST /api/matches/{id}/score` přidá nebo odebere jeden bod aktuálního setu; endpoint kontroluje Firebase ID token, admin UID, živý stav zápasu, nezáporné skóre a verzi zápasu. Počty vyhraných setů jsou v této první iteraci jen zobrazené, zatím se automaticky nepřepočítávají.

## Jednorázové nastavení GCP

Příkazy spusť v Cloud Shellu s vybraným GCP projektem `ttts-poc`. Vytvoří samostatnou identitu nasazovacího účtu a povolí GitHub Actions získat krátkodobé přihlašovací údaje přes OIDC.

```bash
gcloud config set project ttts-poc

PROJECT_ID=ttts-poc
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
POOL_ID=github-actions
PROVIDER_ID=github
SA_NAME=github-deployer
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com firebasehosting.googleapis.com --project="$PROJECT_ID"

gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="GitHub Actions Firebase deployer"

gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --display-name="TTTS GitHub repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository == 'MartyJuhy/ttts-poc' && assertion.ref == 'refs/heads/main'"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/MartyJuhy/ttts-poc"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/firebasehosting.admin"

printf '\nGitHub Actions variables:\nGCP_WIF_PROVIDER=projects/%s/locations/global/workloadIdentityPools/%s/providers/%s\nGCP_SERVICE_ACCOUNT=%s\n' \
  "$PROJECT_NUMBER" "$POOL_ID" "$PROVIDER_ID" "$SA_EMAIL"
```

The provider accepts only this repository's `main` branch. The service account gets Firebase Hosting deploy permission. If Google Cloud reports an existing pool or service account with one of these names, inspect that resource instead of creating a duplicate.

## Jednorázové nastavení API

Tyto příkazy navazují na již vytvořený účet `github-deployer` a WIF provider. Vytvoří Artifact Registry repository a runtime service account pro Cloud Run. Runtime účet čte a zapisuje Firestore; GitHub deployer smí publikovat API image a nasazovat Cloud Run.

```bash
PROJECT_ID=ttts-poc
REGION=europe-west1
DEPLOYER=github-deployer@ttts-poc.iam.gserviceaccount.com
RUNTIME=ttts-api-runtime@ttts-poc.iam.gserviceaccount.com

gcloud services enable run.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com --project="$PROJECT_ID"

gcloud artifacts repositories create ttts \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker \
  --description="TTTS PoC container images"

gcloud iam service-accounts create ttts-api-runtime \
  --project="$PROJECT_ID" \
  --display-name="TTTS API Cloud Run runtime"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME}" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER}" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER}" \
  --role="roles/serviceusage.serviceUsageConsumer"

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME" \
  --project="$PROJECT_ID" \
  --role="roles/iam.serviceAccountUser" \
  --member="serviceAccount:${DEPLOYER}"
```

V Firebase Console otevři **Firestore Database → Create database**, zvol **Production mode** a lokaci `europe-west1`. Tím zůstanou přímé browser reads/writes zavřené; API používá připojenou Cloud Run identitu a Firestore Security Rules obchází bezpečným serverovým SDK.

## Firebase Auth admin účet

V Firebase Console zaregistruj v projektu `ttts-poc` webovou aplikaci. V **Authentication → Sign-in method** zapni Email/Password a v **Users** vytvoř admin účet. Z jeho detailu zkopíruj Firebase UID.

V **Firestore Database** vytvoř výchozí databázi v režimu **Production** a lokaci `europe-west1`. API ji při prvním čtení naplní třemi demo zápasy, pokud je kolekce `matches` prázdná. Cloud Run používá runtime účet `ttts-api-runtime`; browser nemá Firestore SDK ani přímé oprávnění zapisovat do databáze.

V repozitáři otevři **Settings → Secrets and variables → Actions → Variables** a doplň:

| Variable | Hodnota |
| --- | --- |
| `FIREBASE_ADMIN_UID` | UID vytvořeného admin uživatele |
| `VITE_FIREBASE_API_KEY` | `apiKey` z konfigurace Firebase webové aplikace |
| `VITE_FIREBASE_APP_ID` | `appId` z konfigurace Firebase webové aplikace |

Ponech existující `GCP_WIF_PROVIDER` a `GCP_SERVICE_ACCOUNT`. Firebase `apiKey` a `appId` jsou veřejná klientská konfigurace, ne tajný klíč. Backend povolí změnu skóre pouze UID uloženému v `FIREBASE_ADMIN_UID`; samotné přihlášení jiného Firebase uživatele nestačí.

Lokálně vytvoř `.env.local` podle `.env.example`. Pro API spusť `ADMIN_UID=tvuj-firebase-uid dotnet run --project api --urls http://localhost:5080`; ve druhém terminálu spusť `npm run dev`. Lokální API používá paměťový store a seed zápasy, Cloud Run používá Firestore. Lokální admin test vyžaduje stejné Firebase Web hodnoty a UID testovacího účtu.

## Jednorázové nastavení GitHubu

V repozitáři `MartyJuhy/ttts-poc` otevři **Settings → Secrets and variables → Actions → Variables** a přidej hodnoty `GCP_WIF_PROVIDER` a `GCP_SERVICE_ACCOUNT` vypsané výše. Nejde o tajné klíče; přístup omezuje podmínka GCP provideru. Do GitHubu se nevkládá service-account JSON ani dlouhodobý token.

## Jak WIF funguje

1. GitHub Actions požádá GitHub OIDC o krátkodobý token, který identifikuje repozitář a branch workflow.
2. Google Security Token Service ověří podpis tokenu a podmínku provideru. Povolená je pouze `MartyJuhy/ttts-poc` a `main`.
3. GCP vymění GitHub token za krátkodobé přihlašovací údaje nasazovacího service accountu.
4. Firebase CLI použije tyto údaje k uploadu statických souborů do Hosting.

Soukromý klíč service accountu nikde dlouhodobě neleží. Pull request pouze sestavuje web; deployment a GCP přihlášení se spouští jen po pushi do `main`.

## Ověření nasazení

Po nastavení GCP zdrojů a GitHub variables sluč PR do `main`. V **Actions → Verify and deploy TTTS** musí projít build; deploy job pak nasadí API a web. Veřejný scoreboard načítá Firestore přes API. Admin se přihlásí přes tlačítko **ADMIN** a může přidat nebo odebrat bod. Změny ukládá API do Firestore a ostatní klienti je načtou nejpozději při dalším pollingu. Bez nakonfigurovaného API zůstávají zobrazené mock zápasy, ale editace skóre není dostupná.