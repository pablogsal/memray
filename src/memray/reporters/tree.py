import linecache
import sys
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from typing import IO
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterator
from typing import Optional
from typing import Tuple

from textual import events
from textual.app import App
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.dom import DOMNode
from textual.screen import ModalScreen
from textual.widgets import Footer
from textual.widgets import Label
from textual.widgets import ListItem
from textual.widgets import ListView
from textual.widgets import TextArea
from textual.widgets import Tree
from textual.widgets._text_area import Edit
from textual.widgets.tree import TreeNode

from memray import AllocationRecord
from memray._memray import size_fmt
from memray.reporters.frame_tools import is_cpython_internal
from memray.reporters.frame_tools import is_frame_from_import_system
from memray.reporters.frame_tools import is_frame_interesting
from memray.reporters.tui import _filename_to_module_name

MAX_STACKS = int(sys.getrecursionlimit() // 2.5)

StackElement = Tuple[str, str, int]

ROOT_NODE = ("<ROOT>", "", 0)


@dataclass
class Frame:
    """A frame in the tree"""

    location: StackElement
    value: int
    children: Dict[StackElement, "Frame"] = field(default_factory=dict)
    n_allocations: int = 0
    thread_id: str = ""
    interesting: bool = True
    import_system: bool = False


class FrozenTextArea(TextArea):
    """A text area that cannot be edited"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_blink = False

    def edit(self, edit: Edit) -> Any:
        self.app.pop_screen()


class FrameDetailScreen(ModalScreen[bool]):
    """A screen that displays information about a frame"""

    def __init__(self, frame: Frame):
        super().__init__()
        self.frame = frame

    def compose(self) -> ComposeResult:
        function, file, line = self.frame.location
        delta = 3
        lines = linecache.getlines(file)[line - delta : line + delta]
        text = FrozenTextArea(
            "\n".join(lines), language="python", theme="dracula", id="textarea"
        )
        text.select_line(delta + 1)
        text.show_line_numbers = False
        yield Grid(
            text,
            ListView(
                ListItem(Label(f":compass: Function: {function}")),
                ListItem(Label(f":compass: Location: {file}:{line}")),
                ListItem(
                    Label(f":floppy_disk: Allocations: {self.frame.n_allocations}")
                ),
                ListItem(Label(f":package: Size: {size_fmt(self.frame.value)}")),
                ListItem(Label(f":thread: Thread: {self.frame.thread_id}")),
                ListItem(Label("Press any key to go back")),
            ),
            id="node",
        )
        yield Footer()

    def on_key(self, event: events.Key) -> None:
        self.dismiss(True)


class TreeApp(App[None]):
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(
            key="s", action="show_information", description="Show node information"
        ),
        Binding(key="i", action="hide_import_system", description="Hide import system"),
        Binding(
            key="e", action="expand_linear_group", description="Expand linear group"
        ),
    ]

    DEFAULT_CSS = """
        FrameDetailScreen {
            align: center middle;
        }

        Label {
            padding: 1 3;
        }

        #textarea {
            height: 20;
        }

        #node {
            grid-size: 1 2;
            grid-gutter: 1 2;
            padding: 0 1;
            width: 80;
            height: 40;
            border: thick $background 80%;
            background: $surface;
        }
    """

    def __init__(self, data: Frame):
        super().__init__()
        self.data = data
        self.filter: Optional[Callable[[Frame], bool]] = None

    def expand_bigger_nodes(self, node: TreeNode[Frame]) -> None:
        if not node.children:
            return
        biggest_child = max(
            node.children, key=lambda child: 0 if not child.data else child.data.value
        )
        biggest_child.toggle()
        self.expand_bigger_nodes(biggest_child)

    def compose(self) -> ComposeResult:
        tree = self.create_tree(self.data)
        tree.root.expand()
        self.expand_bigger_nodes(tree.root)
        yield tree
        yield Footer()

    def action_expand_linear_group(self) -> None:
        tree = self.query_one(Tree)
        assert tree
        current_node = tree.cursor_node
        while current_node:
            current_node.toggle()
            if len(current_node.children) != 1:
                break
            current_node = current_node.children[0]

    def action_show_information(self) -> None:
        tree: Tree[Frame] = self.query_one(Tree)
        if tree.cursor_node is None or tree.cursor_node.data is None:
            return
        self.push_screen(FrameDetailScreen(tree.cursor_node.data))

    def create_tree(
        self,
        node: Frame,
        parent_tree: Optional[TreeNode[Frame]] = None,
        root_node: Optional[Tree[Frame]] = None,
    ) -> Tree[Frame]:
        if node.value == 0:
            return Tree("<No allocations>")
        value = node.value
        root_data = root_node.root.data if root_node else node
        assert root_data is not None
        size_str = f"{size_fmt(value)} ({100 * value / root_data.value:.2f} %)"
        function, file, lineno = node.location
        icon = ":page_facing_up:" if len(node.children) == 0 else ":open_file_folder:"
        frame_text = (
            "{icon}[{info_color}] {size} "
            "[bold]{function}[/bold][/{info_color}]  "
            "[dim cyan]{code_position}[/dim cyan]".format(
                icon=icon,
                size=size_str,
                info_color=_info_color(node, root_data),
                function=function,
                code_position=f"{_filename_to_module_name(file)}:{lineno}"
                if lineno != 0
                else file,
            )
        )
        children = tuple(node.children.values())
        if self.filter is not None:
            children = tuple(filter(self.filter, children))
        if root_node is None:
            root_node = Tree(frame_text, data=node)
            new_tree = root_node.root
        else:
            assert parent_tree is not None
            new_tree = parent_tree.add(
                frame_text, data=node, allow_expand=bool(len(children))
            )
        for child in children:
            self.create_tree(child, new_tree, root_node=root_node)
        return root_node

    def action_hide_import_system(self) -> None:
        self.query_one(Tree).remove()
        if self.filter is None:

            def _filter(node: Frame) -> bool:
                return not node.import_system

            self.filter = _filter
        else:
            self.filter = None
        self.remount_tree()

    def remount_tree(self) -> None:
        new_tree: Tree[Frame] = self.create_tree(self.data)
        self.mount(new_tree)
        new_tree.focus()
        new_tree.root.expand()
        self.expand_bigger_nodes(new_tree.root)

    @property
    def namespace_bindings(self) -> Dict[str, Tuple[DOMNode, Binding]]:
        bindings = super().namespace_bindings.copy()
        if self.filter is not None:
            node, binding = bindings["i"]
            bindings["i"] = (
                node,
                replace(binding, description="Show import system"),
            )
        return bindings


def _info_color(node: Frame, root_node: Frame) -> str:
    proportion_of_total = node.value / root_node.value
    if proportion_of_total > 0.6:
        return "red"
    elif proportion_of_total > 0.2:
        return "yellow"
    elif proportion_of_total > 0.05:
        return "green"
    else:
        return "bright_green"


class TreeReporter:
    def __init__(self, data: Frame):
        super().__init__()
        self.data = data

    @classmethod
    def from_snapshot(
        cls,
        allocations: Iterator[AllocationRecord],
        *,
        biggest_allocs: int = 10,
        native_traces: bool,
    ) -> "TreeReporter":
        data = Frame(location=ROOT_NODE, value=0, import_system=False, interesting=True)
        for record in sorted(allocations, key=lambda alloc: alloc.size, reverse=True)[
            :biggest_allocs
        ]:
            size = record.size
            data.value += size
            data.n_allocations += record.n_allocations

            current_frame = data
            stack = (
                tuple(record.hybrid_stack_trace())
                if native_traces
                else record.stack_trace()
            )
            for index, stack_frame in enumerate(reversed(stack)):
                if is_cpython_internal(stack_frame):
                    continue
                is_import_system = is_frame_from_import_system(stack_frame)
                is_interesting = (
                    is_frame_interesting(stack_frame) and not is_import_system
                )
                if stack_frame not in current_frame.children:
                    node = Frame(
                        value=0,
                        location=stack_frame,
                        import_system=is_import_system,
                        interesting=is_interesting,
                    )
                    current_frame.children[stack_frame] = node

                current_frame = current_frame.children[stack_frame]
                current_frame.value += size
                current_frame.n_allocations += record.n_allocations
                current_frame.thread_id = record.thread_name

                if index > MAX_STACKS:
                    break

        return cls(data)

    def get_app(self) -> TreeApp:
        return TreeApp(self.data)

    def render(
        self,
        *,
        file: Optional[IO[str]] = None,
    ) -> None:
        self.get_app().run()
