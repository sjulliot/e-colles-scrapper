"""Récupère toutes les notes enregistrées dans ecolle et vérifie cohérence avec data.json."""
import os, json, math
from dotenv import load_dotenv
from datetime import datetime, timezone, date, timedelta
from collections import defaultdict

load_dotenv()

import sys; sys.path.insert(0, os.path.dirname(__file__))
from kholles.client import EColleClient

with EColleClient(os.environ["ECOLLE_URL"], os.environ["ECOLLE_USER"], os.environ["ECOLLE_PASS"]) as c:
    c.login()
    data = c.fetch_data()

# Format note : [pk, subject_id, classe_id, note, comment, semaine, date_ts, eleve_id, ...]
notes = data.get("notes", [])
eleves = {e[0]: e[1] for e in data.get("eleves", [])}
matieres = {m[0]: m[1] for m in data.get("matieres", [])}

print(f"Total notes enregistrées : {len(notes)}\n")

by_subject = defaultdict(list)
for n in notes:
    by_subject[n[1]].append(n)

for subj_id, snotes in sorted(by_subject.items()):
    print(f"=== {matieres.get(subj_id, subj_id)} ({len(snotes)} notes) ===")
    by_date = defaultdict(list)
    for n in snotes:
        d = datetime.fromtimestamp(n[6], tz=timezone.utc)
        by_date[d.date().isoformat()].append(n)
    for date_str, dnotes in sorted(by_date.items()):
        eleve_ids = [n[7] for n in dnotes]
        flag = " ⚠ DOUBLON" if len(eleve_ids) != len(set(eleve_ids)) else ""
        noms = [f"{eleves.get(n[7], '?'+str(n[7]))} ({n[3]})" for n in dnotes]
        print(f"  {date_str}{flag} : {', '.join(noms)}")
    print()

# --- Vérification vs data.json ---
print("=" * 60)
print("VÉRIFICATION vs data.json")
print("=" * 60)

with open(os.path.join(os.path.dirname(__file__), "data.json"), encoding="utf-8") as f:
    local = json.load(f)

cfg = local["config"]
MATHS_SUBJ_ID = cfg["matiere_maths_id"]
INFO_SUBJ_ID = cfg["matiere_info_id"]

# Index des notes enregistrées : (subject_id, eleve_id, date_iso) → note
recorded = {}
for n in notes:
    d = datetime.fromtimestamp(n[6], tz=timezone.utc).date().isoformat()
    key = (n[1], n[7], d)
    recorded[key] = n[3]

semaines_ecolle = {s[1]: s for s in data.get("semaines", [])}

def ecolle_date(semaine_num, jour_semaine):
    """Calcule la date réelle stockée par ecolle (lundi de la semaine + offset jour)."""
    s = semaines_ecolle.get(semaine_num)
    if not s:
        return None
    lundi = datetime.fromtimestamp(s[2], tz=timezone.utc).date()
    return (lundi + timedelta(days=jour_semaine)).isoformat()

print("\n--- Maths : attendu vs enregistré ---")
missing = []
for entry in local["maths"]:
    ods_date = entry["date"]
    sem = entry["semaine"]
    jour = entry["jour_semaine"]
    expected_date = ecolle_date(sem, jour) if sem else ods_date

    for colle in entry["colles"]:
        for eleve in colle.get("eleves", []):
            eid = eleve.get("id_ecolle")
            note = eleve.get("note")
            if eid is None or note is None:
                continue
            expected_note = math.ceil(note) if isinstance(note, float) else note
            # Chercher sous expected_date, puis J+1 (quirk ecolle pour les lundis)
            key = (MATHS_SUBJ_ID, eid, expected_date)
            key_j1 = (MATHS_SUBJ_ID, eid, (date.fromisoformat(expected_date) + timedelta(1)).isoformat()) if expected_date else None
            found_key = key if key in recorded else (key_j1 if key_j1 and key_j1 in recorded else None)
            if found_key:
                rec = recorded[found_key]
                stored_date = found_key[2]
                day_note = f"  (stocké J+1 : {stored_date})" if stored_date != expected_date else ""
                if abs(rec - expected_note) > 0:
                    print(f"  ⚠ {ods_date} {eleves.get(eid,'?')} : attendu {expected_note}, enregistré {rec}{day_note}")
                elif day_note:
                    print(f"  ℹ {ods_date} {eleves.get(eid,'?')} ({expected_note}){day_note}")
            else:
                print(f"  ✗ MANQUANT {ods_date} (ecolle: {expected_date}) {eleves.get(eid,'?')} (attendu {note})")
                missing.append((ods_date, eleves.get(eid, str(eid)), note))

if not missing:
    print("  ✓ Toutes les notes maths sont présentes")

print("\n--- Info : attendu vs enregistré ---")
info_missing = []
override = cfg.get("semaine_override", {})
for date_str in cfg.get("info_dates", []):
    # Calculer la semaine correspondante
    d = date.fromisoformat(date_str)
    sem_num = override.get(date_str)
    if sem_num is None:
        for s in data.get("semaines", []):
            lundi = datetime.fromtimestamp(s[2], tz=timezone.utc).date()
            if lundi <= d <= lundi + timedelta(days=6):
                sem_num = s[1]
                break
    expected_date = ecolle_date(sem_num, d.weekday()) if sem_num else date_str
    for eleve_id in cfg["info_eleves"]:
        key = (INFO_SUBJ_ID, eleve_id, expected_date)
        if key not in recorded:
            info_missing.append((date_str, expected_date, eleve_id))

if info_missing:
    for ds, edate, eid in info_missing:
        print(f"  ✗ MANQUANT {ds} (ecolle: {edate}) élève {eid}")
else:
    print("  ✓ Tous les TDs info sont présents")
