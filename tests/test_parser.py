from pathlib import Path
import importlib.util
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "opriri-detaliate.json"
PARSER = ROOT / "custom_components" / "cmteb_termoficare" / "parser.py"
spec = importlib.util.spec_from_file_location("cmteb_parser", PARSER)
parser = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)
parse_cmteb_status = parser.parse_cmteb_status


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_barbu_vacarescu_deficiency():
    result = parse_cmteb_status(load_fixture(), "Barbu Vacarescu", "1")

    assert result.state == "affected"
    assert result.match_found is True
    assert result.sector == "2"
    assert result.punct_termic == "Barbu Vacarescu"
    assert result.affected_count == "6 blocuri/imobile"
    assert result.service == "ACC"
    assert result.status_type == "Deficienta ACC"
    assert result.cause == "Lipsa parametri pentru livrare apă caldă de consum"
    assert result.started == "2026-10-24T20:00:00+03:00"
    assert result.eta == "2026-10-26T23:30:00+02:00"
    assert result.matched_zone == "Str Barbu Văcărescu - bl.1,2; 7"
    assert result.address_lines == ["Str Dinu Vintilă - bl.3, 4, 5", "Str Barbu Văcărescu - bl.1,2; 7"]
    assert result.source_generated == "2026-10-26T00:51:01.620Z"


def test_parse_with_matching_punct_termic():
    result = parse_cmteb_status(load_fixture(), "Barbu Vacarescu", "7", "Barbu Vacarescu")

    assert result.state == "affected"
    assert result.punct_termic == "Barbu Vacarescu"


def test_configured_punct_termic_must_match():
    result = parse_cmteb_status(load_fixture(), "Barbu Vacarescu", "1", "Judetului")

    assert result.state == "normal"
    assert result.match_found is False


def test_heating_outage_service_label():
    result = parse_cmteb_status(load_fixture(), "Pantelimon", "51")

    assert result.state == "affected"
    assert result.punct_termic == "4 Pantelimon"
    assert result.service == "ÎNC"
    assert result.status_type == "Oprire INC"


def test_block_token_must_match_exactly():
    assert parse_cmteb_status(load_fixture(), "Barbu Vacarescu", "3").state == "normal"
    assert parse_cmteb_status(load_fixture(), "Lacul Tei", "19").state == "normal"
    assert parse_cmteb_status(load_fixture(), "Lacul Tei", "19NOU").state == "affected"


def test_staircase_number_is_not_a_block():
    assert parse_cmteb_status(load_fixture(), "Ilia", "2").state == "normal"
    assert parse_cmteb_status(load_fixture(), "Ilia", "57").state == "affected"


def test_empty_details_cover_whole_street():
    result = parse_cmteb_status(load_fixture(), "Garii de Nord", "99")

    assert result.state == "affected"
    assert result.matched_zone == "Str Gării de Nord"


def test_no_match_reports_normal():
    result = parse_cmteb_status(load_fixture(), "Imaginary Street", "4")

    assert result.state == "normal"
    assert result.match_found is False
    assert result.source_generated == "2026-10-26T00:51:01.620Z"


def test_unknown_feed_shape_raises():
    with pytest.raises(ValueError):
        parse_cmteb_status({"versiune": 2}, "Barbu Vacarescu", "1")
