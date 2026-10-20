# Deploying the React beta

Nothing here touches production. `app.usetelosapp.com` keeps serving Streamlit
throughout.

## Order matters

1. **Run `infra/enable-rls.sql` in Supabase first.** The React app is the point
   at which an anon key starts living in a browser. Do not put it there while
   the tables are still readable with it.

2. **Create the DNS record.** An A record for `beta` pointing at the same
   Elastic IP. Caddy gets the certificate itself on first request.

3. **Create the SSM parameter** `/telos/SITE_URL` set to
   `https://beta.usetelosapp.com`, so password reset links land on the beta and
   not on the Streamlit app.

4. **Build the frontend and ship the static files.**

       cd frontend && npm ci && npm run build
       # dist/ goes to /srv/beta on the instance

5. **Add the API container** to the compose file:

       telos-api:
         build: .
         command: uvicorn api.main:app --host 0.0.0.0 --port 8000
         env_file: /opt/telos/.env
         restart: unless-stopped

6. **Append `deploy/beta.Caddyfile`** to the Caddyfile and reload Caddy.

## Before letting anyone in

- `curl https://beta.usetelosapp.com/api/health` returns `{"ok":true}`
- signing out of the beta does not sign you out of the Streamlit app, and the
  reverse, since both read the same `user_sessions` table
- a second account cannot see the first account's pipeline
- `tests/test_api.py` passes against the real database

## The trap this project has hit twice

EC2 user data runs only on first boot. A stack update stops, updates and
restarts the instance rather than replacing it, so cloud-init never re-runs and
template changes silently never reach the running box. Anything in this list
that looks like it should happen automatically will not. Apply it on the
instance and verify from inside the container.
