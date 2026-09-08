# Enable Google sign-in and password-free recovery

The login page now includes **Continue with Google** and **Forgot your password?**. The recovery page lets an approved care-team user sign in through Google without their MediCase password. It does not change their password or send reset emails.

## Google setup (one time)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create your project.
2. Configure Google Auth Platform's branding/audience (OAuth consent screen). While the app is in testing, add the Google accounts you will use as test users.
3. Create an OAuth client with application type **Web application**.
4. Add this exact authorized redirect URI for the local demo:

   `http://127.0.0.1:5000/auth/google/callback`

5. Save your Client ID and Client secret privately. Never commit the secret or paste it into public chat or source files.

Google documents the [OpenID Connect flow and client setup](https://developers.google.com/identity/openid-connect/openid-connect).

## Configure and run MediCase

In PowerShell, inside the extracted MediCase directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GOOGLE_CLIENT_ID = Read-Host 'Google Client ID'
$googleSecret = Read-Host 'Google Client secret' -AsSecureString
$env:GOOGLE_CLIENT_SECRET = [System.Net.NetworkCredential]::new('', $googleSecret).Password
$env:GOOGLE_REDIRECT_URI = 'http://127.0.0.1:5000/auth/google/callback'
.\.venv\Scripts\python.exe app.py
```

Use the same shell so the app inherits these environment variables. Stop any previous MediCase server first. The Google button becomes enabled after restarting with both credentials set. These commands configure only the current terminal session. For hosting, set the same values in your deployment's secret/environment settings and use an HTTPS redirect URI registered with Google.

## Register the care-team account

Create a MediCase user with the same Gmail or Google Workspace address they will choose at Google:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app create-user
```

The sample `doctor@medicase.demo` is a fictional address and cannot be used for real Google sign-in. Keep that sample account for the existing password demo; create a separate account using your real Google email for testing.

On the first successful Google sign-in, MediCase matches an already-approved user and stores Google's stable account ID. It never registers arbitrary Google users into the shared clinical workspace. Subsequent sign-ins use that stable ID. A different Google account cannot replace the link merely by presenting the same email.

First-time email matching requires a verified Gmail address or a verified Google Workspace account with Google's `hd` claim. Google accounts using unrelated external email addresses must be handled by the administrator; `email_verified` alone is insufficient for that automatic match. See [Google's explanation of authoritative email claims](https://developers.google.com/identity/sign-in/android/backend-auth).

## Test the flow

1. Use a full browser such as Chrome or Edge; Google can reject embedded browsers.
2. Open `http://127.0.0.1:5000/login`.
3. Choose Forgot your password? → Continue with Google.
4. Select the registered account and complete Google's sign-in.
5. You should return to the MediCase dashboard without entering a MediCase password.

An unregistered account stays signed out. Cancelling Google returns to login with an explanatory message. If credentials are absent, the UI explains that Google sign-in is not enabled.

## Implementation and verification

Authlib handles the authorization-code exchange and OpenID Connect signature, issuer, audience, expiry, state and nonce validation. PKCE is enabled. Only identity scopes (`openid email profile`) are requested. No access/refresh/ID tokens are saved in the MediCase session or database. Login initiation uses a CSRF-protected POST; the callback is public but authenticated through the OpenID Connect flow.

The additional automated tests mock Google's already-validated token response. They verify account matching, stable ID binding, CSRF, failure states, cancellation and missing configuration; they do not replace a real Google sign-in test. Live Google consent/token exchange requires your Google client credentials and registered account, and has not been completed in this delivery.
