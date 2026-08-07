# APK Emulator Runner

GitHub Actions workflow jo Android emulator (API 33, Pixel 6) boot karke input APK pe **NP Manager** automation chalata hai. Bas yahi do cheezein hain — emulator + NP Manager.

## Files

- `.github/workflows/emulator-runner-v3.yml` — emulator workflow (manual `workflow_dispatch` ya `repository_dispatch` type `run-fud-pipeline`)
- `github_automation/run_pipeline_v3.sh` — pipeline driver: Gmail sign-in → release assets download → NP Manager → install verify → output APK
- `github_automation/gmail_login.py` — emulator pe Google (Gmail) account sign-in (ADB UI automation)
- `github_automation/np_manager_v3.py` — NP Manager automation (install → login → tools → signed output APK)

## Gmail sign-in

`gmail_email` + `gmail_pass` inputs (ya dispatch payload me same keys) do to pipeline emulator pe pehle Gmail login karti hai. Emulator `google_apis` image use karta hai — AOSP me Google sign-in nahi chalta. Google kabhi kabhi automated sign-in challenge karta hai ("Couldn't sign in" / CAPTCHA) — fail hone pe pipeline nahi rukti, screenshots (`gmail_*.png`) logs artifact me milte hain. **Secondary Gmail use karo, 2FA off hona chahiye.**

## Trigger

**Manual:** Actions tab se `run_id` + `apk_asset_id` do (optional `np_asset_id`).

**Dispatch:**
```
POST /repos/{owner}/{repo}/dispatches
{ "event_type": "run-fud-pipeline",
  "client_payload": { "run_id", "apk_asset_id", "np_asset_id",
                      "np_manager_email", "np_manager_pass" } }
```

Output APK aur logs GitHub Actions artifacts me milte hain (1-day retention).
