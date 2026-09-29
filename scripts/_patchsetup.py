import pathlib

p = pathlib.Path("src/ocean_sim/workshop_setup.py")
s = p.read_text()

# 1. Resolve the container through compose rather than by a hardcoded name.
old = '''    # Confirm we can actually query it, not merely that the container is up.
    r = run(
        ["docker", "exec", "ocean-sim-db", "psql", "-U", "postgres", "-d", "ocean_sim",
         "-tAc", "select 1"],
        check=False, quiet=True, timeout=60,
    )
    if r.returncode != 0:
        die("container is up but postgres is not accepting connections yet")
    ok("accepting connections")'''
new = '''    # Confirm we can actually query it, not merely that the container is up.
    # `docker compose exec` resolves the container name, so nothing here hardcodes it.
    r = run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "postgres",
         "-d", "ocean_sim", "-tAc", "select 1"],
        check=False, quiet=True, timeout=60,
    )
    if r.returncode != 0:
        die("container is up but postgres is not accepting connections yet")
    ok("accepting connections")'''
assert old in s, "exec anchor not found"
s = s.replace(old, new, 1)

# 2. Handle the two failure modes compose actually produces.
old2 = '''    if r.returncode != 0:
        if "port is already allocated" in (r.stderr + r.stdout):
            die(
                f"host port {DB_PORT} is already in use",
                "You probably have a local PostgreSQL. Either stop it, or pick another:\\n"
                f"    uv run workshop-setup --port 5433\\n"
                "The port is read from OCEAN_SIM_PORT by the database and by every\\n"
                "script that connects, so this stays consistent.",
            )
        die(f"docker compose up failed\\n{(r.stderr or r.stdout)[-800:]}")'''
new2 = '''    if r.returncode != 0:
        out = r.stderr + r.stdout
        if "port is already allocated" in out:
            die(
                f"host port {DB_PORT} is already in use",
                "You probably have a local PostgreSQL. Either stop it, or pick another:\\n"
                f"    uv run workshop-setup --port 5433\\n"
                "The port is read from OCEAN_SIM_PORT by the database and by every\\n"
                "script that connects, so this stays consistent.",
            )
        if "already in use by container" in out or "Conflict" in out:
            die(
                "another checkout of this repo is already running its database",
                "Two checkouts share the compose project name and its volume. Give this\\n"
                "one its own project so the two stay independent:\\n"
                "    OCEAN_SIM_PROJECT=$(basename $PWD) uv run workshop-setup --port 5433\\n"
                "or tear the other one down:\\n"
                "    docker compose -p ocean-sim down",
            )
        die(f"docker compose up failed\\n{out[-800:]}")'''
assert old2 in s, "error anchor not found"
s = s.replace(old2, new2, 1)

# 3. Let the project name be overridden, and default it per-checkout.
old3 = '''    env = {**os.environ, "OCEAN_SIM_PORT": str(DB_PORT)}'''
new3 = '''    env = {
        **os.environ,
        "OCEAN_SIM_PORT": str(DB_PORT),
        # Default the compose project to this checkout's directory name, so two
        # checkouts on one machine get separate containers and separate volumes. Falls
        # back to the compose file's own default if the directory name is unusable.
        "OCEAN_SIM_PROJECT": os.environ.get("OCEAN_SIM_PROJECT", PROJECT),
    }'''
assert old3 in s, "env anchor not found"
s = s.replace(old3, new3, 1)

old4 = '''DB_PORT = int(os.environ.get("OCEAN_SIM_PORT", "5432"))'''
new4 = '''DB_PORT = int(os.environ.get("OCEAN_SIM_PORT", "5432"))

# Compose project name: this checkout's directory, so two clones do not collide.
PROJECT = os.environ.get("OCEAN_SIM_PROJECT") or re.sub(
    r"[^a-z0-9_-]", "-", ROOT.name.lower()
).strip("-") or "ocean-sim"'''
assert old4 in s, "port anchor not found"
s = s.replace(old4, new4, 1)

s = s.replace("import argparse\nimport os", "import argparse\nimport os\nimport re", 1)

p.write_text(s)
print("patched workshop_setup")
