import os
import typer
from dotenv import load_dotenv
from datetime import datetime, timezone

from kholles.client import EColleClient, JOURS

load_dotenv()

app = typer.Typer(no_args_is_help=True)


def make_client() -> EColleClient:
    url = os.environ.get("ECOLLE_URL", "").strip()
    user = os.environ.get("ECOLLE_USER", "").strip()
    password = os.environ.get("ECOLLE_PASS", "").strip()
    if not (url and user and password):
        typer.echo("Erreur : ECOLLE_URL, ECOLLE_USER et ECOLLE_PASS requis dans .env")
        raise typer.Exit(1)
    return EColleClient(url, user, password)


@app.command()
def info():
    """Affiche les classes, matières et semaines disponibles pour le colleur."""
    with make_client() as client:
        login_info = client.login()
        typer.echo(f"\n✓ Connecté : {login_info.get('name')}")

        data = client.fetch_data()

        classes = data.get("classes", [])  # [id, nom, annee, semestres, opt1, opt2]
        typer.echo(f"\n--- Classes ({len(classes)}) ---")
        for c in classes:
            typer.echo(f"  [{c[0]}] {c[1]}")

        matieres = data.get("matieres", [])  # [id, nom, couleur, lv]
        typer.echo(f"\n--- Matières ({len(matieres)}) ---")
        for m in matieres:
            typer.echo(f"  [{m[0]}] {m[1]}")

        semaines = data.get("semaines", [])  # [id, numero, lundi_ts]
        typer.echo(f"\n--- Semaines ({len(semaines)}) ---")
        for s in semaines:
            lundi = datetime.fromtimestamp(s[2], tz=timezone.utc).strftime("%d/%m/%Y")
            typer.echo(f"  S{s[1]:02d}  lundi {lundi}")

        groupes = data.get("groupes", [])  # [id, nom, classe_id]
        typer.echo(f"\n--- Groupes ({len(groupes)}) ---")
        for g in groupes:
            typer.echo(f"  [{g[0]}] groupe {g[1]}  (classe {g[2]})")

        creneaux = data.get("creneaux", [])  # [id, classe_id, jour, heure, salle]
        typer.echo(f"\n--- Créneaux ({len(creneaux)}) ---")
        for cr in creneaux:
            jour = JOURS[cr[2]] if cr[2] < len(JOURS) else str(cr[2])
            h, m = cr[3] // 60, cr[3] % 60
            typer.echo(f"  [{cr[0]}] {jour} {h:02d}h{m:02d}  salle {cr[4]}  (classe {cr[1]})")


@app.command()
def eleves(classe_id: int = typer.Argument(..., help="ID de la classe")):
    """Liste les élèves d'une classe avec leur ID."""
    with make_client() as client:
        client.login()
        data = client.fetch_data()
        # [pk, nom, login, groupe_id, lv1, lv2, classe_id, order, option, groupe2, photo]
        eleves_classe = [e for e in data.get("eleves", []) if e[6] == classe_id]
        if not eleves_classe:
            typer.echo(f"Aucun élève trouvé pour la classe {classe_id}")
            raise typer.Exit(1)
        typer.echo(f"\n--- Élèves classe {classe_id} ({len(eleves_classe)}) ---")
        for e in eleves_classe:
            typer.echo(f"  [{e[0]}] {e[1]}  (groupe {e[3]})")


@app.command()
def notes():
    """Affiche les notes déjà saisies."""
    with make_client() as client:
        client.login()
        data = client.fetch_data()
        existing = data.get("notes", [])
        if not existing:
            typer.echo("Aucune note saisie.")
            return
        typer.echo(f"\n--- Notes existantes ({len(existing)}) ---")
        for n in existing:
            typer.echo(f"  {n}")


@app.command()
def test_grade(
    week: int = typer.Option(..., help="Numéro de semaine"),
    day: int = typer.Option(..., help="Jour : 0=lundi … 5=samedi"),
    hour: int = typer.Option(..., help="Heure en minutes depuis minuit (ex: 840 = 14h00)"),
    classe: int = typer.Option(..., help="ID de la classe"),
    subject: int = typer.Option(..., help="ID de la matière"),
    eleve1: int = typer.Option(..., help="ID élève 1"),
    note1: int = typer.Option(..., help="Note élève 1 (0-20, ou 21=absent)"),
    eleve2: int = typer.Option(0, help="ID élève 2 (optionnel)"),
    note2: int = typer.Option(-1, help="Note élève 2"),
    eleve3: int = typer.Option(0, help="ID élève 3 (optionnel)"),
    note3: int = typer.Option(-1, help="Note élève 3"),
):
    """Déclare les notes d'un groupe (test)."""
    students = [(eleve1, note1, "")]
    if eleve2:
        students.append((eleve2, note2, ""))
    if eleve3:
        students.append((eleve3, note3, ""))

    with make_client() as client:
        client.login()
        client.fetch_data()
        result = client.add_group_grades(
            week=week,
            day=day,
            hour=hour,
            classe_id=classe,
            subject_id=subject,
            students=students,
        )
        typer.echo(f"✓ Notes enregistrées : {result}")


def main():
    app()
