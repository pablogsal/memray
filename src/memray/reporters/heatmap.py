from math import log10
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Tuple
from typing import TextIO

from math import log, log10, exp
from collections import Counter

from memray import AllocationRecord
from memray import AllocatorType
from memray import MemorySnapshot
from memray import Metadata
import memray
from memray.reporters.templates import render_report
from memray.reporters.stats import get_histogram_databins


def calculate_bins_from_allocations(maxx, data, bins):
    """Make histogram bins from the list of sizes into n buckets"""
    if not data:
        return []
    low = log10(1)
    high = log10(maxx)
    if low == high:
        low = low / 2
    step = (high - low) / bins

    # Determine the upper bound in bytes for each bin
    steps = [int(exp(low + step * (i + 1))) for i in range(bins)]
    dist = Counter(steps)
    for size in data:
        bucket = min(int((log10(size) - low) // step), bins - 1) if size else 0
        dist[bucket] += 1
    return [(steps[b], dist[b]) for b in range(bins)]

class HeatmapReporter:
    def __init__(
        self,
        data: List[Dict[str, Any]],
        *,
        memory_records: Iterable[MemorySnapshot],
    ):
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
    ) -> "HeatmapReporter":

        with open("heatmap.txt", "w") as f:
            for index, record in enumerate(allocations):
                if record.allocator in {AllocatorType.FREE, AllocatorType.MUNMAP, AllocatorType.PYMALLOC_FREE}:
                    continue
                if record.size == 0:
                    continue
                f.write(f"{index*20} {log10(record.size)*100}\n")

        result = []
        memory_records = tuple(memory_records)
        allocations = tuple(allocations)
        ntom = int(len(allocations)/len(memory_records)) + 10
        maxx = max([allocation.size for allocation in allocations])
        i = 0
        res = []
        sizes= []

        for index, record in enumerate(allocations):
            if index % ntom == 0:
                for s, c in calculate_bins_from_allocations(maxx, sizes, 100):
                    res.append({"time": memory_records[0].time+i, "bucket": s, "size": c})
                i += 1
                sizes.clear()
            if record.allocator in {AllocatorType.FREE, AllocatorType.MUNMAP, AllocatorType.PYMALLOC_FREE}:
                continue
            if record.size == 0:
                continue
            sizes.append(record.size)

        return cls(res, memory_records=memory_records)

    def render(
        self,
        outfile: TextIO,
        metadata: Metadata,
        show_memory_leaks: bool,
    ) -> None:
        html_code = render_report(
            kind="heatmap",
            data=self.data,
            metadata=metadata,
            memory_records=self.memory_records,
            show_memory_leaks=show_memory_leaks,
            merge_threads=True,
        )
        print(html_code, file=outfile)

