import nox

@nox.session
def tests(session: nox.Session) -> None:
    session.install("pytest", "coverage")
    session.install(".")
    session.run("make", "SIM=icarus", external=True)
