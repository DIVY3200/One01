"""Gap 2: questions must not be mistaken for "move to the next topic"."""
import pytest

from api.routes.chat import navigation_intent

ADVANCES = [
    "next",
    "Next topic please",
    "ok got it, continue",
    "I'm ready for the next topic",
    "let's move on",
    "understood, lets go",
    "yes",
    "skip",
]

ANSWERED = [
    "Can you explain it from the start?",
    "Is this clear for beginners?",
    "Why do we continue the loop?",
    "Yes but why is the gradient zero",
    "I don't understand",
    "not clear",
    "start again with an example",
    "what is next after backprop",
    'I choose option 2: "Iterative learning". This is correct! Let\'s move to the next sub-concept.',
]


@pytest.mark.parametrize("message", ADVANCES)
def test_move_on_commands_advance(message):
    assert navigation_intent(message) is True


@pytest.mark.parametrize("message", ANSWERED)
def test_questions_are_answered(message):
    assert navigation_intent(message) is not True


def test_unsure_messages_are_answered_without_a_classifier():
    import asyncio
    from api.routes.chat import is_navigation_command
    assert navigation_intent("ok but the derivative part") is None
    assert asyncio.run(is_navigation_command("ok but the derivative part")) is False


def test_question_in_chat_gets_an_answer_not_a_new_topic(client, subject):
    from helpers import sse
    headers, _, topics = subject
    events = sse(client.post("/api/chat/doubt", json={"topic_id": topics[0]["id"], "message": "Can you explain it from the start?"}, headers=headers).text)
    assert not any(e.get("type") == "topic_advanced" for e in events)
    assert any(e.get("chunk") for e in events)
