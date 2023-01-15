import datetime
import html
import linecache
import sys
from itertools import tee
from itertools import zip_longest
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import Tuple
from typing import TypeVar


from flask import Flask
from flask import jsonify
from flask import request

from memray import AllocationRecord
from memray import FileReader
from memray import MemorySnapshot
from memray import Metadata
from memray.reporters.frame_tools import StackFrame
from memray.reporters.frame_tools import is_cpython_internal
from memray.reporters.frame_tools import is_frame_from_import_system
from memray.reporters.frame_tools import is_frame_interesting
from memray.reporters.templates import render_report

MAX_STACKS = int(sys.getrecursionlimit() // 2.5)

T = TypeVar("T")


def pairwise_longest(iterable: Iterator[T]) -> Iterable[Tuple[T, T]]:
    a, b = tee(iterable)
    next(b, None)
    return zip_longest(a, b)


def with_converted_children_dict(node: Dict[str, Any]) -> Dict[str, Any]:
    stack = [node]
    while stack:
        the_node = stack.pop()
        the_node["children"] = [child for child in the_node["children"].values()]
        stack.extend(the_node["children"])
    return node


def create_framegraph_node_from_stack_frame(
    stack_frame: StackFrame, **kwargs: Any
) -> Dict[str, Any]:
    function, filename, lineno = stack_frame

    name = (
        # Use the source file line.
        linecache.getline(filename, lineno)
        # Or just describe where it is from
        or f"{function} at {filename}:{lineno}"
    )
    return {
        "name": name,
        "location": [html.escape(str(part)) for part in stack_frame],
        "value": 0,
        "children": {},
        "n_allocations": 0,
        "thread_id": 0,
        "interesting": (
            is_frame_interesting(stack_frame)
            and not is_frame_from_import_system(stack_frame)
        ),
        **kwargs,
    }


class FlameGraphReporter:
    def __init__(
        self,
        data: Dict[str, Any],
        *,
        memory_records: Iterable[MemorySnapshot],
    ) -> None:
        super().__init__()
        self.data = data
        self.memory_records = memory_records

    @classmethod
    def from_snapshot(
        cls,
        allocations: Iterator[AllocationRecord],
        *,
        memory_records: Iterable[MemorySnapshot],
        native_traces: bool,
    ) -> "FlameGraphReporter":
        data: Dict[str, Any] = {
            "name": "<root>",
            "location": [html.escape("<tracker>"), "<b>memray</b>", 0],
            "value": 0,
            "children": {},
            "n_allocations": 0,
            "thread_id": "0x0",
            "interesting": True,
            "import_system": False,
        }

        unique_threads = set()
        for record in allocations:
            size = record.size
            thread_id = record.thread_name

            data["value"] += size
            data["n_allocations"] += record.n_allocations

            current_frame = data
            stack = (
                tuple(record.hybrid_stack_trace())
                if native_traces
                else record.stack_trace()
            )
            num_skipped_frames = 0
            is_import_system = False
            for index, (stack_frame, next_frame) in enumerate(
                pairwise_longest(reversed(stack))
            ):
                if is_cpython_internal(stack_frame):
                    num_skipped_frames += 1
                    continue
                # Check if the next frame is from the import system. We check
                # the next frame because the "import ..." code will be the parent
                # of the first frame to enter the import system and we want to hide
                # that one as well.
                if is_frame_from_import_system(stack_frame) or (
                    next_frame and is_frame_from_import_system(next_frame)
                ):
                    is_import_system = True
                if (stack_frame, thread_id) not in current_frame["children"]:
                    node = create_framegraph_node_from_stack_frame(
                        stack_frame, import_system=is_import_system
                    )
                    current_frame["children"][(stack_frame, thread_id)] = node

                current_frame = current_frame["children"][(stack_frame, thread_id)]
                current_frame["value"] += size
                current_frame["n_allocations"] += record.n_allocations
                current_frame["thread_id"] = thread_id
                unique_threads.add(thread_id)

                if index - num_skipped_frames > MAX_STACKS:
                    current_frame["name"] = "<STACK TOO DEEP>"
                    current_frame["location"] = ["...", "...", 0]
                    break

        transformed_data = with_converted_children_dict(data)
        transformed_data["unique_threads"] = sorted(unique_threads)
        return cls(transformed_data, memory_records=memory_records)

    def render(
        self,
        metadata: Metadata,
        show_memory_leaks: bool,
        merge_threads: bool,
    ) -> None:
        html_code = render_report(
            kind="lel",
            data=self.data,
            metadata=metadata,
            memory_records=self.memory_records,
            show_memory_leaks=show_memory_leaks,
            merge_threads=merge_threads,
        )
        return html_code


app = Flask(__name__)
reader = FileReader("/home/pablogsal/github/memray/lel.bin", report_progress=True)


@app.route("/")
def index():
    show_memory_leaks = False
    merge_threads = True
    temporary_allocation_threshold = -1

    try:
        if reader.metadata.has_native_traces:
            warn_if_not_enough_symbols()

        if show_memory_leaks:
            snapshot = reader.get_leaked_allocation_records(
                merge_threads=merge_threads if merge_threads is not None else True
            )
        elif temporary_allocation_threshold >= 0:
            snapshot = reader.get_temporary_allocation_records(
                threshold=temporary_allocation_threshold,
                merge_threads=merge_threads if merge_threads is not None else True,
            )
        else:
            snapshot = reader.get_high_watermark_allocation_records(
                merge_threads=merge_threads if merge_threads is not None else True
            )
        memory_records = tuple(reader.get_memory_snapshots())
    except OSError as e:
        raise ValueError("oh no")

    reporter = FlameGraphReporter.from_snapshot(
        allocations=snapshot,
        memory_records=memory_records,
        native_traces=False,
    )

    return reporter.render(
        metadata=reader.metadata,
        show_memory_leaks=show_memory_leaks,
        merge_threads=merge_threads,
    )


@app.route("/time", methods=["POST"])
def time():
    # Get the strings from the request's JSON data
    string1 = request.json["string1"]
    string2 = request.json["string2"]

    # Transform the strings to datetime objects
    time1 = datetime.datetime.strptime(string1, "%Y-%m-%d %H:%M:%S.%f")
    time2 = datetime.datetime.strptime(string2, "%Y-%m-%d %H:%M:%S.%f")

    # Transform the datetime objects to milliseconds since the epoch
    time1_ms = int(time1.timestamp() * 1000)
    time2_ms = int(time2.timestamp() * 1000)

    records = reader.get_range_allocation_records(time1_ms, time2_ms)

    reporter = FlameGraphReporter.from_snapshot(
        allocations=records,
        memory_records=[],
        native_traces=False,
    )

    # Return the result as a JSON
    return jsonify(data=reporter.data)


if __name__ == "__main__":
    app.run(debug=True)
