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
from typing import Union
import datetime


class REPLErrors(Enum):
    TIMEOUT = auto()
    SIZELIMIT = auto()


def timed_read(fds, size_limit, timeout):
    start_time = time.time()
    result = b""
    is_initial_read = True
    while (time.time() - start_time) < timeout:
        ready_to_read, _, _ = select.select(fds, [], [], 0.1)
        if len(ready_to_read) == 0 and is_initial_read:
            continue
        try:
            is_initial_read = False

            if len(ready_to_read) == 0:
                return result

            sub_result = os.read(ready_to_read.pop(), 1024)
            result += sub_result

            if len(result) >= size_limit:
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
    def __init__(
        self, response_size_limit: int, compute_time_limit: datetime.timedelta
    ):
        self.ansi_escape = re.compile(
            r"""
            \x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])
        """,
            re.VERBOSE,
        )

        self.stdin_master, self.stdin_slave = pty.openpty()
        self.stdout_master, self.stdout_slave = pty.openpty()
        self.stderr_master, self.stderr_slave = pty.openpty()
        self.response_size_limit = response_size_limit
        self.compute_time_limit = compute_time_limit.seconds

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
        out = timed_read(self.fds, self.response_size_limit, self.compute_time_limit)

        if isinstance(out, Enum):
            self.kill()
            return out

        return self.ansi_escape.sub("", out.decode())

    def create_generator(self):
        yield self.read()
        while True:
            inp = yield
            self.stdin.write(f"{inp}\n")
            yield self.read()

    def run(self, code) -> Union[tuple[str, str], REPLErrors]:
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
        self.process.kill()

    def pause(self):
        try:
            os.kill(self.process.pid, signal.SIGSTOP)
        except ProcessLookupError:
            pass

    def resume(self):
        try:
            os.kill(self.process.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass


class Session:
    def __init__(
        self,
        identifier: str,
        response_size_limit: int,
        compute_time_limit: datetime.timedelta,
    ):
        self.active = False
        self.identifier = identifier
        self.process = FutharkREPL(
            response_size_limit=response_size_limit,
            compute_time_limit=compute_time_limit,
        )
        self.banner = self.process.banner
        self.init_lastline = self.process.init_lastline

    def read_eval_print(self, code: str) -> Union[tuple[str, str], REPLErrors]:
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
        self.process.kill()

    def is_active(self) -> bool:
        return self.active
