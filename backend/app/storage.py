import json
import sqlite3
from pathlib import Path

from app.models import AssessmentOutput, StoredAssessment, UseCaseInput


class AssessmentRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assessments (
                    use_case_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    source_payload TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(assessments)").fetchall()
            }
            if "source_payload" not in columns:
                connection.execute("ALTER TABLE assessments ADD COLUMN source_payload TEXT")

    def save(
        self,
        assessment: AssessmentOutput,
        status: str = "in_review",
        source_use_case: UseCaseInput | None = None,
    ) -> StoredAssessment:
        payload = assessment.model_dump_json()
        source_payload = source_use_case.model_dump_json() if source_use_case is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assessments (use_case_id, status, payload, source_payload, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(use_case_id) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload,
                    source_payload = COALESCE(excluded.source_payload, assessments.source_payload),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (assessment.use_case_id, status, payload, source_payload),
            )
        return StoredAssessment(assessment=assessment, status=status, source_use_case=source_use_case)

    def get(self, use_case_id: str) -> StoredAssessment | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, payload, source_payload FROM assessments WHERE use_case_id = ?",
                (use_case_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredAssessment(
            assessment=AssessmentOutput.model_validate(json.loads(row["payload"])),
            status=row["status"],
            source_use_case=_load_source_use_case(row["source_payload"]),
        )

    def list_all(self) -> list[StoredAssessment]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, payload, source_payload FROM assessments ORDER BY updated_at DESC"
            ).fetchall()
        return [
            StoredAssessment(
                assessment=AssessmentOutput.model_validate(json.loads(row["payload"])),
                status=row["status"],
                source_use_case=_load_source_use_case(row["source_payload"]),
            )
            for row in rows
        ]

    def confirm(self, use_case_id: str, reviewer_overrides: dict) -> StoredAssessment:
        stored = self.get(use_case_id)
        if stored is None:
            raise KeyError(use_case_id)

        updated = stored.assessment.model_copy(
            update={
                "human_reviewed": True,
                "reviewer_overrides": reviewer_overrides,
            }
        )
        return self.save(updated, status="sent", source_use_case=stored.source_use_case)


def _load_source_use_case(payload: str | None) -> UseCaseInput | None:
    if not payload:
        return None
    return UseCaseInput.model_validate(json.loads(payload))
