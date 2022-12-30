import mmap
import os
import tempfile

from memray import AllocatorType
from memray import FileReader
from memray._test import MemoryAllocator
from memray import Tracker

from .benchmarking.cases import async_tree_base
from .benchmarking.cases import fannkuch_base
from .benchmarking.cases import mdp_base
from .benchmarking.cases import pprint_format_base
from .benchmarking.cases import raytrace_base
from .benchmarking.cases import docutils_html_base

MAX_ITERS = 100000


class TracebackBenchmarks:
    def setup(self):
        self.tempfile = tempfile.NamedTemporaryFile()
        allocator = MemoryAllocator()

        def fac(n):
            if n == 1:
                allocator.valloc(1234)
                allocator.free()
                return 1
            return n * fac(n - 1)

        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            fac(300)

        (self.record,) = [
            record
            for record in FileReader(self.tempfile.name).get_allocation_records()
            if record.allocator == AllocatorType.VALLOC
        ]

    def time_get_stack_trace(self):
        self.record.stack_trace()


class AllocatorBenchmarks:
    def setup(self):
        self.tempfile = tempfile.NamedTemporaryFile()
        self.allocator = MemoryAllocator()

    def time_malloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.malloc(1234):
                    self.allocator.free()

    def time_posix_memalign(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.posix_memalign(1234):
                    self.allocator.free()

    def time_posix_realloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.posix_memalign(1234):
                    self.allocator.free()

    def time_calloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.calloc(1234):
                    self.allocator.free()

    def time_pvalloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.pvalloc(1234):
                    self.allocator.free()

    def time_valloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.valloc(1234):
                    self.allocator.free()

    def time_realloc(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                if self.allocator.realloc(1234):
                    self.allocator.free()

    def time_mmap(self):
        os.unlink(self.tempfile.name)
        with Tracker(self.tempfile.name):
            for _ in range(MAX_ITERS):
                with mmap.mmap(-1, length=2048, access=mmap.ACCESS_WRITE) as mmap_obj:
                    mmap_obj[0:100] = b"a" * 100


class ParserBenchmarks:
    def setup(self):
        self.tempfile = tempfile.NamedTemporaryFile()
        self.allocator = MemoryAllocator()
        os.unlink(self.tempfile.name)
        self.tracker = Tracker(self.tempfile.name)
        with self.tracker:
            for _ in range(MAX_ITERS):
                self.allocator.valloc(1234)
                self.allocator.free()

    def time_end_to_end_parsing(self):
        list(FileReader(self.tempfile.name).get_allocation_records())


def recursive(n, chunk_size):
    """Mimics generally-increasing but spiky usage"""
    if not n:
        return

    allocator = MemoryAllocator()
    allocator.valloc(n * chunk_size)

    # Don't keep allocated memory when recursing, ~50% of the calls.
    if n % 2:
        allocator.free()
        recursive(n - 1, chunk_size)
    else:
        recursive(n - 1, chunk_size)
        allocator.free()


class HighWatermarkBenchmarks:
    def setup(self):
        self.tempfile = tempfile.NamedTemporaryFile()
        os.unlink(self.tempfile.name)
        self.tracker = Tracker(self.tempfile.name)

        with self.tracker:
            recursive(700, 99)

    def time_high_watermark(self):
        list(
            FileReader(self.tempfile.name).get_high_watermark_allocation_records(
                merge_threads=False
            )
        )


class MacroBenchmarksBase:
    def setup(self):
        self.tracker = Tracker("/dev/null")

    def time_async_tree_cpu(self):
        with self.tracker:
            async_tree_base.run_benchmark("none")

    def time_async_tree_io(self):
        with self.tracker:
            async_tree_base.run_benchmark("io")

    def time_async_tree_memoization(self):
        with self.tracker:
            async_tree_base.run_benchmark("memoization")

    def time_async_tree_cpu_io_mixed(self):
        with self.tracker:
            async_tree_base.run_benchmark("cpu_io_mixed")

    def time_fannkuch(self):
        with self.tracker:
            fannkuch_base.run_benchmark()

    def time_mdp(self):
        with self.tracker:
            mdp_base.run_benchmark()

    def time_pprint_format(self):
        with self.tracker:
            pprint_format_base.run_benchmark()

    def time_raytrace_base(self):
        with self.tracker:
            raytrace_base.run_benchmark()


class MacroBenchmarksPythonAllocators:
    def setup(self):
        self.tracker = Tracker("/dev/null", trace_python_allocators=True)

    def time_async_tree_cpu(self):
        with self.tracker:
            async_tree_base.run_benchmark("none")

    def time_async_tree_io(self):
        with self.tracker:
            async_tree_base.run_benchmark("io")

    def time_async_tree_memoization(self):
        with self.tracker:
            async_tree_base.run_benchmark("memoization")

    def time_async_tree_cpu_io_mixed(self):
        with self.tracker:
            async_tree_base.run_benchmark("cpu_io_mixed")

    def time_fannkuch(self):
        with self.tracker:
            fannkuch_base.run_benchmark()

    def time_mdp(self):
        with self.tracker:
            mdp_base.run_benchmark()

    def time_pprint_format(self):
        with self.tracker:
            pprint_format_base.run_benchmark()

    def time_raytrace(self):
        with self.tracker:
            raytrace_base.run_benchmark()

    def time_docutils_html(self):
        with self.tracker:
            docutils_html_base.run_benchmark()


class MacroBenchmarksPythonNative:
    def setup(self):
        self.tracker = Tracker("/dev/null", native_traces=True)

    def time_async_tree_cpu(self):
        with self.tracker:
            async_tree_base.run_benchmark("none")

    def time_async_tree_io(self):
        with self.tracker:
            async_tree_base.run_benchmark("io")

    def time_async_tree_memoization(self):
        with self.tracker:
            async_tree_base.run_benchmark("memoization")

    def time_async_tree_cpu_io_mixed(self):
        with self.tracker:
            async_tree_base.run_benchmark("cpu_io_mixed")

    def time_fannkuch(self):
        with self.tracker:
            fannkuch_base.run_benchmark()

    def time_mdp(self):
        with self.tracker:
            mdp_base.run_benchmark()

    def time_pprint_format(self):
        with self.tracker:
            pprint_format_base.run_benchmark()

    def time_raytrace(self):
        with self.tracker:
            raytrace_base.run_benchmark()

    def time_docutils_html(self):
        with self.tracker:
            docutils_html_base.run_benchmark()


class MacroBenchmarksPythonAll:
    def setup(self):
        self.tracker = Tracker(
            "/dev/null", native_traces=True, trace_python_allocators=True
        )

    def time_async_tree_cpu(self):
        with self.tracker:
            async_tree_base.run_benchmark("none")

    def time_async_tree_io(self):
        with self.tracker:
            async_tree_base.run_benchmark("io")

    def time_async_tree_memoization(self):
        with self.tracker:
            async_tree_base.run_benchmark("memoization")

    def time_async_tree_cpu_io_mixed(self):
        with self.tracker:
            async_tree_base.run_benchmark("cpu_io_mixed")

    def time_fannkuch(self):
        with self.tracker:
            fannkuch_base.run_benchmark()

    def time_mdp(self):
        with self.tracker:
            mdp_base.run_benchmark()

    def time_pprint_format(self):
        with self.tracker:
            pprint_format_base.run_benchmark()

    def time_raytrace(self):
        with self.tracker:
            raytrace_base.run_benchmark()

    def time_docutils_html(self):
        with self.tracker:
            docutils_html_base.run_benchmark()
