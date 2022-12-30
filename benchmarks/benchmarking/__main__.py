import pathlib
import subprocess
import dataclasses
import sys
import tempfile

import json

from typing import List

from .plot import plot_diff

CASES_DIR = pathlib.Path(__file__).parent / "cases"
RESULTS_DIR = pathlib.Path(__file__).parent / "results"


@dataclasses.dataclass
class Case:
    name: str
    file_name: str
    arguments: List[str] = dataclasses.field(default_factory=list)

    def run(self):
        template_file = CASES_DIR / f"{self.file_name}_memray.py"
        if not template_file.exists():
            raise ValueError(f"Case {self.name} does not exist.")

        with tempfile.TemporaryDirectory() as tmpdirname:
            case_file = pathlib.Path(tmpdirname) / f"{self.file_name}.py"
            code = template_file.read_text().replace(
                "MEMRAY_TRACKER_CODE_HERE", "contextlib.nullcontext()"
            )
            case_file.write_text(code)

            results_file = RESULTS_DIR / f"{self.name}.json"
            print(f"Running {self.name} with arguments {self.arguments}")
            subprocess.run(
                [sys.executable, case_file, "-o", results_file] + self.arguments,
                check=True,
            )

        with tempfile.TemporaryDirectory() as tmpdirname:
            case_file = pathlib.Path(tmpdirname) / f"{self.file_name}.py"
            code = template_file.read_text().replace(
                "MEMRAY_TRACKER_CODE_HERE", "memray.Tracker('/dev/null')"
            )
            case_file.write_text(code)

            results_file = RESULTS_DIR / f"{self.name}_memray.json"
            print(f"Running {self.name} with arguments {self.arguments} - memray base")
            subprocess.run(
                [sys.executable, case_file, "-o", results_file] + self.arguments,
                check=True,
            )

        with tempfile.TemporaryDirectory() as tmpdirname:
            case_file = pathlib.Path(tmpdirname) / f"{self.file_name}.py"
            code = template_file.read_text().replace(
                "MEMRAY_TRACKER_CODE_HERE",
                "memray.Tracker('/dev/null', trace_python_allocators=True)",
            )
            case_file.write_text(code)

            results_file = RESULTS_DIR / f"{self.name}_memray_python_allocators.json"
            print(
                f"Running {self.name} with arguments {self.arguments} - memray python allocators"
            )
            subprocess.run(
                [sys.executable, case_file, "-o", results_file] + self.arguments,
                check=True,
            )

        with tempfile.TemporaryDirectory() as tmpdirname:
            case_file = pathlib.Path(tmpdirname) / f"{self.file_name}.py"
            code = template_file.read_text().replace(
                "MEMRAY_TRACKER_CODE_HERE",
                "memray.Tracker('/dev/null', native_traces=True)",
            )
            case_file.write_text(code)

            results_file = RESULTS_DIR / f"{self.name}_memray_python_native.json"
            print(
                f"Running {self.name} with arguments {self.arguments} - memray python native"
            )
            subprocess.run(
                [sys.executable, case_file, "-o", results_file] + self.arguments,
                check=True,
            )

        with tempfile.TemporaryDirectory() as tmpdirname:
            case_file = pathlib.Path(tmpdirname) / f"{self.file_name}.py"
            code = template_file.read_text().replace(
                "MEMRAY_TRACKER_CODE_HERE",
                "memray.Tracker('/dev/null', trace_python_allocators=True, native_traces=True)",
            )
            case_file.write_text(code)

            results_file = RESULTS_DIR / f"{self.name}_memray_python_all.json"
            print(
                f"Running {self.name} with arguments {self.arguments} - memray python all"
            )
            subprocess.run(
                [sys.executable, case_file, "-o", results_file] + self.arguments,
                check=True,
            )


CASES = [
    Case("docutils", "docutils_html", []),
    Case("raytrace", "raytrace", []),
    Case("fannkuch", "fannkuch", []),
    Case("pprint", "pprint_format", []),
    Case("mdp", "mdp", []),
    Case("async_tree", "async_tree", ["none"]),
    Case("async_tree_io", "async_tree", ["io"]),
    Case("async_tree_mem", "async_tree", ["memoization"]),
    Case("async_tree_cpu_io", "async_tree", ["cpu_io_mixed"]),
]


@dataclasses.dataclass
class BenchmarkResult:
    name: str
    data: List


def gather_benchmarks(cases):
    results = []
    names = {"", "Python allocators", "Native", "Python allocators + Native"}
    extensions = {
        "",
        "_memray_python_allocators",
        "_memray_python_native",
        "_memray_python_all",
    }
    for name, extension in zip(names, extensions):
        type_results = []
        for case in cases:
            memray_results_file = RESULTS_DIR / f"{case.name}{extension}.json"
            data = json.loads(memray_results_file.read_text())
            type_results.append(data)
        results.append(BenchmarkResult(name=name, data=type_results))
    return results


if __name__ == "__main__":
    if RESULTS_DIR.exists():
        for file in RESULTS_DIR.iterdir():
            file.unlink()
        RESULTS_DIR.rmdir()

    RESULTS_DIR.mkdir(exist_ok=True)

    for case in CASES:
        case.run()

    base_results, *memray_results = gather_benchmarks(CASES)
    plot_diff(memray_results, base_results, "plot.png", "Results")
