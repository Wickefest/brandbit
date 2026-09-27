# Strips markdown emphasis from narrative text so rationales stay plain prose.
# Used when rendering the cleaned rationale on the front end.

from __future__ import annotations

import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_UNDERSCORE = re.compile(r"(?<!\w)_(.+?)_(?!\w)")
_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MULTI_UNDERSCORE = re.compile(r"_{2,}")
_MULTI_STAR = re.compile(r"\*{2,}")


# Removes markdown bold and italic markers while keeping section headers.
def plain_narrative(text: str) -> str:
    if not text:
        return text
    out = text.replace("\r\n", "\n")
    out = _BOLD.sub(r"\1", out)
    out = _ITALIC_UNDERSCORE.sub(r"\1", out)
    out = _ITALIC_STAR.sub(r"\1", out)
    out = _MULTI_UNDERSCORE.sub("", out)
    out = _MULTI_STAR.sub("", out)
    # Second pass strips leftover bold markers on non header lines.
    lines: list[str] = []
    for line in out.split("\n"):
        if line.lstrip().startswith("##"):
            lines.append(line)
        else:
            lines.append(line.replace("**", "").replace("__", ""))
    return "\n".join(lines).strip()
