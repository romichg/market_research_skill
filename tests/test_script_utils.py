from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_UTILS = ROOT / "market-research" / "shared" / "scripts" / "script_utils.py"


def test_script_utils_holds_common_json_symbol_date_and_checksum_primitives():
    text = SCRIPT_UTILS.read_text(encoding="utf-8")

    for name in [
        "def normalize_symbol(",
        "def validate_as_of(",
        "def read_json(",
        "def write_json(",
        "def sha256_file(",
    ]:
        assert name in text


def test_procedural_helper_uses_shared_script_primitives():
    text = (ROOT / "market-research" / "shared" / "scripts" / "procedural_source_helper.py").read_text(encoding="utf-8")

    assert "from script_utils import" in text
    for duplicate in [
        "def normalize_symbol(",
        "def validate_as_of(",
        "def read_json(",
        "def write_json(",
        "def sha256_file(",
    ]:
        assert duplicate not in text


def test_research_loop_uses_shared_script_primitives():
    text = (ROOT / "market-research" / "batch-supervisor" / "scripts" / "research_loop.py").read_text(encoding="utf-8")

    assert "from script_utils import" in text
    for duplicate in [
        "def normalize_symbol(",
        "def validate_as_of(",
        "def read_json(",
        "def write_json(",
    ]:
        assert duplicate not in text


def test_validator_uses_shared_json_primitives():
    text = (ROOT / "market-research" / "shared" / "scripts" / "validate_market_research.py").read_text(encoding="utf-8")

    assert "from script_utils import" in text
    assert "def read_json(" not in text
    assert "def write_json(" not in text
