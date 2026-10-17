"""
Persistent SQLite Memory Store for ChainSight Agent.
Stores incident records and observed/simulated outcomes.
Provides deterministic, transparent keyword & context similarity recall without third-party vector databases.
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from schemas import IncidentMemoryRecord

logger = logging.getLogger(__name__)


class IncidentMemoryStore:
    def __init__(self, db_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.db_path = db_path or (base_dir / "memory" / "chainsight_memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create incidents memory table if not exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    normalized_location TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    affected_entities TEXT NOT NULL,
                    selected_mitigation TEXT NOT NULL,
                    estimated_delay_hours REAL NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    observed_outcome TEXT,
                    is_simulated INTEGER NOT NULL DEFAULT 1,
                    evidence_summary TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Create indexing for fast lookup
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_incident_loc ON incident_memory(normalized_location)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_incident_type ON incident_memory(event_type)"
            )
            conn.commit()

    def save_incident(
        self,
        event_type: str,
        normalized_location: str,
        severity: str,
        affected_entities: List[str],
        selected_mitigation: str,
        estimated_delay_hours: float,
        estimated_cost_usd: float,
        evidence_summary: str,
        observed_outcome: Optional[str] = None,
        is_simulated: bool = True,
    ) -> int:
        """Store an incident memory record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        entities_json = json.dumps(affected_entities)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO incident_memory (
                    event_type, normalized_location, severity, affected_entities,
                    selected_mitigation, estimated_delay_hours, estimated_cost_usd,
                    observed_outcome, is_simulated, evidence_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type.lower().strip(),
                    normalized_location.lower().strip(),
                    severity.lower().strip(),
                    entities_json,
                    selected_mitigation,
                    float(estimated_delay_hours),
                    float(estimated_cost_usd),
                    observed_outcome,
                    1 if is_simulated else 0,
                    evidence_summary,
                    now_iso,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def recall_similar_incidents(
        self,
        event_type: str,
        location: str,
        severity: Optional[str] = None,
        affected_entities: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[IncidentMemoryRecord]:
        """
        Recall relevant incidents using transparent scoring:
        - Exact location match: +40 pts
        - Location substring/contains: +25 pts
        - Exact event_type match: +30 pts
        - Severity match: +15 pts
        - Entity overlap: +5 pts per matching entity (up to +15 pts)
        """
        norm_type = event_type.lower().strip()
        norm_loc = location.lower().strip()
        norm_sev = severity.lower().strip() if severity else ""
        entity_set = set(e.upper() for e in (affected_entities or []))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incident_memory ORDER BY id DESC")
            rows = cursor.fetchall()

        scored_records: List[tuple[float, IncidentMemoryRecord]] = []
        for r in rows:
            score = 0.0
            r_loc = str(r["normalized_location"]).lower()
            r_type = str(r["event_type"]).lower()
            r_sev = str(r["severity"]).lower()

            try:
                r_entities = set(e.upper() for e in json.loads(r["affected_entities"]))
            except Exception:
                r_entities = set()

            # Location match
            if norm_loc == r_loc:
                score += 40.0
            elif norm_loc in r_loc or r_loc in norm_loc:
                score += 25.0

            # Event type match
            if norm_type == r_type:
                score += 30.0
            elif norm_type in r_type or r_type in norm_type:
                score += 15.0

            # Severity match
            if norm_sev and norm_sev == r_sev:
                score += 15.0

            # Entity overlap
            overlap = len(entity_set.intersection(r_entities))
            score += min(overlap * 5.0, 15.0)

            if score > 20.0:  # Meaningful relevance threshold
                record = IncidentMemoryRecord(
                    memory_id=r["id"],
                    event_type=r["event_type"],
                    normalized_location=r["normalized_location"],
                    severity=r["severity"],
                    affected_entities=list(r_entities),
                    selected_mitigation=r["selected_mitigation"],
                    estimated_delay_hours=r["estimated_delay_hours"],
                    estimated_cost_usd=r["estimated_cost_usd"],
                    observed_outcome=r["observed_outcome"],
                    is_simulated=bool(r["is_simulated"]),
                    evidence_summary=r["evidence_summary"],
                    created_at=r["created_at"],
                )
                scored_records.append((score, record))

        scored_records.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_records[:limit]]

    def seed_initial_demo_memories(self) -> None:
        """Seed benchmark historical memories if database is empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM incident_memory")
            count = cursor.fetchone()["count"]
            if count > 0:
                return

        self.save_incident(
            event_type="cyclone",
            normalized_location="shanghai, china",
            severity="high",
            affected_entities=["PORT-01", "PLANT-01", "CUST-01"],
            selected_mitigation="Divert Feeder Cargo to Port of Busan (PORT-03)",
            estimated_delay_hours=48.0,
            estimated_cost_usd=16250.0,
            evidence_summary="Typhoon Muifa gale force winds exceeded 65 km/h. Feeder diversion completed within 28 hours.",
            observed_outcome="HISTORICAL_ARCHIVE: Reroute prevented 3-day line stoppage at Detroit Plant Alpha. Customer SLA intact.",
            is_simulated=False,
        )

        self.save_incident(
            event_type="port_congestion",
            normalized_location="los angeles, ca, usa",
            severity="critical",
            affected_entities=["PORT-04", "PLANT-01", "PLANT-02"],
            selected_mitigation="Reroute Ocean Freight to Port of Long Beach (PORT-05)",
            estimated_delay_hours=72.0,
            estimated_cost_usd=8400.0,
            evidence_summary="Anchor queue exceeded 18 vessels at San Pedro Bay. Berth shift executed.",
            observed_outcome="HISTORICAL_ARCHIVE: Truck turn times at Long Beach were 35% faster than LA main terminal.",
            is_simulated=False,
        )
