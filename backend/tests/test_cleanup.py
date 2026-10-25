"""Gap 5: deleting a subject removes everything that belonged to it."""
from helpers import BACKPROP_MD, db_rows, hex_id

CHILD_TABLES = [
    ("topics", "subject_id"),
    ("notes", "subject_id"),
    ("progress", "subject_id"),
    ("feedback", "subject_id"),
    ("quiz_sets", "subject_id"),
    ("documents", "subject_id"),
    ("document_chunks", "subject_id"),
]


def test_deleting_a_subject_leaves_no_rows_behind(client, subject):
    headers, subject_id, topics = subject
    topic_ids = [hex_id(t["id"]) for t in topics]
    client.post(f"/api/chat/explain/{topics[0]['id']}", headers=headers)
    client.post("/api/chat/doubt", json={"topic_id": topics[0]["id"], "message": "why does this work"}, headers=headers)
    client.post("/api/quiz/generate", json={"topic_id": topics[0]["id"], "quiz_types": ["mcq"]}, headers=headers)
    subject_quiz = client.post("/api/quiz/generate", json={"subject_id": subject_id, "quiz_types": ["mcq"]}, headers=headers).json()["quiz_sets"][0]
    first = subject_quiz["questions"][0]["correct"]
    client.post("/api/quiz/submit", json={"quiz_set_id": subject_quiz["id"], "answers": [first]}, headers=headers)
    client.post(f"/api/feedback/{subject_id}", json={"content": "more examples"}, headers=headers)
    client.post(f"/api/rag/{subject_id}/documents", headers=headers, files={"file": ("n.md", BACKPROP_MD.encode())})

    sid = hex_id(subject_id)
    assert all(db_rows(f"select count(*) from {t} where {c} = ?", sid)[0][0] > 0 for t, c in CHILD_TABLES)
    placeholders = ",".join("?" * len(topic_ids))
    assert db_rows(f"select count(*) from messages where topic_id in ({placeholders})", *topic_ids)[0][0] > 0

    assert client.delete(f"/api/subjects/{subject_id}", headers=headers).status_code == 200

    leftovers = {t: db_rows(f"select count(*) from {t} where {c} = ?", sid)[0][0] for t, c in CHILD_TABLES}
    leftovers["messages"] = db_rows(f"select count(*) from messages where topic_id in ({placeholders})", *topic_ids)[0][0]
    leftovers["quiz_attempts"] = db_rows("select count(*) from quiz_attempts where quiz_set_id = ?", hex_id(subject_quiz["id"]))[0][0]
    assert leftovers == {name: 0 for name in leftovers}
