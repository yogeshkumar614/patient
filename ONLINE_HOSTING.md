# Put MediCase online

This project now includes a Dockerfile and an online server entry point for hosting the existing Flask + SQLite app. A public deployment was not completed: the local public-tunnel process was blocked by execution policy, and the connected Railway account had no projects or selected source repository.

## Railway setup

1. Upload this MediCase folder to a GitHub repository, excluding `.secret_key`, `.env`, `.venv`, and local databases. The existing `.gitignore` covers these.
2. In Railway, create a project/service from that repository. The Dockerfile builds the Flask application.
3. Attach a persistent volume at `/data` so `patient_case.db` survives restarts/deployments.
4. Set `MEDICASE_SECRET_KEY` to a private random value (at least 32 random bytes). Never share this value in chat or commit it.
5. Set `MEDICASE_DEMO=1` to initialize fictional demo records and the demo login. Local patient data is not included in the container.
6. Under Networking, generate a public domain; select the port used by the service (`PORT`, default 8080).
7. Open the generated HTTPS domain and sign in with `doctor@medicase.demo` / `demo123`.

All people with the demo credentials can edit the shared fictional demo. Use synthetic data only. Railway hosting/volumes may require a paid plan; review the account's pricing before provisioning.

For Google sign-in, configure the client credentials described in `GOOGLE_SIGN_IN.md`. Register `https://YOUR-DOMAIN/auth/google/callback` with Google and set `GOOGLE_REDIRECT_URI` to the same URL. Publishing the website alone does not enable Google login.

References: [Railway Dockerfiles](https://docs.railway.com/guides/dockerfiles), [persistent volumes](https://docs.railway.com/guides/volumes), [public networking](https://docs.railway.com/guides/public-networking).
