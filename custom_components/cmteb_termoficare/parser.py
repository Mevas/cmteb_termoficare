"""Parsing helpers for the CMTEB Termoficare outage feed."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
import unicodedata

# Detail qualifiers that carry numbers which are not block tokens, e.g. "57 sc.2".
QUALIFIER_RE = re.compile(r"\b(sc|scara|et|ap)\s+[a-z0-9]+\b")


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
    started: str | None = None
    eta: str | None = None
    eta_raw: str | None = None
    matched_zone: str | None = None
    address_lines: list[str] | None = None
    record_text: str | None = None
    source_generated: str | None = None
    parser: str = "json"

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
            "started": self.started,
            "eta": self.eta,
            "eta_raw": self.eta_raw,
            "matched_zone": self.matched_zone,
            "address_lines": self.address_lines or [],
            "record_text": self.record_text,
            "source_generated": self.source_generated,
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


def service_from_agent(agent: str | None) -> str | None:
    """Convert the feed agent code (ACC, INC, ACC+INC) to the service label."""
    if not agent:
        return None
    return "+".join("ÎNC" if part.strip().upper() == "INC" else part.strip() for part in agent.split("+"))


def street_matches(strada: str, street: str) -> bool:
    """Match the configured street inside a feed street such as 'Str Barbu Văcărescu'."""
    return f" {normalize(street)} " in f" {normalize(strada)} "


def details_match_block(detalii: str, block: str) -> bool:
    """Match a block token inside feed details such as 'bl.1,2; 7'.

    Empty details mean the whole street is listed.
    """
    details = QUALIFIER_RE.sub(" ", normalize(detalii))
    if not details:
        return True
    block_token = re.escape(normalize(block))
    return re.search(rf"(^|[^a-z0-9]){block_token}($|[^a-z0-9])", details) is not None


def address_line(address: dict[str, Any]) -> str:
    """Format one feed address like the old CMTEB listing."""
    strada = str(address.get("strada") or "").strip()
    detalii = str(address.get("detalii") or "").strip()
    return f"{strada} - {detalii}" if detalii else strada


def _punct_matches(configured_punct_termic: str | None, parsed_punct_termic: str | None) -> bool:
    """Return True if no punct termic was configured or it matches the parsed one."""
    if not configured_punct_termic:
        return True
    if not parsed_punct_termic:
        return False
    return normalize(configured_punct_termic) in normalize(parsed_punct_termic)


def parse_cmteb_status(data: dict[str, Any], street: str, block: str, punct_termic: str | None = None) -> CmtebStatus:
    """Parse the CMTEB opriri-detaliate.json feed for one address."""
    outages = data.get("avarii") if isinstance(data, dict) else None
    if not isinstance(outages, list):
        raise ValueError("CMTEB feed has no 'avarii' list; the feed format may have changed")
    generated = data.get("generat")

    for outage in outages:
        for point in outage.get("puncteTermice") or []:
            name = point.get("denumire")
            if not _punct_matches(punct_termic, name):
                continue
            addresses = point.get("adrese") or []
            for address in addresses:
                if not street_matches(address.get("strada") or "", street):
                    continue
                if not details_match_block(address.get("detalii") or "", block):
                    continue
                address_lines = [address_line(item) for item in addresses]
                imobile = point.get("imobile")
                estimare = outage.get("estimare")
                sector = outage.get("sector")
                return CmtebStatus(
                    state="affected",
                    match_found=True,
                    sector=str(sector) if sector is not None else None,
                    punct_termic=name,
                    affected_count=f"{imobile} blocuri/imobile" if imobile is not None else None,
                    service=service_from_agent(outage.get("agent")),
                    status_type=outage.get("eticheta"),
                    cause=outage.get("cauza"),
                    started=outage.get("inceput"),
                    eta=estimare,
                    eta_raw=estimare,
                    matched_zone=address_line(address),
                    address_lines=address_lines,
                    record_text=" | ".join([f"Punct termic: {name}", *address_lines])[:1000],
                    source_generated=generated,
                )
    return CmtebStatus(state="normal", match_found=False, source_generated=generated)
