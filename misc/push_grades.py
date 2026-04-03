"""
Push les notes de maths (PC*2) dans ecolle depuis data.json.

Usage :
    python push_grades.py              # dry-run (affiche ce qui serait envoyé)
    python push_grades.py --push       # envoie réellement les notes
    python push_grades.py --date 2025-10-07 --push   # une seule date
"""
import json
import math
import sys
import os
import argparse
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from kholles.client import EColleClient

JOUR_MARDI = 1  # 0=lundi


def make_client() -> EColleClient:
    url = os.environ["ECOLLE_URL"].strip()
    user = os.environ["ECOLLE_USER"].strip()
    pwd = os.environ["ECOLLE_PASS"].strip()
    return EColleClient(url, user, pwd)


def push_maths(data: dict, only_date: str | None, dry_run: bool, ceil_notes: bool = False):
    cfg = data["config"]
    classe_id = cfg["classe_maths_id"]
    matiere_id = cfg["matiere_maths_id"]

    entries = data["maths"]
    if only_date:
        entries = [e for e in entries if e["date"] == only_date]
        if not entries:
            print(f"Aucune entrée trouvée pour la date {only_date}")
            return

    with make_client() as client:
        client.login()
        client.fetch_data()

        for entry in entries:
            date_str = entry["date"]
            semaine = entry["semaine"]
            alertes = entry.get("alertes", [])

            if semaine is None:
                print(f"\n⏭ {date_str} : semaine non renseignée — SKIPPÉ")
                for a in alertes:
                    print(f"   {a}")
                continue

            print(f"\n📅 {date_str} (semaine {semaine})")
            if alertes:
                for a in alertes:
                    print(f"   ⚠ {a}")

            for colle in entry["colles"]:
                colle_num = colle["colle"]
                heure = colle["heure_min"]
                colle_alertes = colle.get("alertes", [])
                eleves = colle.get("eleves", [])

                if not eleves:
                    print(f"  Colle {colle_num} : feuille vide, skippé")
                    continue

                if colle_alertes:
                    for a in colle_alertes:
                        print(f"  Colle {colle_num} ⚠ {a}")

                # Filtrer les élèves valides
                eleves_valides = []
                for e in eleves:
                    if e["id_ecolle"] is None:
                        print(f"  Colle {colle_num} / {e['nom_ods']} : ⏭ ID inconnu, skippé")
                        continue
                    if e["note"] is None:
                        print(f"  Colle {colle_num} / {e['nom_ods']} : ⏭ note manquante, skippé")
                        continue
                    if e["note"] == 0:
                        print(f"  Colle {colle_num} / {e['nom_ods']} : ⚠ note 0 — à vérifier (absent ou réelle ?)")
                    eleves_valides.append(e)

                if not eleves_valides:
                    print(f"  Colle {colle_num} : aucun élève valide")
                    continue

                # Construire les tuples (eleve_id, note, commentaire)
                # Les notes décimales sont envoyées telles quelles ; si ecolle rejette,
                # relancer avec --ceil pour arrondir au plafond.
                students = [
                    (e["id_ecolle"], math.ceil(e["note"]) if ceil_notes else e["note"], "")
                    for e in eleves_valides
                ]

                h, m = heure // 60, heure % 60
                noms = ", ".join(f"{e['nom_ods']} ({e['note']})" for e in eleves_valides)
                print(f"  Colle {colle_num} ({h:02d}h{m:02d}) → {noms}")

                if not dry_run:
                    try:
                        result = client.add_group_grades(
                            week=semaine,
                            day=JOUR_MARDI,
                            hour=heure,
                            classe_id=classe_id,
                            subject_id=matiere_id,
                            students=students,
                        )
                        print(f"    ✓ {result}")
                    except Exception as ex:
                        print(f"    ✗ ERREUR : {ex}")

    if dry_run:
        print("\n[dry-run] Aucune note envoyée. Relancer avec --push pour envoyer.")


def main():
    parser = argparse.ArgumentParser(description="Push notes de maths vers ecolle")
    parser.add_argument("--push", action="store_true", help="Envoyer réellement (sinon dry-run)")
    parser.add_argument("--date", help="Ne traiter qu'une date (YYYY-MM-DD)")
    parser.add_argument("--ceil", action="store_true", help="Arrondir les notes décimales au plafond (ex: 14.5 → 15)")
    args = parser.parse_args()

    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)

    push_maths(data, only_date=args.date, dry_run=not args.push, ceil_notes=args.ceil)


if __name__ == "__main__":
    main()
