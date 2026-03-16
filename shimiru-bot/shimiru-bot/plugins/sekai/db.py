import psycopg2

def check_song_exists(conn, keyword: str) -> bool:
    """
    arcaea_assets テーブルの name と alias(text[]) を曖昧検索
    見つかったら True、なければ False
    """

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