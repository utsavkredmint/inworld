import sqlite3
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "db.sqlite3"


def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            greeting TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            persona TEXT DEFAULT '',
            voice TEXT DEFAULT 'Riya',
            language TEXT DEFAULT 'hi',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            call_uuid TEXT,
            phone_number TEXT NOT NULL,
            direction TEXT DEFAULT 'outbound',
            status TEXT DEFAULT 'queued',
            duration_sec INTEGER DEFAULT 0,
            recording_url TEXT,
            started_at TEXT,
            ended_at TEXT,
            created_at TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL REFERENCES calls(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            status TEXT DEFAULT 'running', -- running, paused, completed
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaign_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id),
            phone_number TEXT NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'pending', -- pending, calling, completed, failed
            call_id TEXT REFERENCES calls(id)
        );

        CREATE TABLE IF NOT EXISTS voices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ref_audio_path TEXT NOT NULL,
            ref_text TEXT DEFAULT '',
            language TEXT DEFAULT 'hindi',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_calls_agent ON calls(agent_id);
        CREATE INDEX IF NOT EXISTS idx_calls_uuid ON calls(call_uuid);
        CREATE INDEX IF NOT EXISTS idx_messages_call ON messages(call_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_campaign ON campaign_contacts(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_status ON campaign_contacts(status);
    """)
    conn.commit()

    # Auto-migration: Check if 'language' column exists in 'voices'
    try:
        cursor = conn.execute("PRAGMA table_info(voices)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'language' not in columns:
            log.info("[DB] Migrating 'voices' table: adding 'language' column")
            conn.execute("ALTER TABLE voices ADD COLUMN language TEXT DEFAULT 'hindi'")
            conn.commit()
    except Exception as e:
        log.warning(f"[DB] Migration check failed: {e}")

    conn.close()
    log.info("[DB] Database initialized")


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _now():
    return datetime.utcnow().isoformat() + "Z"


# ── Agents ──

def create_agent(name, greeting, system_prompt, persona="", voice="Riya", language="hi"):
    conn = get_db()
    agent_id = uuid.uuid4().hex[:12]
    now = _now()
    conn.execute(
        "INSERT INTO agents (id, name, greeting, system_prompt, persona, voice, language, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (agent_id, name, greeting, system_prompt, persona, voice, language, "active", now, now)
    )
    conn.commit()
    agent = _row_to_dict(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())
    conn.close()
    return agent


def get_agent(agent_id):
    conn = get_db()
    agent = _row_to_dict(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())
    conn.close()
    return agent


def list_agents():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, COUNT(c.id) as total_calls
        FROM agents a LEFT JOIN calls c ON a.id = c.agent_id
        GROUP BY a.id ORDER BY a.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_agent(agent_id, **kwargs):
    conn = get_db()
    kwargs["updated_at"] = _now()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [agent_id]
    conn.execute(f"UPDATE agents SET {sets} WHERE id=?", vals)
    conn.commit()
    agent = _row_to_dict(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())
    conn.close()
    return agent


def delete_agent(agent_id):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE call_id IN (SELECT id FROM calls WHERE agent_id=?)", (agent_id,))
    conn.execute("DELETE FROM calls WHERE agent_id=?", (agent_id,))
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()
    return True


# ── Calls ──

def create_call(agent_id, phone_number):
    conn = get_db()
    call_id = uuid.uuid4().hex[:12]
    now = _now()
    conn.execute(
        "INSERT INTO calls (id, agent_id, phone_number, direction, status, created_at) VALUES (?,?,?,?,?,?)",
        (call_id, agent_id, phone_number, "outbound", "queued", now)
    )
    conn.commit()
    call = _row_to_dict(conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone())
    conn.close()
    return call


def get_call(call_id):
    conn = get_db()
    call = _row_to_dict(conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone())
    conn.close()
    return call


def get_call_by_uuid(call_uuid):
    conn = get_db()
    call = _row_to_dict(conn.execute("SELECT * FROM calls WHERE call_uuid=?", (call_uuid,)).fetchone())
    conn.close()
    return call


def list_calls(agent_id=None, limit=50, offset=0):
    conn = get_db()
    if agent_id:
        rows = conn.execute("""
            SELECT c.*, a.name as agent_name,
                   (SELECT COUNT(*) FROM messages m WHERE m.call_id=c.id) as message_count
            FROM calls c JOIN agents a ON c.agent_id=a.id
            WHERE c.agent_id=? ORDER BY c.created_at DESC LIMIT ? OFFSET ?
        """, (agent_id, limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM calls WHERE agent_id=?", (agent_id,)).fetchone()[0]
    else:
        rows = conn.execute("""
            SELECT c.*, a.name as agent_name,
                   (SELECT COUNT(*) FROM messages m WHERE m.call_id=c.id) as message_count
            FROM calls c JOIN agents a ON c.agent_id=a.id
            ORDER BY c.created_at DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def update_call(call_id, **kwargs):
    conn = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [call_id]
    conn.execute(f"UPDATE calls SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


# ── Messages ──

def add_message(call_id, role, content):
    conn = get_db()
    now = _now()
    conn.execute(
        "INSERT INTO messages (call_id, role, content, timestamp) VALUES (?,?,?,?)",
        (call_id, role, content, now)
    )
    conn.commit()
    conn.close()


def get_messages(call_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages WHERE call_id=? ORDER BY id", (call_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Campaigns ──

def create_campaign(name, agent_id):
    conn = get_db()
    campaign_id = uuid.uuid4().hex[:12]
    now = _now()
    conn.execute(
        "INSERT INTO campaigns (id, name, agent_id, status, created_at) VALUES (?,?,?,?,?)",
        (campaign_id, name, agent_id, "running", now)
    )
    conn.commit()
    campaign = _row_to_dict(conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone())
    conn.close()
    return campaign


def add_campaign_contacts(campaign_id, contacts):
    """contacts: list of dicts {'phone_number': str, 'name': str}"""
    conn = get_db()
    for c in contacts:
        conn.execute(
            "INSERT INTO campaign_contacts (campaign_id, phone_number, name, status) VALUES (?,?,?,?)",
            (campaign_id, c["phone_number"], c.get("name", ""), "pending")
        )
    conn.commit()
    conn.close()


def list_campaigns():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, a.name as agent_name,
               (SELECT COUNT(*) FROM campaign_contacts cc WHERE cc.campaign_id=c.id) as total_contacts,
               (SELECT COUNT(*) FROM campaign_contacts cc WHERE cc.campaign_id=c.id AND cc.status='completed') as completed_contacts,
               (SELECT COUNT(*) FROM campaign_contacts cc WHERE cc.campaign_id=c.id AND cc.status='failed') as failed_contacts
        FROM campaigns c JOIN agents a ON c.agent_id=a.id
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()
    
    campaigns = []
    for r in rows:
        d = dict(r)
        total = d["total_contacts"]
        comp = d["completed_contacts"]
        d["success_rate"] = f"{int((comp / total * 100))}%" if total > 0 else "0%"
        campaigns.append(d)
    return campaigns


def get_campaign(campaign_id):
    conn = get_db()
    campaign = _row_to_dict(conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone())
    conn.close()
    return campaign


def update_campaign_status(campaign_id, status):
    conn = get_db()
    conn.execute("UPDATE campaigns SET status=? WHERE id=?", (status, campaign_id))
    conn.commit()
    conn.close()


def delete_campaign(campaign_id):
    conn = get_db()
    conn.execute("DELETE FROM campaign_contacts WHERE campaign_id=?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id=?", (campaign_id,))
    conn.commit()
    conn.close()


def get_next_pending_contact(campaign_id):
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM campaign_contacts 
        WHERE campaign_id=? AND status='pending' 
        LIMIT 1
    """, (campaign_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def update_contact_status(contact_id, status, call_id=None):
    conn = get_db()
    if call_id:
        conn.execute("UPDATE campaign_contacts SET status=?, call_id=? WHERE id=?", (status, call_id, contact_id))
    else:
        conn.execute("UPDATE campaign_contacts SET status=? WHERE id=?", (status, contact_id))
    conn.commit()
    conn.close()
# ── Voices ──

def create_voice(name, ref_audio_path, ref_text="", language="hindi"):
    conn = get_db()
    voice_id = uuid.uuid4().hex[:12]
    now = _now()
    conn.execute(
        "INSERT INTO voices (id, name, ref_audio_path, ref_text, language, created_at) VALUES (?,?,?,?,?,?)",
        (voice_id, name, ref_audio_path, ref_text, language, now)
    )
    conn.commit()
    voice = _row_to_dict(conn.execute("SELECT * FROM voices WHERE id=?", (voice_id,)).fetchone())
    conn.close()
    return voice


def get_voice(voice_id):
    conn = get_db()
    voice = _row_to_dict(conn.execute("SELECT * FROM voices WHERE id=?", (voice_id,)).fetchone())
    conn.close()
    return voice


def list_voices():
    conn = get_db()
    rows = conn.execute("SELECT * FROM voices ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_voice(voice_id):
    conn = get_db()
    conn.execute("DELETE FROM voices WHERE id=?", (voice_id,))
    conn.commit()
    conn.close()
    return True
