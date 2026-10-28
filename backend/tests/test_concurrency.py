"""Regression: a real server hands a request's connection across worker threads (TestClient does not)."""
from concurrent.futures import ThreadPoolExecutor
import threading

from app.database import db


def test_connection_usable_from_another_thread(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite3")
    db.migrate(conn)
    out: list[int] = []
    t = threading.Thread(target=lambda: out.append(conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]))
    t.start(); t.join()
    assert out == [0]


def test_parallel_api_requests_do_not_error(client):
    def hit(path: str) -> int:
        return client.get(path).status_code

    paths = ["/api/system/overview", "/api/memories/facets", "/api/privacy/lock-status", "/api/system/health"] * 8
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(hit, paths))
    assert set(codes) == {200}
