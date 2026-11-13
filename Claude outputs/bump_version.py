"""
Automātiski palielina lapas versiju version.json failā pēc katra koda atjauninājuma.

Versija: MAJOR.MINOR.PATCH (piem. 1.6.2)
  [major]  -> 2.0.0   pilns lapas pārveidojums (dizains, struktūra)
  [minor]  -> 1.7.0   jauna funkcija (jauna sadaļa, veikals, preču veids)
  (nekas)  -> 1.6.3   mazs labojums (kļūda, teksts, saite) — noklusējums
  [skip-version]      versiju nemainīt

Atzīmi raksta commit ziņojumā, piem.: "[minor] Pievienotas nūjas"
"""
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION_PATH = os.path.join(ROOT, "version.json")

event = {}
if os.environ.get("GITHUB_EVENT_PATH"):
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        event = json.load(f)
commits = event.get("commits") or []
messages = [c.get("message", "") for c in commits] or [os.environ.get("COMMIT_MSG", "")]
text = "\n".join(messages).lower()

if "[skip-version]" in text:
    print("Atzīme [skip-version] — versija netiek mainīta.")
    raise SystemExit(0)

with open(VERSION_PATH, encoding="utf-8") as f:
    data = json.load(f)

major, minor, patch = (int(x) for x in re.findall(r"\d+", data.get("version", "1.0.0"))[:3])
if "[major]" in text:
    major, minor, patch, level = major + 1, 0, 0, "major"
elif "[minor]" in text:
    minor, patch, level = minor + 1, 0, "minor"
else:
    patch, level = patch + 1, "patch"

new_version = f"{major}.{minor}.{patch}"
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
# Pirmā commit ziņojuma rinda bez atzīmēm kā īss apraksts
first = next((m for m in messages if m.strip()), "").splitlines()[0] if messages else ""
notes = re.sub(r"\[(major|minor|patch)\]\s*", "", first, flags=re.I).strip() or "Atjauninājums"

data.update({"version": new_version, "released": now, "notes": notes})
data["history"] = ([{"version": new_version, "released": now, "notes": notes}] + data.get("history", []))[:30]

with open(VERSION_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"Versija: {new_version} ({level}) — {notes}")
