import signal
import os
import re
from enum import Enum, auto
import errno
import select
import subprocess
import time
import os
import pty
from typing import Union, Optional, List
import datetime


class REPLErrors(Enum):
    """Errors the REPL session might return."""

    TIMEOUT = auto()
    SIZELIMIT = auto()


def timed_read(
    fds: List[int],
    size_limit: Optional[int],
    timeout: float,
    step_timeout: float,
    step_read_size: int,
) -> Union[bytes, REPLErrors]:
    """
    Reads from the file descriptors (fds) that are ready within the given time
    limit and size constraints. It will wait for a file pointer to be ready to
    be read from and then continue reading until the there is no more or the
    timelimit or size limit is exceeded.

    A problem with this approach is select is timed out at 0.2 so if the steps
    in the computation takes too much time then the output will be broken. I
    think this is unlikely to happen for users.

    size_limit is measured in bytes and timeout is measured in seconds.
    """
    start_time = time.time()
    result = b""
    is_initial_read = True

    while (time.time() - start_time) < timeout:
        ready_to_read, _, _ = select.select(fds, [], [], step_timeout)
        if len(ready_to_read) == 0 and is_initial_read:
            continue
        try:
            is_initial_read = False

            if len(ready_to_read) == 0:
                return result

            sub_result = os.read(ready_to_read.pop(), step_read_size)
            result += sub_result

            if size_limit is not None and len(result) >= size_limit:
                return REPLErrors.SIZELIMIT
            elif len(sub_result) == 0:
                break

        except OSError as e:
            if e.errno == errno.EAGAIN:
                continue
            else:
                raise
    else:
        return REPLErrors.TIMEOUT

    return result


class FutharkREPL:
    """
    Class that handles a Futhark REPL process that can be interacted with.
    """

    def __init__(
        self,
        response_size_limit: Optional[int],
        compute_time_limit: datetime.timedelta,
        step_timeout: datetime.timedelta,
        step_read_size: int,
    ):
        self.ansi_escape = re.compile(
            r"""
            \x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])
        """,
            re.VERBOSE,
        )

        # Used to simulate a shell.
        self.stdin_master, self.stdin_slave = pty.openpty()
        self.stdout_master, self.stdout_slave = pty.openpty()
        self.stderr_master, self.stderr_slave = pty.openpty()
        self.response_size_limit = response_size_limit
        self.compute_time_limit = compute_time_limit.seconds
        self.step_timeout = step_timeout.total_seconds()
        self.step_read_size = step_read_size

        self.stdin = open(self.stdin_master, "w")
        self.fds = [self.stdout_master, self.stderr_master]

        self.process = subprocess.Popen(
            ["futhark", "repl"],
            preexec_fn=os.setsid,
            stdin=self.stdin_slave,
            stdout=self.stdout_slave,
            stderr=self.stderr_slave,
            text=True,
        )
        time.sleep(0.5)
        self.generator = self.create_generator()
        self.banner, self.init_lastline = next(self.generator).rsplit("\n", 1)
        self.pause()

    def read(self) -> Union[str, REPLErrors]:
        """
        Reads from the process' stdout or stderr of if an error happens then
        the session is killed.
        """
        out = timed_read(
            self.fds,
            self.response_size_limit,
            self.compute_time_limit,
            self.step_timeout,
            self.step_read_size,
        )

        if isinstance(out, Enum):
            self.kill()
            return out

        return self.ansi_escape.sub("", out.decode())

    def create_generator(self):
        """
        A generator that can be used to communicate with the REPL process.
        """
        yield self.read()
        while True:
            inp = yield
            self.stdin.write(f"{inp}\n")
            yield self.read()

    def run(self, code: str) -> Union[tuple[str, str], Enum]:
        """
        Method for communicating with the active REPL process.
        """
        next(self.generator)
        out = self.generator.send(code)

        if isinstance(out, Enum):
            return out

        result_tuple = out.rsplit("\n", 1)
        if len(result_tuple) == 1:
            (out,) = result_tuple
            return "", out

        result, lastline = result_tuple
        return result.strip(), lastline.strip()

    def kill(self):
        """Kills the REPL process."""
        self.process.kill()

    def pause(self):
        """Pauses the process."""
        try:
            os.kill(self.process.pid, signal.SIGSTOP)
        except ProcessLookupError:
            pass

    def resume(self):
        """Resumes the process."""
        try:
            os.kill(self.process.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass


class Session:
    """A session managed by a Sessions"""

    def __init__(
        self,
        identifier: str,
        response_size_limit: Optional[int],
        compute_time_limit: datetime.timedelta,
        step_timeout: datetime.timedelta,
        step_read_size: int,
    ):
        self.active = False
        self.identifier = identifier
        self.process = FutharkREPL(
            response_size_limit=response_size_limit,
            compute_time_limit=compute_time_limit,
            step_timeout=step_timeout,
            step_read_size=step_read_size,
        )
        self.banner = self.process.banner
        self.init_lastline = self.process.init_lastline

    def read_eval_print(self, code: str) -> Union[tuple[str, str], Enum]:
        """Reads ssome code and evaluates it in the repl"""
        self.active = True
        self.process.resume()
        out = self.process.run(code)
        self.process.pause()
        self.active = False

        if isinstance(out, Enum):
            return out

        result, lastline = out
        return result.strip(), lastline.strip() + " "

    def kill(self):
        """Ends the session."""
        self.process.kill()

    def is_active(self) -> bool:
        """This is used in sessions to check if computations can be done."""
        return self.active
