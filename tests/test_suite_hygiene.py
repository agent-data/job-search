"""Guards on the test suite itself rather than on anything the suite tests."""
import ast
import collections
import pathlib

TESTS = pathlib.Path(__file__).resolve().parent

# pytest's own defaults, so this sees every file and every function pytest would collect. A guard
# narrower than the collector has its blind spot exactly where no file exists yet to reveal it:
# nothing under tests/ matches `*_test.py` today, and nothing defines `testFoo`.
MODULE_GLOBS = ("test_*.py", "*_test.py")   # python_files
TEST_PREFIX = "test"                        # python_functions = test*


def _scopes(node, where):
    """Every namespace under `node` that can hold collected test functions, each with a label.

    Class bodies are walked at any depth rather than only at module level, because two methods of
    one class shadow each other wherever that class is written.
    """
    yield where, node.body
    for child in node.body:
        if isinstance(child, ast.ClassDef):
            for scope in _scopes(child, "%s::%s" % (where, child.name)):
                yield scope


def _test_names(body):
    """The test functions defined directly in one scope, in source order."""
    return [node.name for node in body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith(TEST_PREFIX)]


def test_no_scope_defines_one_test_name_twice():
    """A second `def test_x` in one scope replaces the first, and pytest reports nothing at all:
    the earlier case stops running while the suite stays green.

    It happened here. A judgment test took the name of a queue test in the same module and removed
    its three parametrized cases. Measured afterwards: shadowing a parametrized test drops the
    collected count, which is how that one was caught, but shadowing a plain one collects and passes
    the same number of tests either way, so nothing but this guard sees it.

    Names are read with `ast` per scope rather than by grep, because a method on a test class and a
    module-level function of the same name do not shadow each other, and a `def` nested inside
    another function is not collected at all.
    """
    modules = sorted({path for glob in MODULE_GLOBS for path in TESTS.glob(glob)})
    assert modules, "no test modules found under %s — this guard would pass on an empty set" % TESTS
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for where, body in _scopes(tree, module.name):
            counts = collections.Counter(_test_names(body))
            repeated = sorted(name for name, n in counts.items() if n > 1)
            assert repeated == [], "%s defines these test names more than once: %s" % (
                where, repeated)
