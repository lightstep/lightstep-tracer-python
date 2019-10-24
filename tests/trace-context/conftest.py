from os import mkdir, environ
from os.path import abspath, dirname, join
from subprocess import Popen
from shlex import split
from time import sleep

from git import Repo
from git.exc import InvalidGitRepositoryError

_TEST_SERVICE = None


def pytest_sessionstart(session):
    global _TEST_SERVICE
    trace_context_path = join(dirname(abspath(__file__)), "trace-context")

    try:
        mkdir(trace_context_path)

    except FileExistsError:
        pass

    try:
        trace_context_repo = Repo(trace_context_path)

    except InvalidGitRepositoryError:
        trace_context_repo = Repo.clone_from(
            "git@github.com:w3c/trace-context.git",
            trace_context_path
        )

    trace_context_repo.heads.master.checkout()
    trace_context_repo.head.reset(
        "98f210efd89c63593dce90e2bae0a1bdcb986f51"
    )

    environ["SERVICE_ENDPOINT"] = "http://127.0.0.1:5000/test"

    _TEST_SERVICE = Popen(
        split(
            "python3 {}".format(
                join(
                    dirname(abspath(__file__)),
                    "trace_context_test_service.py"
                )
            )
        )
    )
    # This seems to be necessary, if not the first few test cases will fail
    # since they won't find the test service running.
    sleep(1)


def pytest_sessionfinish(session, exitstatus):
    _TEST_SERVICE.terminate()
