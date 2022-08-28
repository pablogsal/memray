from importlib.resources import path
import pathlib

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from collections import defaultdict
from dataclasses import dataclass

from memray import FileReader


@dataclass(frozen=True, eq=True)
class Location:
    function: str
    file: str
    line: int


@dataclass
class AllocationEntry:
    own_memory: int
    total_memory: int
    n_allocations: int
    thread_ids: set[int]


class CodeFormatter(HtmlFormatter):
    """Formatter that highlights the specified code lines in red"""

    def __init__(
        self, total_memory: int, lines_to_highlight: list[int], *args, **kwargs
    ):
        self.lines_to_highlight = lines_to_highlight
        self.total_memory = total_memory
        super().__init__(*args, **kwargs)

    def wrap(self, source):
        source = super().wrap(source)
        return self._wrap_code(source)

    def _wrap_code(self, source):
        line_no = self.linenostart - 1
        for i, t in source:
            line_no += 1
            if i == 1:
                # Wrap the line with a highlight style if it's a line we want to highlight
                if (line_no - 1) in self.lines_to_highlight:
                    allocation = self.lines_to_highlight[line_no - 1]
                    percentage = allocation.total_memory / self.total_memory
                    number = round(percentage * 4) + 1
                    t = f"<span class='highlight-{number}'>{t}</span>"
                    t += f"<span class='tooltiptext'>total: {percentage*100} - {allocation}</span>"
            yield i, t


def html_generator(code: str, total_memory: int, lines_to_highlight: list[int]):
    yield "<!DOCTYPE html>"
    yield "<html>"
    yield "<head>"
    yield "<title>MEMRAY REPORT</title>"
    yield '<meta charset="UTF-8">'

    formatter = CodeFormatter(
        total_memory=total_memory,
        lines_to_highlight=lines_to_highlight,
        linenos=True,
        full=True,
        style="material",
    )

    yield "<style>"

    # Yield css styles for 10 different colors from green to red
    for i in range(1, 6):
        yield f".highlight-{i} {{ background-color: hsl({150 + (i/5)*100}, 50%, 20%); display: block; }}"
        yield "span.highlight-{i}:hover + span.tooltiptext { visibility: visible; }"

    # Add css for the highlight class with red background bold text
    yield "table td:last-child { width: 100%; }"
    yield "table.highlighttable {     display: table; border-collapse: separate; }"
    yield "span.tooltiptext { visibility: hidden; background-color: black; color: #fff; text-align: center; padding: 5px 0; border-radius: 6px; position: absolute; z-index: 1; }"
    yield "span.annotation { background-color: yellow; padding: 20px; display: none; }"
    # yield "span.highlight:hover { background-color: #ff0000; }"
    yield formatter.get_style_defs()
    yield "</style>"
    yield "</head>"

    yield "<body>"
    code = highlight(code, PythonLexer(), formatter)
    yield code
    yield "</body>"
    yield "</html>"


def generate_html(*args, **kwargs):
    return "\n".join(html_generator(*args, **kwargs))


def main(allocations):
    processed_allocations = defaultdict(
        lambda: AllocationEntry(
            own_memory=0, total_memory=0, n_allocations=0, thread_ids=set()
        )
    )

    current_total = 0
    for allocation in allocations:
        current_total += allocation.size

        stack_trace = list(allocation.stack_trace())
        if not stack_trace:
            frame = processed_allocations[Location(function="???", file="???", line=0)]
            frame.total_memory += allocation.size
            frame.own_memory += allocation.size
            frame.n_allocations += allocation.n_allocations
            frame.thread_ids.add(allocation.tid)
            continue
        (function, file_name, line), *caller_frames = stack_trace
        location = Location(function=function, file=file_name, line=line)
        processed_allocations[location] = AllocationEntry(
            own_memory=allocation.size,
            total_memory=allocation.size,
            n_allocations=allocation.n_allocations,
            thread_ids={allocation.tid},
        )

        # Walk upwards and sum totals
        visited = set()
        for function, file_name, line in caller_frames:
            location = Location(function=function, file=file_name, line=line)
            frame = processed_allocations[location]
            if location in visited:
                continue
            visited.add(location)
            frame.total_memory += allocation.size
            frame.n_allocations += allocation.n_allocations
            frame.thread_ids.add(allocation.tid)

    files = defaultdict(dict)
    for location, allocation in processed_allocations.items():
        files[location.file][location.line] = allocation

    for file, allocations in files.items():
        thefile = pathlib.Path(file)
        if not thefile.exists():
            continue
        with open(thefile) as codefile:
            code = codefile.read()

        with open("results/" + thefile.name.replace(".py", ".html"), "w") as html_file:
            print(
                generate_html(
                    code, total_memory=current_total, lines_to_highlight=allocations
                ),
                file=html_file,
            )
    return processed_allocations


with FileReader("test.bin") as reader:
    allocations = reader.get_high_watermark_allocation_records()
    main(allocations)
