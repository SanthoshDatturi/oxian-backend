import json
import re
from typing import Dict, Generator, Optional

StreamEvent = Dict[str, object]


class MixedStreamParser:
    TAG_START_PATTERN = re.compile(r"<([A-Z_]+)>")

    def __init__(self) -> None:
        self.buffer: str = ""
        self.total_buffer: str = ""
        self.json_buffer: str = ""
        self.in_block: bool = False
        self.tag_name: Optional[str] = None

    def feed(self, chunk: str) -> Generator[StreamEvent, None, None]:
        """
        Feed new streamed text into the parser and yield events immediately.
        """

        self.total_buffer += chunk
        self.buffer += chunk

        while True:
            # --------------------
            # MARKDOWN STATE
            # --------------------
            if not self.in_block:
                match = self.TAG_START_PATTERN.search(self.buffer)

                if not match:
                    # keep tail in case a tag splits across chunks
                    safe_flush = len(self.buffer) - 20

                    if safe_flush > 0:
                        text = self.buffer[:safe_flush]
                        self.buffer = self.buffer[safe_flush:]

                        yield {"type": "markdown", "delta": text}

                    break

                start = match.start()
                tag = match.group(1)

                if start > 0:
                    yield {"type": "markdown", "delta": self.buffer[:start]}

                self.buffer = self.buffer[match.end() :]

                self.in_block = True
                self.tag_name = tag
                self.json_buffer = ""

                continue

            # --------------------
            # STRUCTURED STATE
            # --------------------
            tag_name = self.tag_name
            assert tag_name is not None
            end_tag = f"</{tag_name}>"
            end_index = self.buffer.find(end_tag)

            if end_index == -1:
                self.json_buffer += self.buffer
                self.buffer = ""
                break

            self.json_buffer += self.buffer[:end_index]

            try:
                data = json.loads(self.json_buffer)

                yield {"type": tag_name.lower(), "data": data}

            except json.JSONDecodeError:
                yield {"type": "error", "raw": self.json_buffer}

            self.buffer = self.buffer[end_index + len(end_tag) :]

            self.in_block = False
            self.tag_name = None
            self.json_buffer = ""

            continue
