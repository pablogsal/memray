from typing import cast
import statistics
import argparse
import os
from pathlib import Path
from typing import Optional

from memray import FileReader
from memray._errors import MemrayCommandError

from ..reporters.heatmap import HeatmapReporter
from .common import HighWatermarkCommand
from .common import ReporterFactory


class HeatmapCommand(HighWatermarkCommand):
    """Generate an HTML heatmap with all records in the peak memory usage"""

    def __init__(self) -> None:
        super().__init__(
            reporter_factory=cast(ReporterFactory, HeatmapReporter.from_snapshot),
            reporter_name="heatmap",
        )

    def prepare_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            help="Output file name",
            default=None,
        )
        parser.add_argument(
            "-f",
            "--force",
            help="If the output file already exists, overwrite it",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--leaks",
            help="Show memory leaks, instead of peak memory usage",
            action="store_true",
            dest="show_memory_leaks",
            default=False,
        )
        parser.add_argument("results", help="Results of the tracker run")

    def write_report(
        self,
        result_path: Path,
        output_file: Path,
        show_memory_leaks: bool,
        merge_threads: Optional[bool] = None,
    ) -> None:
        try:
            reader = FileReader(os.fspath(result_path), report_progress=True)
            snapshot = tuple(reader.get_allocation_records())
            memory_records = tuple(reader.get_memory_snapshots())
            reporter = self.reporter_factory(
                snapshot,
                memory_records=memory_records,
                native_traces=reader.metadata.has_native_traces,
            )
        except OSError as e:
            raise MemrayCommandError(
                f"Failed to parse allocation records in {result_path}\nReason: {e}",
                exit_code=1,
            )

        with open(os.fspath(output_file.expanduser()), "w") as f:
            kwargs = {}
            if merge_threads is not None:
                kwargs["merge_threads"] = merge_threads
            reporter.render(
                outfile=f,
                metadata=reader.metadata,
                show_memory_leaks=show_memory_leaks,
                **kwargs,
            )