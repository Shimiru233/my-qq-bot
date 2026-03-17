import psycopg2
import json

data = {
  "sayonarahatsukoi": "Sayonara Hatsukoi",
  "fairytale": "Fairytale",
  "vexaria": "Vexaria",
  "rise": "Rise"
}

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="arcaea_assets",
    user="postgres",
    password="root"
)

with conn.cursor() as cur:
    for song_id, title in data.items():

        # 插入一条 alias（默认 alias = title）
        cur.execute(
            """
            INSERT INTO m_alias (id, alias, title)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (song_id, title.lower(), title)
        )

conn.commit()
conn.close()
