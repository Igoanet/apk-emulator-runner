"""CI native patches — expo prebuild ke BAAD chalta hai (android/ fresh generate hota hai,
isliye ye edits har CI build pe dobara lagane padte hain; local android/ gitignored hai).

1. allowBackup="false" — warna reinstall pe AsyncStorage (deviceId + panel session)
   auto-restore ho jata hai aur naya device OTP skip kar deta hai (owner rule:
   naya device = turant OTP).
2. ABI splits — per-ABI APKs (arm64-v8a / armeabi-v7a / x86_64); bot ko teeno chahiye.
"""
import pathlib
import re
import sys

manifest = pathlib.Path("android/app/src/main/AndroidManifest.xml")
m = manifest.read_text()
if 'android:allowBackup="false"' not in m:
    m2 = m.replace('android:allowBackup="true"', 'android:allowBackup="false"')
    if m2 == m:
        m2 = re.sub(r"<application ", '<application android:allowBackup="false" ', m, count=1)
    if m2 == m:
        sys.exit("FAIL: application tag nahi mila AndroidManifest me")
    manifest.write_text(m2)
print("OK: allowBackup=false")

gradle = pathlib.Path("android/app/build.gradle")
g = gradle.read_text()
if "splits" not in g:
    block = (
        "    splits {\n"
        "        abi {\n"
        "            enable true\n"
        "            reset()\n"
        "            include 'arm64-v8a', 'armeabi-v7a', 'x86_64'\n"
        "            universalApk false\n"
        "        }\n"
        "    }\n"
    )
    g2 = g.replace("android {", "android {\n" + block, 1)
    if g2 == g:
        sys.exit("FAIL: android { block nahi mila build.gradle me")
    gradle.write_text(g2)
print("OK: ABI splits (arm64-v8a, armeabi-v7a, x86_64)")
