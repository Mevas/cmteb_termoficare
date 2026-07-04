"""Parsing helpers for CMTEB Termoficare status pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata

from bs4 import BeautifulSoup


ADDRESS_PREFIX_RE = re.compile(
    r"\b(Str|Bld|Bd|Calea|Aleea|Intrarea|Sos|Șos|Şos|Piata|Piața|Piaţa)\b",
    re.IGNORECASE,
)
ETA_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\s+\d{1,2}:\d{2}\b")
STATUS_VALUES = {
    "acc",
    "inc",
    "inc acc",
    "acc inc",
    "deficienta acc",
    "deficienta inc",
    "oprire acc",
    "oprire inc",
    "oprire acc inc",
    "deficienta acc inc",
}


@dataclass(slots=True)
class CmtebStatus:
    """Parsed CMTEB status for one configured address."""

    state: str
    match_found: bool
    sector: str | None = None
    punct_termic: str | None = None
    affected_count: str | None = None
    service: str | None = None
    status_type: str | None = None
    cause: str | None = None
    eta: str | None = None
    eta_raw: str | None = None
    matched_zone: str | None = None
    address_lines: list[str] | None = None
    record_text: str | None = None
    parser: str = "table"

    def as_attributes(self) -> dict[str, object]:
        """Return Home Assistant attributes without the state value."""
        return {
            "match_found": self.match_found,
            "sector": self.sector,
            "punct_termic": self.punct_termic,
            "affected_count": self.affected_count,
            "service": self.service,
            "status_type": self.status_type,
            "cause": self.cause,
            "eta": self.eta,
            "eta_raw": self.eta_raw,
            "matched_zone": self.matched_zone,
            "address_lines": self.address_lines or [],
            "record_text": self.record_text,
            "parser": self.parser,
        }


def strip_diacritics(value: str) -> str:
    """Remove diacritics for matching only."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize(value: object) -> str:
    """Normalize text for robust address matching."""
    text = strip_diacritics(str(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_eta(value: str | None) -> str | None:
    """Convert CMTEB date text to a Home Assistant parseable datetime string."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y %H:%M").isoformat(timespec="seconds")
    except ValueError:
        return value


def is_status_line(line: str) -> bool:
    """Return True when a cell line is a status/service label."""
    return normalize(line) in STATUS_VALUES


def service_from_status(line: str) -> str:
    """Extract affected service code from a status label."""
    normalized = normalize(line)
    services: list[str] = []
    if "acc" in normalized:
        services.append("ACC")
    if "inc" in normalized:
        services.append("ÎNC")
    return "+".join(services) if services else line.strip()


def cell_lines(cell) -> list[str]:
    """Return clean line-oriented text from one BeautifulSoup table cell."""
    for br in cell.find_all("br"):
        br.replace_with("\n")
    text = cell.get_text("\n", strip=True)
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def line_matches_address(line: str, street: str, block: str) -> bool:
    """Match a street/block inside a CMTEB grouped affected-zone line."""
    normalized = normalize(line)
    if normalize(street) not in normalized:
        return False
    if " bl " not in f" {normalized} ":
        return False
    block_token = re.escape(normalize(block))
    return re.search(rf"(^|[^a-z0-9]){block_token}($|[^a-z0-9])", normalized) is not None


def section_for_address(lines: list[str], index: int) -> list[str]:
    """Return the Punct Termic section containing an address line."""
    start = index
    for pos in range(index, -1, -1):
        if "punct termic" in normalize(lines[pos]):
            start = pos
            break

    end = len(lines)
    for pos in range(index + 1, len(lines)):
        if "punct termic" in normalize(lines[pos]):
            end = pos
            break

    return lines[start:end]


def parse_punct_section(section: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Parse one Punct Termic section from the affected-zone cell."""
    punct_termic = None
    affected_count = None

    for pos, line in enumerate(section):
        match = re.search(r"Punct\s+termic\s*:\s*(.*)", line, re.IGNORECASE)
        if not match:
            continue

        remainder = match.group(1).strip()
        if remainder:
            if "--" in remainder:
                punct_termic, affected_count = [part.strip() for part in remainder.split("--", 1)]
            else:
                punct_termic = remainder
        else:
            for candidate in section[pos + 1 :]:
                normalized = normalize(candidate)
                if not normalized or normalized.startswith("--") or "blocuri imobile" in normalized:
                    continue
                punct_termic = candidate.strip(" -–")
                break
        break

    if affected_count is None:
        for line in section:
            match = re.search(r"(?:--|[-–])?\s*(\d+\s+blocuri/imobile)", line, re.IGNORECASE)
            if match:
                affected_count = match.group(1).strip()
                break

    address_lines = [line for line in section if ADDRESS_PREFIX_RE.search(line)]
    return punct_termic, affected_count, address_lines


def row_sector(cells: list[list[str]]) -> str | None:
    """Extract sector from the row cells."""
    for lines in cells:
        text = " ".join(lines)
        normalized = normalize(text)
        if re.fullmatch(r"[1-6]", normalized):
            return normalized
        match = re.search(r"\bsector\s+([1-6])\b", normalized)
        if match:
            return match.group(1)
    return None


def row_status(cells: list[list[str]], street: str, block: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract status, service, cause and raw ETA from one table row."""
    status_type = None
    service = None
    cause = None
    eta_raw = None

    for lines in cells:
        for line in lines:
            if is_status_line(line):
                status_type = line.strip()
                service = service_from_status(line)
                break
        if status_type:
            break

    for lines in cells:
        for line in lines:
            match = ETA_RE.search(line)
            if match:
                eta_raw = match.group(0)
                break
        if eta_raw:
            break

    for lines in cells:
        if not lines:
            continue
        normalized_cell = normalize(" ".join(lines))
        if "punct termic" in normalized_cell:
            continue
        if any(line_matches_address(line, street, block) for line in lines):
            continue
        if any(is_status_line(line) for line in lines):
            continue
        if eta_raw and any(eta_raw in line for line in lines):
            continue
        if row_sector([lines]) is not None:
            continue
        if normalized_cell in {
            "zone afectate",
            "agentul termic afectat",
            "cauza descrierea interventiei",
            "data ora estimarii punerii in functiune",
            "sector",
        }:
            continue
        cause = " | ".join(lines)
        break

    return status_type, service, cause, eta_raw


def _punct_matches(configured_punct_termic: str | None, parsed_punct_termic: str | None) -> bool:
    """Return True if no punct termic was configured or it matches the parsed one."""
    if not configured_punct_termic:
        return True
    if not parsed_punct_termic:
        return False
    return normalize(configured_punct_termic) in normalize(parsed_punct_termic)


def parse_cmteb_status(html: str, street: str, block: str, punct_termic: str | None = None) -> CmtebStatus:
    """Parse CMTEB HTML for one address."""
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        raw_cells = row.find_all(["td", "th"])
        if not raw_cells:
            continue
        cells = [cell_lines(cell) for cell in raw_cells]
        for lines in cells:
            for line_index, line in enumerate(lines):
                if not line_matches_address(line, street, block):
                    continue
                section = section_for_address(lines, line_index)
                parsed_punct_termic, affected_count, address_lines = parse_punct_section(section)
                if not _punct_matches(punct_termic, parsed_punct_termic):
                    continue
                status_type, service, cause, eta_raw = row_status(cells, street, block)
                return CmtebStatus(
                    state="affected",
                    match_found=True,
                    sector=row_sector(cells),
                    punct_termic=parsed_punct_termic,
                    affected_count=affected_count,
                    service=service,
                    status_type=status_type,
                    cause=cause,
                    eta=parse_eta(eta_raw),
                    eta_raw=eta_raw,
                    matched_zone=line,
                    address_lines=address_lines,
                    record_text=" | ".join(section)[:1000],
                )
    return CmtebStatus(state="normal", match_found=False, parser="table")
