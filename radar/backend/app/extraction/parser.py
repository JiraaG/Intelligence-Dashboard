"""Sanitize HTML entry → testo piano per il prompt LLM.

Purga tag multimediali/tracking e il loro contenuto interno; cap byte
**prima** del parse; poi unescape e normalizzazione whitespace.
Niente BeautifulSoup: solo ``html.parser`` stdlib.

SoT:
    .agents/AGENTS.md §2 (purgazione media); radar/.ecc/rules/backend.md HTML Sanitize.
"""

import re
from html.parser import HTMLParser
from html import unescape

from app.core.config import MAX_ENTRY_CONTENT_BYTES


class EntryContentTooLarge(ValueError):
    """HTML grezzo oltre ``MAX_ENTRY_CONTENT_BYTES``: non si avvia il parse."""


class HTMLStripper(HTMLParser):
    """Parser che emette solo testo fuori dai tag spazzatura/multimediali.

    Mantiene ``ignored_stack``: finché lo stack non è vuoto, ``handle_data``
    scarta il testo (script/style/iframe/svg/noscript/meta/video/audio/embed/
    object/img/picture/source). Gli attributi non sono mai riprodotti.
    """

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.fed: list[str] = []
        # Tag di cui ignorare sia il markup sia tutto il testo interno.
        self.content_ignored_tags = {
            "script", "style", "iframe", "svg", "noscript", "meta",
            "video", "audio", "embed", "object", "img", "picture", "source"
        }
        self.ignored_stack: list[str] = []

    def _has_matching_close_tag(self, tag_lower: str) -> bool:
        """True se nel resto del documento c'è un ``</tag>`` prima di un nuovo open.

        Serve per void-ish tags (``img``, ``source``, ``meta``, ``embed``): se non
        c'è close matching non si pusha sullo stack (tipicamente self-closing).
        """
        try:
            raw = self.rawdata
            line, offset = self.getpos()
            idx = 0
            lines = raw.splitlines(keepends=True)
            if line - 1 < len(lines):
                idx = sum(len(line_str) for line_str in lines[:line - 1]) + offset
            remaining = raw[idx:]
            close_tag = f"</{tag_lower}>"
            close_idx = remaining.find(close_tag)
            if close_idx == -1:
                return False

            start_tag_end = remaining.find(">")
            if start_tag_end != -1:
                next_start_search = remaining[start_tag_end:]
                next_start_idx = -1
                for pattern in (f"<{tag_lower} ", f"<{tag_lower}>", f"<{tag_lower}/"):
                    p_idx = next_start_search.find(pattern)
                    if p_idx != -1:
                        actual_p_idx = p_idx + start_tag_end
                        if next_start_idx == -1 or actual_p_idx < next_start_idx:
                            next_start_idx = actual_p_idx
                if next_start_idx != -1 and next_start_idx < close_idx:
                    return False
            return True
        except (AttributeError, TypeError, IndexError, ValueError):
            return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.content_ignored_tags:
            # Void-ish: push solo se esiste un close esplicito nel markup.
            if tag_lower in {"img", "source", "meta", "embed"}:
                if self._has_matching_close_tag(tag_lower):
                    self.ignored_stack.append(tag_lower)
            else:
                self.ignored_stack.append(tag_lower)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.ignored_stack:
            self.ignored_stack.remove(tag_lower)

    def handle_data(self, data: str) -> None:
        # Testo solo fuori dai tag ignorati (riduce token LLM / rimuove media).
        if not self.ignored_stack:
            self.fed.append(data)

    def get_data(self) -> str:
        """Concatena i frammenti di testo accumulati."""
        return "".join(self.fed)


def strip_html_tags(html_content: str) -> str:
    """Rimuove tutto l'HTML, unescape entità e normalizza gli spazi.

    Cap byte **prima** di ``HTMLParser.feed`` per non parsare payload enormi.
    Collassa whitespace orizzontale e limita i newline consecutivi a due.

    Args:
        html_content: HTML grezzo da ``ValidatedMinifluxEntry.content``.
    Returns:
        Testo piano strip-pato; stringa vuota se input vuoto.
    Raises:
        EntryContentTooLarge: oltre ``MAX_ENTRY_CONTENT_BYTES``.
    SoT:
        AGENTS.md §2 purgazione media; llm-json-extraction (content[:4000] a valle).
    """
    if not html_content:
        return ""

    content_bytes = len(html_content.encode("utf-8"))
    if content_bytes > MAX_ENTRY_CONTENT_BYTES:
        raise EntryContentTooLarge(
            f"Contenuto entry {content_bytes} bytes supera "
            f"MAX_ENTRY_CONTENT_BYTES={MAX_ENTRY_CONTENT_BYTES}"
        )

    stripper = HTMLStripper()
    stripper.feed(html_content)
    text = stripper.get_data()

    # Entità residue (&amp;, &quot;, …) → caratteri Unicode.
    text = unescape(text)

    # Tab/spazi multipli → spazio singolo (non tocca i newline).
    text = re.sub(r"[ \t]+", " ", text)

    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    # Max due newline: preserva paragrafi senza gonfiare il prompt.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
