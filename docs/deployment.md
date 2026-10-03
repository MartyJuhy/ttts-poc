# Nasazení TTTS PoC

## Co se nasazuje

React + Vite se při buildu převede na statické soubory v `dist/`. Firebase Hosting je servíruje na `https://ttts-poc.web.app`. Zatím je stránka pouze prezentační; turnajová data ani API ještě nejsou připojené.

GitHub Actions spustí build pro pull request do `main`. Po pushi nebo merge do `main` workflow navíc nasadí web do Firebase Hosting.

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

## Jednorázové nastavení GitHubu

V repozitáři `MartyJuhy/ttts-poc` otevři **Settings → Secrets and variables → Actions → Variables** a přidej hodnoty `GCP_WIF_PROVIDER` a `GCP_SERVICE_ACCOUNT` vypsané výše. Nejde o tajné klíče; přístup omezuje podmínka GCP provideru. Do GitHubu se nevkládá service-account JSON ani dlouhodobý token.

## Jak WIF funguje

1. GitHub Actions požádá GitHub OIDC o krátkodobý token, který identifikuje repozitář a branch workflow.
2. Google Security Token Service ověří podpis tokenu a podmínku provideru. Povolená je pouze `MartyJuhy/ttts-poc` a `main`.
3. GCP vymění GitHub token za krátkodobé přihlašovací údaje nasazovacího service accountu.
4. Firebase CLI použije tyto údaje k uploadu statických souborů do Hosting.

Soukromý klíč service accountu nikde dlouhodobě neleží. Pull request pouze sestavuje web; deployment a GCP přihlášení se spouští jen po pushi do `main`.

## Ověření nasazení

Po nastavení proměnných pushni změnu do `main` nebo sluč pull request. V GitHubu otevři **Actions → Build and deploy web**. Po úspěšném běhu obnov `https://ttts-poc.web.app`.