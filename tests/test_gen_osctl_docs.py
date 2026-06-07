import importlib.util, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen_osctl_docs", ROOT / "scripts" / "gen_osctl_docs.py")
gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
DOC = ROOT / "docs" / "generated" / "osctl-commands.md"

def test_generated_osctl_doc_in_sync():
    assert DOC.exists(), "run scripts/gen_osctl_docs.py"
    assert gen.generate() == DOC.read_text(), "osctl-commands.md is stale — regenerate and commit"

def test_generated_lists_known_commands():
    text = DOC.read_text()
    for cmd in ("resolve", "set-active", "schedule-status", "set-sched-intent"):
        assert f"`{cmd}`" in text, f"missing command {cmd}"
