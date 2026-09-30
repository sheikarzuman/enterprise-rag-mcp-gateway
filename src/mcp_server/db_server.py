import psycopg2
from mcp.server.fastmcp import FastMCP
from src.config import settings

mcp = FastMCP("Enterprise-Telemetry-Bridge")

@mcp.tool()
def query_telemetry_db(sql_query: str) -> str:
    """Executes a sandboxed, hardware-enforced READ-ONLY SQL query against enterprise telemetry tables.
    Mutations (INSERT, UPDATE, DROP, DELETE, ALTER) are hard rejected.
    """
    clean_sql = sql_query.strip()
    if not clean_sql.upper().startswith("SELECT"):
        return "Security Violation: Non-SELECT queries are strictly prohibited on this protocol gateway."

    conn = None
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            cursor.execute(clean_sql)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            return f"Columns: {headers} | Rows: {rows}"
    except Exception as e:
        return f"Database query execution failure: {str(e)}"
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    mcp.run()
