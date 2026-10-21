"""Held out. The feedback export of replica-holdout-feedback-status, as a feedback_data table,
and what the note must say of it: the words a person would use for each group, and which group
a release fixed."""

TABLE = {
    "seed": "chatsvc-feedback-holdout",
    "rows": [
        (20, [("1.6.1", "up", None)]),
        (2, [("1.6.1", "down", "voice-input-fails")]),
        (6, [("1.7.0", "up", None)]),
        (4, [("1.7.0", "down", "voice-input-fails")]),
        (2, [("1.7.0", "down", "voice-input-fails"), ("1.7.1", "down", "voice-input-fails")]),
        (3, [("1.7.1", "down", "voice-input-fails")]),
        (5, [("1.7.0", "down", "attachment-upload-error")]),
        (1, [("1.7.0", "down", "attachment-upload-error"), ("1.7.1", "up", None)]),
        (3, [("1.7.0", "down", "slow-first-token")]),
        (6, [("1.7.0", "down", "slow-first-token")]),
        (4, [("1.7.0", "down", "wrong-language")]),
        (5, [("1.7.1", "up", None)]),
        (1, [("1.7.1", "down", None)]),
        (8, [("1.7.1", "up", None)]),
    ],
    "channels": {
        1: "mobile",
        2: "mobile",
        3: "mobile",
        4: "mobile",
        5: "mobile",
        6: "mobile",
        7: "mobile",
        8: "mobile",
        9: "web",
        10: "web",
        11: "mobile",
        12: "mobile",
        13: "web",
    },
    "comments": {
        "voice-input-fails": (
            "tapping the mic does nothing",
            "dictation stopped working after the update",
            "voice question never sent",
        ),
        "attachment-upload-error": (
            "my PDF won't upload",
            "upload spinner forever then error",
            "can't attach screenshots anymore",
        ),
    },
}

WORDS = {
    "voice-input-fails": r"voice|dictat|speech|microphone|\bmic\b|speak",
    "attachment-upload-error": r"attach|upload",
    "slow-first-token": (
        r"slow|first[- ]token|first word|latenc|time[- ]to[- ]first|takes? (long|ages)|delay"
        r"|starts? late"
    ),
}

FIXED = {"attachment-upload-error"}
