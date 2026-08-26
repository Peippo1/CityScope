from pathlib import Path

from scripts.dev import public_web_environment


def test_public_web_environment_does_not_forward_server_secrets(tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "NEXT_PUBLIC_FIREBASE_PROJECT_ID=cityscope-test\n"
        "GEMINI_API_KEY=server-secret\n"
    )

    environment = public_web_environment(env_file, {"PATH": "/usr/bin"})

    assert environment["PATH"] == "/usr/bin"
    assert environment["NEXT_PUBLIC_FIREBASE_PROJECT_ID"] == "cityscope-test"
    assert "GEMINI_API_KEY" not in environment


def test_explicit_public_environment_overrides_local_file(tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("NEXT_PUBLIC_CITYSCOPE_API_URL=http://localhost:8000\n")

    environment = public_web_environment(
        env_file,
        {"NEXT_PUBLIC_CITYSCOPE_API_URL": "https://api.example"},
    )

    assert environment["NEXT_PUBLIC_CITYSCOPE_API_URL"] == "https://api.example"


def test_public_values_do_not_interpolate_server_secrets(tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "SERVER_SECRET=do-not-forward\n"
        "NEXT_PUBLIC_REFERENCE=${SERVER_SECRET}\n"
    )

    environment = public_web_environment(env_file, {})

    assert environment["NEXT_PUBLIC_REFERENCE"] == "${SERVER_SECRET}"
    assert "do-not-forward" not in environment.values()
