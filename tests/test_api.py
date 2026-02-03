"""Tests for SDRF Validator API."""

import io

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_check():
    """Test health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "sdrf_pipelines_version" in data
    assert "ontology_validation_available" in data


def test_get_templates():
    """Test templates endpoint returns available templates."""
    response = client.get("/templates")
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert "legacy_mappings" in data
    assert len(data["templates"]) > 0

    # Check that some expected templates are present
    template_names = [t["name"] for t in data["templates"]]
    # At least some templates should be available
    assert len(template_names) > 0


def test_validate_empty_file():
    """Test validation fails for empty file."""
    response = client.post(
        "/validate",
        files={"file": ("test.sdrf.tsv", b"", "text/tab-separated-values")},
    )
    assert response.status_code == 400


def test_validate_invalid_template():
    """Test validation fails for unknown template."""
    valid_sdrf = b"source name\tcharacteristics[organism]\nassay_1\thomo sapiens\n"
    response = client.post(
        "/validate",
        files={"file": ("test.sdrf.tsv", valid_sdrf, "text/tab-separated-values")},
        params={"template": "nonexistent_template_xyz"},
    )
    assert response.status_code == 400
    assert "Unknown template" in response.json()["detail"]


def test_validate_minimal_sdrf():
    """Test validation of a minimal SDRF file."""
    # A minimal valid SDRF with required columns
    sdrf_content = b"""source name\tcharacteristics[organism]\tcharacteristics[organism part]\tassay name\tcomment[data file]\tcomment[fraction identifier]\tcomment[label]\tcomment[instrument]
sample_1\tHomo sapiens\tbrain\trun_1\tfile1.raw\t1\tlabel free sample\tQ Exactive
"""
    response = client.post(
        "/validate",
        files={"file": ("test.sdrf.tsv", sdrf_content, "text/tab-separated-values")},
        params={"template": "default", "skip_ontology": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "errors" in data
    assert "warnings" in data
    assert "templates_used" in data
    assert data["templates_used"] == ["default"]


def test_validate_text_endpoint():
    """Test validation via text endpoint."""
    sdrf_content = """source name\tcharacteristics[organism]\tassay name
sample_1\tHomo sapiens\trun_1
"""
    response = client.post(
        "/validate/text",
        params={
            "content": sdrf_content,
            "template": "default",
            "skip_ontology": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data


def test_validate_text_empty():
    """Test validation fails for empty text."""
    response = client.post(
        "/validate/text",
        params={"content": "", "template": "default"},
    )
    assert response.status_code == 400


def test_root_endpoint():
    """Test root endpoint redirects to docs info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
