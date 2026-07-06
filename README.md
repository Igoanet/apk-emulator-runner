# APK Emulator Runner

  Public emulator automation for APK FUD Pipeline. Gets **4 vCPU / 16 GB RAM** for free because this repo is public.

  ## Architecture

  ```
  Private: apk-fud-pipeline (your code, secret)
           |
           v  Trigger via GitHub API
           |
  Public:  apk-emulator-runner (emulator, 4 cores)
           |
           v  Run NP Manager on Android emulator
           |
           v  Upload output APK as artifact
  ```

  ## Trigger

  This workflow is triggered by the private `apk-fud-pipeline` repo via GitHub Actions API.

  ## Runner Specs

  | Spec | Value |
  |------|-------|
  | Runner | ubuntu-latest |
  | Cores | 4 |
  | RAM | 8192 MB |
  | API Level | 34 |
  | Arch | x86_64 |
  | GPU | swiftshader_indirect |

  ## Secrets Required

  - `TELEGRAM_TOKEN` - For job notifications

  ## Inputs

  | Input | Description |
  |-------|-------------|
  | job_id | Job ID |
  | apk_url | URL to input APK |
  | telegram_chat_id | Telegram chat for notifications |
  | np_manager_email | NP Manager login |
  | np_manager_pass | NP Manager password |
  