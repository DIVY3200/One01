"""Gaps 3-4: lesson notes are saved, quiz average is a real average, study time is tracked."""
from helpers import db_rows, hex_id


def submit(client, headers, quiz_set, all_correct: bool):
    answers = [q["correct"] if all_correct else "Z" for q in quiz_set["questions"]]
    response = client.post("/api/quiz/submit", json={"quiz_set_id": quiz_set["id"], "answers": answers}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["analysis"]["score"]


def progress(client, headers, subject_id):
    return client.get(f"/api/progress/{subject_id}", headers=headers).json()


def test_quiz_average_is_the_mean_of_all_attempts(client, subject):
    headers, subject_id, topics = subject
    quiz = client.post("/api/quiz/generate", json={"topic_id": topics[0]["id"], "quiz_types": ["mcq"]}, headers=headers).json()["quiz_sets"][0]

    assert submit(client, headers, quiz, all_correct=True) == 100
    assert progress(client, headers, subject_id)["avg_quiz_score"] == 100  # old formula showed 50

    assert submit(client, headers, quiz, all_correct=False) == 0
    assert progress(client, headers, subject_id)["avg_quiz_score"] == 50  # old formula showed 25


def test_subject_wide_quizzes_count_towards_progress(client, subject):
    """The question bank page sends no topic; those quizzes used to be ignored."""
    headers, subject_id, _ = subject
    quiz = client.post("/api/quiz/generate", json={"topic_id": None, "subject_id": subject_id, "quiz_types": ["mcq"]}, headers=headers).json()["quiz_sets"][0]
    submit(client, headers, quiz, all_correct=True)
    stats = progress(client, headers, subject_id)
    assert stats["avg_quiz_score"] == 100
    assert stats["strong_concepts"]


def test_quiz_tab_links_quizzes_to_the_topic_by_title(client, subject):
    headers, subject_id, topics = subject
    quiz = client.post("/api/quiz/generate", json={"subject_id": subject_id, "topic_title": topics[1]["title"], "quiz_types": ["mcq"]}, headers=headers).json()["quiz_sets"][0]
    linked = db_rows("select topic_id, subject_id from quiz_sets where id = ?", hex_id(quiz["id"]))[0]
    assert linked == (hex_id(topics[1]["id"]), hex_id(subject_id))


def test_study_heartbeat_adds_one_minute_and_ignores_rapid_repeats(client, subject):
    headers, subject_id, _ = subject
    assert progress(client, headers, subject_id)["time_spent_minutes"] == 0
    first = client.post(f"/api/progress/{subject_id}/heartbeat", headers=headers).json()
    second = client.post(f"/api/progress/{subject_id}/heartbeat", headers=headers).json()
    assert first == {"counted": True, "time_spent_minutes": 1}
    assert second == {"counted": False}
    assert progress(client, headers, subject_id)["time_spent_minutes"] == 1


def test_completing_a_topic_twice_counts_once(client, subject):
    headers, subject_id, topics = subject
    for _ in range(2):
        assert client.patch(f"/api/topics/{topics[0]['id']}/complete", headers=headers).status_code == 200
    assert progress(client, headers, subject_id)["completed_topics"] == 1


def test_lesson_notes_are_saved_and_user_edits_are_kept(client, subject):
    headers, subject_id, topics = subject
    topic = topics[0]
    client.post(f"/api/chat/explain/{topic['id']}", headers=headers)

    notes = client.get(f"/api/notes/{subject_id}", headers=headers).json()
    topic_notes = [n for n in notes if n["topic_id"] == topic["id"]]
    assert len(topic_notes) == 1 and topic_notes[0]["topic_title"] == topic["title"]
    assert topic_notes[0]["content"].strip()

    # The student edits the note; teaching the topic again must not overwrite it
    client.put(f"/api/notes/{topic_notes[0]['id']}", json={"content": "My own notes"}, headers=headers)
    client.post(f"/api/chat/explain/{topic['id']}", headers=headers)
    notes = client.get(f"/api/notes/{subject_id}", headers=headers).json()
    assert [n["content"] for n in notes if n["topic_id"] == topic["id"]] == ["My own notes"]
