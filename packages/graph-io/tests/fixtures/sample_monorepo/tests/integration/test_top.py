from mypkg.foo import foo
from webutil import serve


def test_top() -> None:
    assert foo() == 1
    assert serve() == "ok"
