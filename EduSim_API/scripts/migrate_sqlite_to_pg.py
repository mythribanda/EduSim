import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
import json

sqlite_path = r"edusim.db"
pg_url = "postgresql://postgres:admin123@localhost:5432/edusim"

print(f"Connecting to SQLite: {sqlite_path}")
s_conn = sqlite3.connect(sqlite_path)
s_conn.row_factory = sqlite3.Row
s_cur = s_conn.cursor()

print(f"Connecting to PostgreSQL: {pg_url}")
p_conn = psycopg2.connect(pg_url)
p_cur = p_conn.cursor()
p_cur.execute("SET session_replication_role = 'replica';")
p_conn.commit()

# Get list of tables in PostgreSQL public schema
p_cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
""")
pg_tables = {row[0] for row in p_cur.fetchall()}
print(f"PostgreSQL tables: {sorted(list(pg_tables))}")

# We should migrate tables in order of foreign key dependencies
# Tables to migrate:
table_order = [
    "curriculum_classes",
    "subjects",
    "chapters",
    "topics",
    "users",
    "student_profiles",
    "user_settings",
    "user_sessions",
    "chat_history",
    "formula_history",
    "simulation_history",
    "student_topic_mastery",
    "session_events",
    "questions",
    "books",
    "curriculum_nodes"
]

for table in table_order:
    if table not in pg_tables:
        print(f"Skipping {table} (not in PostgreSQL)")
        continue
    
    # Check if table exists in SQLite
    s_cur.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
    if s_cur.fetchone()[0] == 0:
        print(f"Table {table} not in SQLite, skipping")
        continue

    # Fetch columns in SQLite
    s_cur.execute(f"PRAGMA table_info({table})")
    s_cols = [col["name"] for col in s_cur.fetchall()]
    
    # Fetch columns in PostgreSQL
    p_cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = '{table}';
    """)
    pg_col_info = {row[0]: row[1] for row in p_cur.fetchall()}
    common_cols = [c for c in s_cols if c in pg_col_info]
    
    print(f"\nMigrating {table} ({len(common_cols)} columns)...")
    
    # Check if table already has rows in PostgreSQL
    p_cur.execute(f"SELECT count(*) FROM {table}")
    existing_pg_count = p_cur.fetchone()[0]
    if existing_pg_count > 0:
        print(f"  Table {table} already has {existing_pg_count} rows in PostgreSQL. Skipping insert.")
        continue

    col_list_str = ", ".join(f'"{c}"' for c in common_cols)
    placeholders = ", ".join(["%s"] * len(common_cols))
    insert_sql = f'INSERT INTO "{table}" ({col_list_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
    
    s_cur.execute(f"SELECT {col_list_str} FROM {table}")
    rows = s_cur.fetchall()
    print(f"  Found {len(rows)} rows in SQLite {table}")
    
    batch = []
    for r in rows:
        row_vals = []
        for c in common_cols:
            val = r[c]
            # Convert boolean or json if needed
            dtype = pg_col_info[c].lower()
            if dtype == 'boolean' and val is not None:
                val = bool(val)
            elif 'json' in dtype and isinstance(val, (dict, list)):
                val = json.dumps(val)
            elif dtype == 'uuid' and val is not None:
                import uuid
                try:
                    val = str(uuid.UUID(str(val)))
                except Exception:
                    # If it's a test integer like 1, generate a deterministic UUID or skip
                    val = str(uuid.UUID(int=int(val))) if str(val).isdigit() else None
            row_vals.append(val)
        batch.append(tuple(row_vals))
        
        if len(batch) >= 1000:
            execute_batch(p_cur, insert_sql, batch)
            p_conn.commit()
            batch = []
    
    if batch:
        execute_batch(p_cur, insert_sql, batch)
        p_conn.commit()
        
    p_cur.execute(f'SELECT count(*) FROM "{table}"')
    final_count = p_cur.fetchone()[0]
    print(f"  PostgreSQL {table} now has {final_count} rows.")

p_cur.execute("SET session_replication_role = 'origin';")
p_conn.commit()
p_conn.close()
s_conn.close()
print("\nMigration completed successfully!")
