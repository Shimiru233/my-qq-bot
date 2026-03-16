import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="testdb",
    user="readonly_user",
    password="password"
)

def check_song_exists(keyword: str) -> bool:
    sql = """
    SELECT 1
    FROM arcaea_assets
    WHERE name ILIKE %s
       OR EXISTS (
           SELECT 1
           FROM unnest(alias) a
           WHERE a ILIKE %s
       )
    LIMIT 1
    """

    pattern = f"%{keyword}%"

    with conn.cursor() as cur:
        cur.execute(sql, (pattern, pattern))
        return cur.fetchone() is not None