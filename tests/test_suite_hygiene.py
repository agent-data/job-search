"""Guards on the test suite itself rather than on anything the suite tests."""
import ast
import collections
import pathlib

TESTS = pathlib.Path(__file__).resolve().parent


def _test_names(body):
    """The test functions defined directly in one scope, in source order."""
    return [node.name for node in body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")]


def test_no_module_defines_one_test_name_twice():
    """A second `def test_x` in a module replaces the first, and pytest reports nothing at all: the
    earlier case stops running and the only signal is a collected count one lower than expected.

    It happened here. A judgment test took the name of a queue test in the same module and removed
    its three parametrized cases; the suite stayed green and the count was caught by arithmetic.
    Tasks 5 through 16 all add cases to `test_mechanics_scripts.py`, so the class fires again unless
    something runs on every commit.

    Names are read with `ast` per scope rather than by grep, because a method on a test class and a
    module-level function of the same name do not shadow each other, and a `def` nested inside
    another function is not collected at all.
    """
    for module in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        scopes = [(module.name, tree.body)]
        scopes += [("%s::%s" % (module.name, node.name), node.body)
                   for node in tree.body if isinstance(node, ast.ClassDef)]
        for where, body in scopes:
            counts = collections.Counter(_test_names(body))
            repeated = sorted(name for name, n in counts.items() if n > 1)
            assert repeated == [], "%s defines these test names more than once: %s" % (
                where, repeated)
