from sherlock.redaction import redact


def test_redacts_aws_key():
    out = redact("key=AKIAIOSFODNN7EXAMPLE in config")
    assert "AKIA" not in out
    assert "REDACTED:AWS_ACCESS_KEY" in out


def test_redacts_password_kv():
    out = redact('database password: "hunter2supersecret"')
    assert "hunter2supersecret" not in out
    assert "REDACTED" in out


def test_redacts_connection_string_password():
    out = redact("postgres://user:s3cr3tpw@db.internal:5432/app")
    assert "s3cr3tpw" not in out
    assert "user" in out  # username preserved, only the password is scrubbed


def test_redacts_jwt_and_email():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N"
    out = redact(f"token {jwt} for alice@example.com")
    assert jwt not in out
    assert "alice@example.com" not in out


def test_leaves_benign_text_untouched():
    text = "OOMKilled: container exceeded its memory limit of 256Mi"
    assert redact(text) == text


def test_handles_empty():
    assert redact("") == ""
