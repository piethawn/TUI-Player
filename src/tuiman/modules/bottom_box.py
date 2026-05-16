from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.color import Color
from textual.widget import Widget
from textual.widgets import Button
from ..utils.player import get_progress, get_waveform, pause, resume


class PlayControls(Widget):
    """Pause/resume, forward/backward controls"""
    def compose(self) -> ComposeResult:
        yield Button("⏮", id="backward", classes="playback", variant="primary", flat=True)
        yield Button("||", id="pause",variant="success", flat=True)
        yield Button("⏭", id="forward", classes="playback",variant="primary", flat=True)

    def on_button_pressed(self, event: Button.Pressed)-> None:
        # play/pause, forward backward buttons
        if event.button.id == "pause":
            if event.button.label == "||":
                event.button.label = "▶"
                event.button.styles.border = ("round", "yellow")
                event.button.styles.color = "deeppink"
                pause()
            else:
                event.button.label = "||"
                event.button.styles.border = ("round", "deeppink")
                event.button.styles.color = Color(255, 255, 255, 0.7)
                resume()

        elif "playback" in event.button.classes:
            play_btn = self.query_one("#pause", Button)
            if play_btn.label == "▶":
                play_btn.label = "||"
                play_btn.styles.border = ("round", "deeppink")
                play_btn.styles.color = Color(255, 255, 255, 0.7)


_WAVE_CHARS = " ▁▂▃▄▅▆▇█"
_NUM_ROWS = 3


class Visualizer(Widget):
    """Scrolling waveform display. Pre-computed amplitude, cursor tracks playback."""

    DEFAULT_CSS = """
    Visualizer {
        width: 100%;
        height: 3;
        color: $accent;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(1 / 15, self.refresh)

    def render(self) -> RichText:
        waveform = get_waveform()
        progress = get_progress()
        width = max(1, self.size.width)

        try:
            pos_frac = progress[0] / progress[1] if progress[1] > 0 else 0.0
        except ZeroDivisionError:
            pos_frac = 0.0

        # Waveform scrolls: playhead fixed at 1/3, data shifts left
        anchor = width // 3
        wf_len = len(waveform)
        center_idx = int(pos_frac * wf_len) if wf_len > 0 else 0

        try:
            c = self.styles.color
            color = f"#{c.r:02x}{c.g:02x}{c.b:02x}"
        except Exception:
            color = "#00e676"

        total_units = _NUM_ROWS * 8
        rows: list[list[tuple[str, str]]] = [[] for _ in range(_NUM_ROWS)]

        for i in range(width):
            wf_idx = center_idx + (i - anchor)
            amp = waveform[wf_idx] if waveform and 0 <= wf_idx < wf_len else 0.0
            units = int(amp * total_units)

            for r in range(_NUM_ROWS):
                row_from_bottom = _NUM_ROWS - 1 - r
                row_units = units - row_from_bottom * 8
                if row_units >= 8:
                    char = "█"
                elif row_units > 0:
                    char = _WAVE_CHARS[row_units]
                else:
                    char = " "
                rows[r].append((char, color))

        text = RichText()
        for r, row in enumerate(rows):
            for char, style in row:
                text.append(char, style=style)
            if r < _NUM_ROWS - 1:
                text.append("\n")
        return text

class QueueOptions(Widget):
    """show/ hide queue, shuffle options"""

    def compose(self) -> ComposeResult:
        yield Button("Queue", variant="primary", flat=True, classes="queue-btn", id="show-queue")
        yield Button("Shuffle", variant="primary", flat=True, classes="queue-btn" ,id="shuffle-queue")


    def on_mount(self) -> None:
        self.query_one("#show-queue").border_title = "Show"
        self.query_one("#shuffle-queue").border_subtitle = "queue"

class BottomBox(Widget):
    """Class containing play controls and waveform visualizer"""
    def compose(self) -> ComposeResult:
        yield PlayControls()
        yield Visualizer()
        yield QueueOptions()
