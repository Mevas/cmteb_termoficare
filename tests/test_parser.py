from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "cmteb_sample.html"
PARSER = ROOT / "custom_components" / "cmteb_termoficare" / "parser.py"
spec = importlib.util.spec_from_file_location("cmteb_parser", PARSER)
parser = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)
parse_cmteb_status = parser.parse_cmteb_status


def load_fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_avionului_grouped_row():
    result = parse_cmteb_status(load_fixture(), "Avionului", "15D")

    assert result.state == "affected"
    assert result.match_found is True
    assert result.sector == "1"
    assert result.punct_termic == "3 Aviatiei"
    assert result.affected_count == "27 blocuri/imobile"
    assert result.service == "ACC"
    assert result.status_type == "Deficienta ACC"
    assert result.eta == "2026-07-04T16:00:00"
    assert result.eta_raw == "04.07.2026 16:00"
    assert result.matched_zone == "• Str Avionului - bl. 16J, 15H, 15D, 15F, 15E"


def test_parse_avionului_with_matching_punct_termic():
    result = parse_cmteb_status(load_fixture(), "Avionului", "15D", "3 Aviatiei")

    assert result.state == "affected"
    assert result.match_found is True
    assert result.punct_termic == "3 Aviatiei"


def test_configured_punct_termic_must_match():
    result = parse_cmteb_status(load_fixture(), "Avionului", "15D", "2 Aviatiei")

    assert result.state == "normal"
    assert result.match_found is False


def test_parse_moinesti_split_punct_termic():
    result = parse_cmteb_status(load_fixture(), "Moinesti", "205")

    assert result.state == "affected"
    assert result.match_found is True
    assert result.sector == "6"
    assert result.punct_termic == "MILITARI - 3 Placare"
    assert result.affected_count == "12 blocuri/imobile"
    assert result.service == "ACC"
    assert result.status_type == "Deficienta ACC"
    assert result.eta == "2026-07-04T23:30:00"
    assert result.matched_zone == "• Str Moineşti - bl. 135, 136, 201, 202, 203, 204, 205, 206"


def test_block_token_must_match_exactly():
    result = parse_cmteb_status(load_fixture(), "Avionului", "15")


    assert result.state == "normal"
    assert result.match_found is False


def test_no_match_reports_normal():
    result = parse_cmteb_status(load_fixture(), "Imaginary Street", "4")

    assert result.state == "normal"
    assert result.match_found is False
