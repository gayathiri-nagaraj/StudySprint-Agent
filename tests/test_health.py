import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'health.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )


def test_health_check_returns_ok(app) -> None:
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "studysprint-agent",
    }
