# Deploying the React beta

Nothing here touches production. `app.usetelosapp.com` keeps serving Streamlit
throughout.

## Order matters

1. ~~**Run `infra/enable-rls.sql` in Supabase first.**~~ **Done, 20 October.**
   Applied as the `enable_rls_public_schema` migration and verified: all twelve
   public tables have RLS on, `anon` and `authenticated` hold no grants, and the
   owner path still reads every row. Note the file as written would have failed:
   it named `interview_preps`, which does not exist in production, and
   `ON_ERROR_STOP` would have aborted the transaction. The applied version
   enumerates `pg_tables` instead. `core.database.protect_public_schema` now
   also hardens tables created lazily at runtime.

   Original reasoning, still the reason order matters: The React app is the point
   at which an anon key starts living in a browser. Do not put it there while
   the tables are still readable with it.

2. **Create the DNS record.** An A record for `beta` pointing at the same
   Elastic IP. Caddy gets the certificate itself on first request.

3. **Set `SITE_URL` on the API container only. Not in the shared env file, and
   not as an SSM parameter the deploy script folds into it.**

   Both containers read `SITE_URL` from `/opt/telos/.env`. Streamlit uses it in
   `core/auth.py` for password reset and confirmation emails; the beta API uses
   it for Stripe return URLs. Putting the beta URL in the shared file sends
   production's reset emails to the beta, which is precisely the break the top
   of this document promises not to cause. Compose `environment:` overrides
   `env_file:`, so scope it to the one container that should see it, as shown in
   step 5.

4. **Build the frontend and ship the static files.**

       cd frontend && npm ci && npm run build
       # dist/ goes to /srv/beta on the instance

5. **Add the API container** to the compose file:

       telos-api:
         build: .
         command: uvicorn api.main:app --host 0.0.0.0 --port 8000
         env_file: /opt/telos/.env
         environment:
           # Overrides the shared env file for this container only, so
           # production's reset emails keep pointing at the Streamlit app.
           - SITE_URL=https://beta.usetelosapp.com
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
