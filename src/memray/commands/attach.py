import argparse
import contextlib
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import threading

import memray

from .live import LiveCommand
from .run import _get_free_port

GDB_SCRIPT = pathlib.Path(__file__).parent / "_attach.gdb"
RTLD_DEFAULT = memray._memray.RTLD_DEFAULT
RTLD_NOW = memray._memray.RTLD_NOW
PAYLOAD = """
import atexit

import memray


def deactivate_last_tracker():
    if hasattr(memray, "_last_tracker"):
        tracker = memray._last_tracker
        memray._last_tracker = None
        if tracker:
            tracker.__exit__(None, None, None)


if not hasattr(memray, "_last_tracker"):
    # This only needs to be registered the first time we attach.
    atexit.register(deactivate_last_tracker)

deactivate_last_tracker()

tracker = {tracker_call}
try:
    tracker.__enter__()
except:
    # Prevent the exception from keeping the tracker alive.
    # This way resources are cleaned up ASAP.
    del tracker
    raise

memray._last_tracker = tracker
"""

# TODO:
# - Allow the user to select between file vs socket (who picks the filename?).


def inject(debugger: str, pid: int, port: int) -> bool:
    """Executes a file in a running Python process."""
    injecter = pathlib.Path(memray.__file__).parent / "_inject.abi3.so"
    assert injecter.exists()

    gdb_cmd = [
        "gdb",
        "-batch",
        "-p",
        str(pid),
        "-nx",
        "-nh",
        "-nw",
        "-iex=set auto-solib-add off",
        f"-ex=set $rtld_now={RTLD_NOW}",
        f'-ex=set $libpath="{injecter}"',
        f"-ex=set $port={port}",
        f"-x={GDB_SCRIPT}",
    ]

    # When adding new breakpoints, also update _attach.gdb
    lldb_breakpoint_args = [
        "breakpoint",
        "set",
        "-b",
        "malloc",
        "-b",
        "calloc",
        "-b",
        "realloc",
        "-b",
        "free",
        "-b",
        "PyMem_Malloc",
        "-b",
        "PyMem_Calloc",
        "-b",
        "PyMem_Realloc",
        "-b",
        "PyMem_Free",
        "-C",
        "'breakpoint disable'",
        "-C",
        f"""'expr void *$dlopen = (void*)dlsym((void*){RTLD_DEFAULT}, "dlopen")'""",
        "-C",
        f"'expr ((void*(*)(const char*, int))$dlopen)($libpath, {RTLD_NOW})'",
        "-C",
        "'p (char*)dlerror()'",
        "-C",
        "'expr ((const char*(*)(int))&memray_spawn_client)($port)'",
    ]

    lldb_cmd = [
        "lldb",
        "--batch",
        "-p",
        str(pid),
        "--no-lldbinit",
        "--source-quietly",
        "-o",
        "p ((void*(*)(size_t))PyMem_Malloc)",
        "-o",
        "p ((void*(*)(size_t, size_t))PyMem_Calloc)",
        "-o",
        "p ((void*(*)(void *, size_t))PyMem_Realloc)",
        "-o",
        "p ((void(*)(void*))PyMem_Free)",
        "-o",
        f'expr char $libpath[]="{injecter}"',
        "-o",
        f"expr int $port={port}",
        "-o",
        " ".join(lldb_breakpoint_args),
        "-o",
        "continue",
    ]

    cmd = gdb_cmd if debugger == "gdb" else lldb_cmd
    # print(shlex.join(cmd))
    p = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = p.communicate()[0]
    # print(f"debugger return code: {p.returncode}")
    # print(f"debugger output:\n{output}")
    return p.returncode == 0 and "error:" not in output


def recvall(sock: socket.socket) -> str:
    return b"".join(iter(lambda: sock.recv(4096), b"")).decode("utf-8")


class ErrorReaderThread(threading.Thread):
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        super().__init__()

    def run(self) -> None:
        try:
            err = recvall(self._sock)
        except OSError as e:
            err = f"Unexpected exception: {e!r}"

        if not err:
            self.error = None
            return

        self.error = err
        os.kill(os.getpid(), signal.SIGINT)


class AttachCommand:
    """Remotely monitor allocations in a text-based interface"""

    def prepare_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            help="Create a capture file instead of starting a live tracking session",
        )
        parser.add_argument(
            "-f",
            "--force",
            help="If the output file already exists, overwrite it",
            action="store_true",
            default=False,
        )

        parser.add_argument(
            "--native",
            help="Track native (C/C++) stack frames as well",
            action="store_true",
            dest="native",
            default=False,
        )
        parser.add_argument(
            "--follow-fork",
            action="store_true",
            help="Record allocations in child processes forked from the tracked script",
            default=False,
        )
        parser.add_argument(
            "--trace-python-allocators",
            action="store_true",
            help="Record allocations made by the Pymalloc allocator",
            default=False,
        )
        compression = parser.add_mutually_exclusive_group()
        compression.add_argument(
            "--compress-on-exit",
            help="Compress the resulting file using lz4 after tracking completes",
            default=True,
            action="store_true",
        )
        compression.add_argument(
            "--no-compress",
            help="Do not compress the resulting file using lz4",
            default=False,
            action="store_true",
        )

        parser.add_argument(
            "--method",
            help="Method to use for injecting code into the process to track",
            type=str,
            default="auto",
            choices=["auto", "gdb", "lldb"],
        )
        parser.add_argument(
            "pid",
            help="Remote pid to attach to",
            type=int,
        )

    def run(self, args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
        if args.method == "auto":
            if shutil.which("lldb"):
                args.method = "lldb"
            elif shutil.which("gdb"):
                args.method = "gdb"
            else:
                print("Cannot find an lldb or gdb executable.")
                return
        elif not shutil.which(args.method):
            print(f"Cannot find a {args.method} executable.")
            return

        destination: memray.Destination
        if args.output:
            live_port = None
            destination = memray.FileDestination(
                path=os.path.abspath(args.output),
                overwrite=args.force,
                compress_on_exit=not args.no_compress,
            )
        else:
            live_port = _get_free_port()
            destination = memray.SocketDestination(server_port=live_port)

        tracker_call = (
            f"memray.Tracker(destination=memray.{destination!r},"
            f" native_traces={args.native},"
            f" follow_fork={args.follow_fork},"
            f" trace_python_allocators={args.trace_python_allocators})"
        )

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with contextlib.closing(server):
            server.bind(("localhost", 0))
            server.listen(1)
            sidechannel_port = server.getsockname()[1]

            if not inject(args.method, args.pid, sidechannel_port):
                print("Failed to attach to remote process.")
                return

            client = server.accept()[0]

        client.sendall(PAYLOAD.format(tracker_call=tracker_call).encode("utf-8"))
        client.shutdown(socket.SHUT_WR)

        if not live_port:
            err = recvall(client)
            if err:
                print(f"Failed to start tracking in remote process: {err}")
            return

        # If an error prevents the tracked process from binding a server to
        # live_port, the TUI will hang forever trying to connect. Handle this
        # by spawning a background thread that watches for an error report over
        # the side channel and raises a SIGINT to interrupt the TUI if it sees
        # one. This can race, though: in some cases the TUI will also see an
        # error (if no header is sent over the socket), and the background
        # thread may raise a SIGINT that we see only after the live TUI has
        # already exited. If so we must ignore the extra KeyboardInterrupt.
        error_reader = ErrorReaderThread(client)
        error_reader.start()
        live = LiveCommand()

        with contextlib.suppress(KeyboardInterrupt):
            try:
                try:
                    live.start_live_interface(live_port)
                finally:
                    # Note: may get a spurious KeyboardInterrupt!
                    error_reader.join()
            except (Exception, KeyboardInterrupt):
                remote_err = error_reader.error
                if not remote_err:
                    raise  # Propagate the exception

                print(f"Failed to start tracking in remote process: {remote_err}")
                return  # Swallow the exception
