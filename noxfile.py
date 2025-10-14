import nox


@nox.session
def install(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")


@nox.session
def serve(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")
    session.run("uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000")


@nox.session
def test(session: nox.Session) -> None:
    session.log("No tests defined for pos-lv2 backend yet.")

