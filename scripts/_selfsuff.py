import pathlib

p = pathlib.Path("scripts/workshop_notebooks.py")
s = p.read_text()

# --- cell 7: the curl cell depends on URL from an earlier cell -------------
old7 = '''        code("""
import shutil
import subprocess

if shutil.which("curl"):'''
new7 = '''        code("""
import shutil
import subprocess

# Defined here as well as earlier, so this cell runs on its own. Every cell in these
# notebooks is runnable in isolation -- people jump around, and "Run All" is not the
# only way anyone ever uses a notebook.
URL = S.sst_csv(point=True)

if shutil.which("curl"):'''
assert old7 in s, "cell 7 anchor"
s = s.replace(old7, new7, 1)

# --- the parse cell depends on `raw` from 8 cells earlier -------------------
old18 = '''        code("""
import io

df = pd.read_csv(io.StringIO(raw.text), skiprows=[1])
df["time"] = pd.to_datetime(df["time"].str.replace("Z", "", regex=False))'''
new18 = '''        code("""
import io

# Re-fetched rather than reusing `raw` from earlier: a variable defined eight cells up
# is a variable that breaks the moment someone runs this cell on its own. Two lines to
# be independent is cheaper than debugging that later.
raw = http.get(S.sst_csv(point=True))

df = pd.read_csv(io.StringIO(raw.text), skiprows=[1])
df["time"] = pd.to_datetime(df["time"].str.replace("Z", "", regex=False))'''
assert old18 in s, "parse cell anchor"
s = s.replace(old18, new18, 1)

# --- the assertion cell depends on both raw and df -------------------------
old34 = '''        code("""
# Assert the response is what this notebook said it would be.
_fetch.expect("response bytes", len(raw.content), 1324)
_fetch.expect("rows", len(df), 30)'''
new34 = '''        code("""
# Assert the response is what this notebook said it would be.
# Built here rather than inherited, so the last cell of the notebook can be run alone
# and still check something real.
raw = http.get(S.sst_csv(point=True))
df = pd.read_csv(io.StringIO(raw.text), skiprows=[1])

_fetch.expect("response bytes", len(raw.content), 1324)
_fetch.expect("rows", len(df), 30)'''
assert old34 in s, "assert cell anchor"
s = s.replace(old34, new34, 1)

p.write_text(s)
print("cells 7, 18 and 34 made self-sufficient")
