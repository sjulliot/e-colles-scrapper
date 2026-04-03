import httpx
from datetime import datetime, time, timezone, timedelta


JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]


class EColleClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=15.0,
        )
        self.colleur_id: int | None = None
        self.data: dict | None = None

    def login(self) -> dict:
        resp = self._client.post(
            "/app_mobile/connect",
            data={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        if resp.text == "invalide":
            raise RuntimeError("Login échoué : identifiants invalides")
        info = resp.json()
        if "colleur_id" not in info:
            raise RuntimeError(f"L'utilisateur n'est pas un colleur : {info}")
        self.colleur_id = info["colleur_id"]
        return info

    def fetch_data(self) -> dict:
        """Récupère tout : classes, creneaux, semaines, groupes, eleves, colles."""
        resp = self._client.get("/app_mobile/colleurdata")
        if resp.status_code == 403:
            raise RuntimeError("Non authentifié comme colleur")
        resp.raise_for_status()
        self.data = resp.json()
        return self.data

    def add_group_grades(
        self,
        *,
        week: int,
        day: int,
        hour: int,
        classe_id: int,
        subject_id: int,
        students: list[tuple[int, int, str]],  # [(eleve_id, note, commentaire), ...]
        catchup: bool = False,
        date_ts: int | None = None,
    ) -> dict:
        """
        Déclare les notes d'un groupe (jusqu'à 3 élèves).
        hour : minutes depuis minuit (ex: 14h00 = 840)
        students : liste de (eleve_id, note, commentaire), max 3
        note : entier 0-20, ou 21 pour absent
        """
        if not students:
            raise ValueError("Au moins un élève requis")
        if len(students) > 3:
            raise ValueError("Maximum 3 élèves par groupe")

        # Compléter à 3 slots avec des valeurs neutres (-1 = ignoré)
        slots = list(students) + [(0, -1, "")] * (3 - len(students))

        if date_ts is None:
            # Calculer la date à partir de la semaine et du jour
            semaine = next(
                (s for s in self.data["semaines"] if s[1] == week), None
            )
            if semaine is None:
                raise ValueError(f"Semaine {week} introuvable")
            lundi_ts = semaine[2]  # timestamp UTC du lundi
            lundi = datetime.fromtimestamp(lundi_ts, tz=timezone.utc).date()
            date_colle = lundi + timedelta(days=day)
            date_ts = int(
                datetime.combine(
                    date_colle, time(hour // 60, hour % 60)
                ).replace(tzinfo=timezone.utc).timestamp()
            )

        payload = {
            "week": week,
            "day": day,
            "hour": hour,
            "catchup": "true" if catchup else "false",
            "date": date_ts,
            "subject": subject_id,
            "classe": classe_id,
            "student1": slots[0][0],
            "grade1": slots[0][1],
            "comment1": slots[0][2],
            "student2": slots[1][0],
            "grade2": slots[1][1],
            "comment2": slots[1][2],
            "student3": slots[2][0],
            "grade3": slots[2][1],
            "comment3": slots[2][2],
        }
        resp = self._client.post("/app_mobile/addgroupgrades", data=payload)
        resp.raise_for_status()
        text = resp.text
        # Réponses d'erreur sont des strings simples, succès = JSON
        try:
            return resp.json()
        except Exception:
            raise RuntimeError(f"Erreur serveur : {text}")

    def add_single_grade(
        self,
        *,
        week: int,
        day: int,
        hour: int,
        classe_id: int,
        subject_id: int,
        eleve_id: int,
        note: int = 21,
        comment: str = "",
        catchup: bool = False,
        date_ts: int | None = None,
    ) -> dict:
        """
        Déclare une note pour un seul élève.
        Utilisé notamment pour les TDs d'info (note=21 = absent/placeholder).
        """
        if date_ts is None:
            semaine = next(
                (s for s in self.data["semaines"] if s[1] == week), None
            )
            if semaine is None:
                raise ValueError(f"Semaine {week} introuvable")
            lundi_ts = semaine[2]
            lundi = datetime.fromtimestamp(lundi_ts, tz=timezone.utc).date()
            date_colle = lundi + timedelta(days=day)
            date_ts = int(
                datetime.combine(
                    date_colle, time(hour // 60, hour % 60)
                ).replace(tzinfo=timezone.utc).timestamp()
            )

        payload = {
            "week": week,
            "day": day,
            "hour": hour,
            "catchup": "true" if catchup else "false",
            "date": date_ts,
            "subject": subject_id,
            "classe": classe_id,
            "student": eleve_id,
            "grade": note,
            "comment": comment,
            "pk": 0,
            "draft_id": 0,
        }
        resp = self._client.post("/app_mobile/addsinglegrade", data=payload)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            raise RuntimeError(f"Erreur serveur : {resp.text}")

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
