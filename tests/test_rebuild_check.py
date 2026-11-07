"""Check that the rebuild comparison really catches changes."""

from scripts.rebuild_check import differences


def test_identical_answers_have_no_differences():
    answers = {"freight": {"predicted_freight": 15.4}, "queue": [("a", 0.7)]}
    assert differences(answers, answers) == []


def test_a_changed_score_is_reported():
    found = differences({"queue": [("a", 0.7)]}, {"queue": [("a", 0.71)]})
    assert found == ["answers.queue[0][1]: 0.7 became 0.71"]


def test_a_reordered_queue_is_reported():
    assert differences({"queue": [("a", 0.7), ("b", 0.6)]}, {"queue": [("b", 0.6), ("a", 0.7)]})


def test_a_missing_item_is_reported():
    assert differences({"loaded": ["x", "y"]}, {"loaded": ["x"]}) == [
        "answers.loaded: 2 items before, 1 after"
    ]


def test_tiny_float_noise_is_ignored():
    assert differences({"x": 0.1 + 0.2}, {"x": 0.3}) == []
