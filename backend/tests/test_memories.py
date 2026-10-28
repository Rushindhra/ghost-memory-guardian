from conftest import PNG, make_wav, mem


def test_crud_roundtrip(client):
    r = client.post("/api/memories", json=mem("Lake day", "We swam all afternoon.", people=["Ann", "Bo"], tags=["Lake", "summer"]))
    assert r.status_code == 201
    m = r.json()
    assert m["people"] == ["Ann", "Bo"] and m["tags"] == ["lake", "summer"] and m["sort_date"] == "1990-05-01"
    assert client.get(f"/api/memories/{m['id']}").json()["title"] == "Lake day"
    upd = client.put(f"/api/memories/{m['id']}", json=mem("Lake day 2", "Changed", memory_date="1991"))
    assert upd.json()["title"] == "Lake day 2" and upd.json()["sort_date"] == "1991-01-01"
    assert client.get("/api/memories").json()["total"] == 1
    assert client.delete(f"/api/memories/{m['id']}").status_code == 200
    assert client.get(f"/api/memories/{m['id']}").status_code == 404


def test_validation_rejects_bad_input(client):
    assert client.post("/api/memories", json={"title": "", "body": "x"}).status_code == 422
    assert client.post("/api/memories", json=mem(memory_date="1990-13-45")).status_code == 422
    assert client.post("/api/memories", json=mem(memory_date="June 1990")).status_code == 422
    assert client.post("/api/memories", json=mem(people=["x" * 200])).status_code == 422
    assert client.put("/api/memories/nope", json=mem()).status_code == 404


def test_filters_and_facets(client):
    client.post("/api/memories", json=mem("A", "alpha", memory_date="1980", people=["Ann"], category="love", tags=["x"]))
    client.post("/api/memories", json=mem("B", "beta", memory_date="1990-06", people=["Bo"], category="work", tags=["y"]))
    client.post("/api/memories", json=mem("C", "gamma needle", memory_date="2000-01-02", people=["Ann", "Bo"], category="work", tags=["x", "y"]))
    count = lambda **p: client.get("/api/memories", params=p).json()["total"]  # noqa: E731
    assert count(person="Ann") == 2 and count(category="work") == 2 and count(tag="x") == 2
    assert count(q="needle") == 1 and count(q="Bo") == 2  # people names are searchable
    assert count(date_from="1985", date_to="1995") == 1
    assert count(date_to="1989") == 1 and count(date_to="1990") == 2  # a bare year is inclusive
    f = client.get("/api/memories/facets").json()
    assert {p["name"] for p in f["people"]} == {"Ann", "Bo"}


def test_timeline_groups_by_year_and_undated(client):
    client.post("/api/memories", json=mem("Old", memory_date="1950"))
    client.post("/api/memories", json=mem("New", memory_date="2001-03"))
    client.post("/api/memories", json={"title": "No date", "body": "?"})
    t = client.get("/api/timeline").json()
    assert [y["year"] for y in t["years"]] == ["1950", "2001"] and len(t["undated"]) == 1


def test_upload_and_file_deletion(client, ctx):
    m = client.post("/api/memories", json=mem()).json()
    r = client.post(f"/api/memories/{m['id']}/attachments", files={"file": ("../../evil.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["kind"] == "photo" and "/" not in att["original_name"]
    stored = list(ctx.settings.files_dir.iterdir())
    assert len(stored) == 1 and stored[0].suffix == ".png"
    got = client.get(att["url"])
    assert got.status_code == 200 and got.content == PNG and got.headers["x-content-type-options"] == "nosniff"
    out = client.delete(f"/api/memories/{m['id']}").json()
    assert out["files_removed"] == 1 and list(ctx.settings.files_dir.iterdir()) == []
    assert client.get(att["url"]).status_code == 404


def test_upload_rejections(client, ctx):
    m = client.post("/api/memories", json=mem()).json()
    url = f"/api/memories/{m['id']}/attachments"
    assert client.post(url, files={"file": ("a.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")}).status_code == 400
    assert client.post(url, files={"file": ("a.png", b"", "image/png")}).status_code == 400
    assert client.post(url, files={"file": ("big.wav", make_wav(0.2) + b"\0" * (2 * 1024 * 1024), "audio/wav")}).status_code == 400
    # an extension/MIME lie does not fool the content sniffing
    r = client.post(url, files={"file": ("photo.png", b"%PDF-1.4 fake", "image/png")})
    assert r.status_code == 201 and r.json()["kind"] == "document"
    assert client.post("/api/memories/missing/attachments", files={"file": ("a.png", PNG, "image/png")}).status_code == 404
    assert list(ctx.settings.files_dir.glob(".incoming-*")) == []  # no temp-file leaks


def test_path_traversal_ids_never_reach_disk(client):
    for bad in ("..%2f..%2fetc%2fpasswd", "../x", "%00"):
        assert client.get(f"/api/files/{bad}").status_code == 404


def test_text_document_attachment_is_searchable(client):
    m = client.post("/api/memories", json=mem("Letter", "see attachment")).json()
    client.post(f"/api/memories/{m['id']}/attachments", files={"file": ("l.txt", b"The zeppelin landed at midnight.", "text/plain")})
    assert client.get("/api/memories", params={"q": "zeppelin"}).json()["total"] == 1
    hits = client.post("/api/search", json={"query": "zeppelin landing", "ask": False}).json()
    assert hits["results"] and hits["results"][0]["memory"]["id"] == m["id"]


def test_deleting_memory_deletes_confirmed_transcript(client):
    wav = make_wav()
    t = client.post("/api/oral", files={"file": ("s.wav", wav, "audio/wav")}).json()["transcript"]
    m = client.post(f"/api/oral/{t['id']}/confirm", json={"title": "Oral", "category": "family"}).json()
    assert client.get("/api/oral").json()["items"][0]["status"] == "confirmed"
    client.delete(f"/api/memories/{m['id']}")
    assert client.get("/api/oral").json()["items"] == []
