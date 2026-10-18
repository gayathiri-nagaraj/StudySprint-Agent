from app import create_app


def test_navigation_exposes_accessible_theme_toggle(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'theme.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )

    client = app.test_client()
    client.post("/register", data={"email": "student@example.com", "password": "correct-horse-battery", "password_confirmation": "correct-horse-battery"})
    response = client.get("/")

    assert response.status_code == 200
    assert b'id="theme-toggle"' in response.data
    assert b'aria-label="Switch to light theme"' in response.data
    assert b"theme-init.js" in response.data
    assert b"theme.js" in response.data


def test_theme_assets_define_dark_and_light_tokens(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{(tmp_path / 'theme-assets.db').as_posix()}",
            "SEED_SAMPLE_DATA": False,
        }
    )
    client = app.test_client()

    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/theme.js")
    init_script = client.get("/static/theme-init.js")

    assert stylesheet.status_code == 200
    assert b"#0b1020" in stylesheet.data
    assert b"#171b32" in stylesheet.data
    assert b"#8b5cf6" in stylesheet.data
    assert b'[data-theme="light"]' in stylesheet.data
    assert b"--field-bg: #ffffff" in stylesheet.data
    assert script.status_code == 200
    assert b"localStorage.setItem" in script.data
    assert init_script.status_code == 200
    assert b"localStorage.getItem" in init_script.data
