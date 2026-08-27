import json

from app.models.nvo_content import NvoProblem, NvoTopic
from app.services.nvo_content_benchmark import benchmark_retrieval


def test_benchmark_reports_readiness_and_latency(db):
    open_slots = {21, 22, 23}
    topic_ids = []
    problem_ids = []
    for slot in range(1, 24):
        topic = NvoTopic(code=f"t{slot}", name=f"T{slot}")
        db.add(topic)
        db.flush()
        topic_ids.append(topic.id)
        problem = NvoProblem(
            topic_id=topic.id, external_ref=f"s{slot}", slot_number=slot,
            answer_format="open" if slot in open_slots else "mcq",
            statement=f"q{slot}",
            options_json=None if slot in open_slots else json.dumps(["А", "Б", "В", "Г"]),
            correct_answer_json=json.dumps(["a"]) if slot in open_slots else json.dumps("А"),
            difficulty="easy",
        )
        db.add(problem)
        db.flush()
        problem_ids.append(problem.id)
    db.commit()

    report = benchmark_retrieval(db, iterations=3)

    assert report["corpus_ready"] is True
    assert report["missing_slots"] == []
    assert "p50" in report["latency_ms"]
    assert "p95" in report["latency_ms"]
    assert report["latency_ms"]["p50"] >= 0

    # Cleanup: delete the problems and topics created in this test
    for problem_id in problem_ids:
        problem = db.query(NvoProblem).filter(NvoProblem.id == problem_id).first()
        if problem:
            db.delete(problem)
    for topic_id in topic_ids:
        topic = db.query(NvoTopic).filter(NvoTopic.id == topic_id).first()
        if topic:
            db.delete(topic)
    db.commit()


def test_benchmark_flags_incomplete_corpus(db):
    report = benchmark_retrieval(db, iterations=2)
    assert report["corpus_ready"] is False
    assert len(report["missing_slots"]) == 23
