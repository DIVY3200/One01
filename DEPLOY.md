# Deploying One01

Free setup, about 20 minutes:

| Part | Host | Config in this repo |
|---|---|---|
| Database (PostgreSQL) | [Neon](https://neon.tech) | – |
| Backend (FastAPI) | [Render](https://render.com) | `render.yaml`, `backend/Dockerfile` |
| Frontend (Next.js) | [Vercel](https://vercel.com) | `frontend/` |

Do the steps in order: each one gives you a value the next one needs.

## 1. Database: Neon

1. Sign up at https://neon.tech with your GitHub account.
2. Create a project named `one01`. Region: **AWS Asia Pacific (Singapore)** (closest to India, same as the backend).
3. On the project dashboard click **Connect**, turn **Connection pooling off**, and copy the connection string.
   It looks like `postgresql://neondb_owner:...@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require...`

   Pooling must be off: pooled connections break the async Postgres driver the backend uses.

## 2. Backend: Render

1. Sign up at https://render.com with your GitHub account.
2. Click **New → Blueprint**, pick the `One01` repo. Render reads `render.yaml`.
3. Fill in the three values it asks for:
   - `GEMINI_API_KEY`: your Gemini key
   - `DATABASE_URL`: the Neon string from step 1
   - `CORS_ORIGINS`: `["http://localhost:3000"]` for now (updated in step 4)
4. Click **Apply**. The first build takes about 5 minutes; the database tables are created automatically on startup.
5. Open `https://<your-service>.onrender.com/health`. You should see `"status":"ok"`.
   Copy that base address (Render may add a suffix if `one01-backend` is taken).

## 3. Frontend: Vercel

1. Sign up at https://vercel.com with your GitHub account.
2. Click **Add New → Project** and import the `One01` repo.
3. Set **Root Directory** to `frontend`. The framework is detected as Next.js.
4. Add the environment variable `NEXT_PUBLIC_API_URL` = your Render address, without a trailing slash,
   e.g. `https://one01-backend.onrender.com`.
5. Click **Deploy** and copy the production address, e.g. `https://one01-xyz.vercel.app`.

## 4. Connect the two

1. In Render open the service, then **Environment**, and change `CORS_ORIGINS` to your exact Vercel address:
   `["https://one01-xyz.vercel.app"]` (no trailing slash). Save; Render redeploys.
2. Open the Vercel address, register a new account and create a subject.

## Good to know

- **Cold starts:** free Render services sleep after about 15 minutes without traffic. The first request after that
  can take up to a minute; if registering or loading times out, wait a moment and retry.
- **Auto-deploy:** every push to `main` redeploys both the backend and the frontend.
- **Fresh data:** your local `test.db` is not uploaded. The live site starts with an empty database.
- **API quota:** visitors use your Gemini key. Each account is limited to 30 AI requests per minute
  (`AI_RATE_LIMIT_PER_MINUTE`); suspend the Render service to switch the site off.
- **Changing the backend address:** `NEXT_PUBLIC_API_URL` is baked in at build time, so redeploy the frontend on
  Vercel after changing it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser console shows a CORS error | `CORS_ORIGINS` on Render must match the Vercel address exactly (https, no trailing slash) |
| Backend logs `prepared statement ... does not exist` | Use the Neon string with connection pooling **off** |
| Every lesson shows "Sample content" | `GEMINI_API_KEY` is missing or wrong on Render |
| Backend logs `[SECURITY] SECRET_KEY is not set` | Add `SECRET_KEY` in Render's Environment (the Blueprint normally generates it) |
