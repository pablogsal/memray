"""Tests for exercising the public API."""

import pytest

from bloomberg.pensieve import FileDestination
from bloomberg.pensieve import FileReader
from bloomberg.pensieve import SocketDestination
from bloomberg.pensieve import Tracker
from bloomberg.pensieve._test import MemoryAllocator


def test_file_reader_as_context_manager(tmp_path):
    # GIVEN
    allocator = MemoryAllocator()
    result_file = tmp_path / "test.bin"
    # WHEN
    with Tracker(result_file):
        allocator.valloc(1234)
        allocator.free()

    # THEN
    with FileReader(result_file) as reader:
        pass

    with pytest.raises(ValueError, match="Operation on a closed FileReader"):
        list(reader.get_high_watermark_allocation_records())


def test_file_destination(tmp_path):
    # GIVEN
    allocator = MemoryAllocator()
    result_file = tmp_path / "test.bin"
    # WHEN
    with Tracker(destination=FileDestination(result_file)):
        allocator.valloc(1234)
        allocator.free()

    # THEN
    with FileReader(result_file) as reader:
        assert len(list(reader.get_allocation_records())) == 2


def test_file_destination_str_path(tmp_path):
    # GIVEN
    allocator = MemoryAllocator()
    result_file = str(tmp_path / "test.bin")
    # WHEN
    with Tracker(destination=FileDestination(result_file)):
        allocator.valloc(1234)
        allocator.free()

    # THEN
    with FileReader(result_file) as reader:
        assert len(list(reader.get_allocation_records())) == 2


def test_combine_destination_args():
    """Combining `writer` and `file_name` arguments in the `Tracker` should
    raise an exception."""

    # GIVEN/WHEN/THEN
    with pytest.raises(
        TypeError,
        match="Exactly one of 'file_name' or 'destination' argument must be specified",
    ):
        with Tracker(destination=SocketDestination(port=1234), file_name="foo"):
            pass


def test_no_destination_arg():
    """Not passing either `writer` or `file_name` argument in the `Tracker` should
    raise an exception."""

    # GIVEN/WHEN/THEN
    with pytest.raises(
        TypeError,
        match="Exactly one of 'file_name' or 'destination' argument must be specified",
    ):
        with Tracker():
            pass