"""
Déclare les TDs d'informatique (BCPST2B) dans ecolle depuis data.json.

Chaque date de TD = 4h (13h-17h). Pour raisons administratives, on déclare
4 colles d'1h non notées (note=21), une par élève fictif.

Usage :
    python push_info.py              # dry-run
    python push_info.py --push       # envoie réellement
    python push_info.py --date 2025-10-14 --push   # une seule date
"""
import json
import sys
import os
import argparse
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from kholles.client import EColleClient

JOUR_MARDI = 1  # 0=lundi
NOTE_NON_NOTE = 21  # code ecolle pour absence/non noté


def make_client() -> EColleClient:
    url = os.environ["ECOLLE_URL"].strip()
    user = os.environ["ECOLLE_USER"].strip()
    pwd = os.environ["ECOLLE_PASS"].strip()
    return EColleClient(url, user, pwd)


def date_to_semaine(d: date, semaines_ecolle: list, override: dict | None = None) -> int | None:
    """Trouve le numéro de semaine ecolle pour une date."""
    from datetime import datetime, timezone
    if override and d.isoformat() in override:
        return override[d.isoformat()]
    for s in semaines_ecolle:
        lundi_ts = s[2]
        lundi = datetime.fromtimestamp(lundi_ts, tz=timezone.utc).date()
        fin = lundi + timedelta(days=6)
        if lundi <= d <= fin:
            return s[1]
    return None


def push_info(data: dict, only_date: str | None, dry_run: bool):
    cfg = data["config"]
    classe_id = cfg["classe_info_id"]
    matiere_id = cfg["matiere_info_id"]
    heures = cfg["info_heures_min"]  # [780, 840, 900, 960]
    eleves = cfg["info_eleves"]      # 4 IDs d'élèves BCPST2B
    dates_str = cfg.get("info_dates", [])

    if not dates_str:
        print("⚠ Aucune date dans info_dates. Ajoute les dates dans data.json → config → info_dates")
        return

    if len(eleves) < len(heures):
        print(f"⚠ Il faut au moins {len(heures)} élèves dans info_eleves, seulement {len(eleves)} renseignés")
        return

    if only_date:
        dates_str = [d for d in dates_str if d == only_date]
        if not dates_str:
            print(f"Date {only_date} non trouvée dans info_dates")
            return

    with make_client() as client:
        client.login()
        ecolle_data = client.fetch_data()
        semaines_ecolle = ecolle_data.get("semaines", [])

        override = cfg.get("semaine_override", {})
        for date_str in dates_str:
            d = date.fromisoformat(date_str)
            semaine = date_to_semaine(d, semaines_ecolle, override)
            jour = d.weekday()

            if semaine is None:
                print(f"\n⏭ {date_str} : semaine ecolle introuvable — SKIPPÉ")
                continue

            print(f"\n📅 {date_str} (semaine {semaine}, jour {jour})")

            for i, heure in enumerate(heures):
                eleve_id = eleves[i]
                h, m = heure // 60, heure % 60
                print(f"  {h:02d}h{m:02d} → élève ID {eleve_id} (non noté)")

                if not dry_run:
                    try:
                        result = client.add_single_grade(
                            week=semaine,
                            day=jour,
                            hour=heure,
                            classe_id=classe_id,
                            subject_id=matiere_id,
                            eleve_id=eleve_id,
                            note=NOTE_NON_NOTE,
                            comment="TD informatique",
                        )
                        print(f"    ✓ {result}")
                    except Exception as ex:
                        print(f"    ✗ ERREUR : {ex}")

    if dry_run:
        print("\n[dry-run] Aucune déclaration envoyée. Relancer avec --push pour envoyer.")


def main():
    parser = argparse.ArgumentParser(description="Déclare les TDs info vers ecolle")
    parser.add_argument("--push", action="store_true", help="Envoyer réellement (sinon dry-run)")
    parser.add_argument("--date", help="Ne traiter qu'une date (YYYY-MM-DD)")
    args = parser.parse_args()

    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)

    push_info(data, only_date=args.date, dry_run=not args.push)


if __name__ == "__main__":
    main()
