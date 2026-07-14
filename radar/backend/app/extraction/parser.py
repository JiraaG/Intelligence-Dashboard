import re
from html.parser import HTMLParser
from html import unescape

from app.core.config import MAX_ENTRY_CONTENT_BYTES


class EntryContentTooLarge(ValueError):
    """Raised when raw entry HTML exceeds MAX_ENTRY_CONTENT_BYTES before parsing."""


class HTMLStripper(HTMLParser):
    """
    Parser HTML personalizzato che rimuove i tag ed esclude completamente 
    i contenuti interni dei tag spazzatura, di tracciamento e multimediali.
    """
    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.fed: list[str] = []
        # Tag di cui vogliamo ignorare sia il tag che tutto il contenuto testuale interno
        self.content_ignored_tags = {
            "script", "style", "iframe", "svg", "noscript", "meta", 
            "video", "audio", "embed", "object"
        }
        self.ignored_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.content_ignored_tags:
            self.ignored_stack.append(tag_lower)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.ignored_stack:
            self.ignored_stack.remove(tag_lower)

    def handle_data(self, data: str) -> None:
        # Aggiunge i dati testuali solo se non siamo all'interno di tag da ignorare
        if not self.ignored_stack:
            self.fed.append(data)

    def get_data(self) -> str:
        return "".join(self.fed)

def strip_html_tags(html_content: str) -> str:
    """
    Rimuove tutti i tag HTML, decodifica le entità HTML e normalizza gli spazi bianchi.
    Esclude completamente i contenuti interni di script, style, e tag multimediali.
    Enforce MAX_ENTRY_CONTENT_BYTES prima del parsing HTML.
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

    # Decodifica le entità HTML residue (es. &amp;, &quot;, &#39;)
    text = unescape(text)

    # Normalizza gli spazi bianchi orizzontali (tabulazioni e spazi multipli in spazio singolo)
    text = re.sub(r"[ \t]+", " ", text)

    # Divide in righe, pulisce spazi iniziali/finali per ciascuna riga e ricompone
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    # Collassa tre o più ritorni a capo consecutivi in massimo due (preservando la struttura in paragrafi)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
