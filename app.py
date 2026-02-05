#!/usr/bin/env python3
"""
SDRF Validator API

A FastAPI service for validating SDRF (Sample and Data Relationship Format) files
against proteomics metadata standards.
"""

import gzip
import io
import logging
import os
import tempfile
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sdrf_pipelines import __version__ as sdrf_version
from sdrf_pipelines.ols.ols import OLS_AVAILABLE
from sdrf_pipelines.sdrf.schemas import SchemaRegistry, SchemaValidator
from sdrf_pipelines.sdrf.sdrf import read_sdrf

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Deployment root path (for ingress sub-paths)
ROOT_PATH = os.getenv("ROOT_PATH", "")

# Initialize FastAPI app
app = FastAPI(
    title="SDRF Validator API",
    description=(
        "API for validating SDRF (Sample and Data Relationship Format) files "
        "against proteomics metadata standards. Supports multiple validation templates "
        "including human, vertebrates, plants, cell-lines, and more."
    ),
    version="1.0.0",
    root_path=ROOT_PATH,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize schema registry
registry = SchemaRegistry()

# Maximum file size (10MB default)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))


# Pydantic models for API responses
class ValidationError(BaseModel):
    """A single validation error or warning."""

    type: str = Field(description="Error type: ERROR or WARNING")
    message: str = Field(description="Error message")
    row: Optional[int] = Field(default=None, description="Row number (1-based)")
    column: Optional[str] = Field(default=None, description="Column name")


class ValidationResult(BaseModel):
    """Result of SDRF file validation."""

    valid: bool = Field(description="Whether the file passed validation (no errors)")
    errors: list[ValidationError] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: list[ValidationError] = Field(
        default_factory=list, description="List of validation warnings"
    )
    error_count: int = Field(description="Total number of errors")
    warning_count: int = Field(description="Total number of warnings")
    templates_used: list[str] = Field(
        description="Templates used for validation"
    )
    sdrf_pipelines_version: str = Field(
        description="Version of sdrf-pipelines library"
    )


class TemplateInfo(BaseModel):
    """Information about a validation template."""

    name: str = Field(description="Template name")
    description: Optional[str] = Field(
        default=None, description="Template description"
    )
    version: str = Field(default="1.0.0", description="Template version")


class TemplatesResponse(BaseModel):
    """Response containing available templates."""

    templates: list[TemplateInfo] = Field(description="List of available templates")
    legacy_mappings: dict[str, str] = Field(
        description="Mapping of legacy template names to current names"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Service status")
    sdrf_pipelines_version: str = Field(
        description="Version of sdrf-pipelines library"
    )
    ontology_validation_available: bool = Field(
        description="Whether ontology validation is available"
    )


def decompress_if_gzipped(content: bytes, filename: str) -> str:
    """Decompress content if it's gzipped, otherwise decode as text."""
    if filename.endswith(".gz") or content[:2] == b"\x1f\x8b":
        try:
            decompressed = gzip.decompress(content)
            return decompressed.decode("utf-8")
        except gzip.BadGzipFile:
            # Not actually gzipped, try to decode as text
            pass
    return content.decode("utf-8")


def validate_sdrf_content(
    content: str,
    templates: list[str],
    skip_ontology: bool = False,
    use_ols_cache_only: bool = True,
) -> ValidationResult:
    """
    Validate SDRF content against one or more templates.

    Args:
        content: SDRF file content as string
        templates: List of template names to validate against
        skip_ontology: Whether to skip ontology validation
        use_ols_cache_only: Whether to use only OLS cache for validation

    Returns:
        ValidationResult with errors and warnings
    """
    # Check if ontology validation is available
    actual_skip_ontology = skip_ontology
    if not skip_ontology and not OLS_AVAILABLE:
        logger.warning(
            "Ontology validation requested but dependencies not available. "
            "Install with: pip install sdrf-pipelines[ontology]"
        )
        actual_skip_ontology = True

    # Read SDRF from string content
    try:
        sdrf_df = read_sdrf(io.StringIO(content))
    except Exception as e:
        logger.error(f"Failed to parse SDRF file: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse SDRF file: {str(e)}",
        )

    all_errors = []
    all_warnings = []

    # Validate against each template
    for template in templates:
        # Check if template exists (considering legacy mappings)
        schema = registry.get_schema(template)
        if schema is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown template: {template}. Use /templates to see available templates.",
            )

        validator = SchemaValidator(registry)
        try:
            errors = validator.validate(
                sdrf_df,
                template,
                use_ols_cache_only=use_ols_cache_only,
                skip_ontology=actual_skip_ontology,
            )
        except Exception as e:
            logger.error(f"Validation failed for template {template}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Validation failed for template {template}: {str(e)}",
            )

        for error in errors:
            validation_error = ValidationError(
                type="ERROR" if error.error_type == logging.ERROR else "WARNING",
                message=error.message,
                row=getattr(error, "row", None),
                column=getattr(error, "column", None),
            )
            if error.error_type == logging.ERROR:
                all_errors.append(validation_error)
            else:
                all_warnings.append(validation_error)

    # Deduplicate errors and warnings
    seen_errors = set()
    unique_errors = []
    for err in all_errors:
        key = (err.type, err.message, err.row, err.column)
        if key not in seen_errors:
            seen_errors.add(key)
            unique_errors.append(err)

    seen_warnings = set()
    unique_warnings = []
    for warn in all_warnings:
        key = (warn.type, warn.message, warn.row, warn.column)
        if key not in seen_warnings:
            seen_warnings.add(key)
            unique_warnings.append(warn)

    return ValidationResult(
        valid=len(unique_errors) == 0,
        errors=unique_errors,
        warnings=unique_warnings,
        error_count=len(unique_errors),
        warning_count=len(unique_warnings),
        templates_used=templates,
        sdrf_pipelines_version=sdrf_version,
    )


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""
    return JSONResponse(
        content={
            "message": "SDRF Validator API",
            "docs": "/docs",
            "health": "/health",
        }
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the service status and version information.
    """
    return HealthResponse(
        status="healthy",
        sdrf_pipelines_version=sdrf_version,
        ontology_validation_available=OLS_AVAILABLE,
    )


@app.get("/templates", response_model=TemplatesResponse, tags=["Templates"])
async def get_templates():
    """
    Get available validation templates.

    Returns a list of all available templates that can be used for validation,
    along with legacy name mappings for backwards compatibility.
    """
    templates = []
    for name in registry.get_schema_names():
        schema = registry.get_schema(name)
        templates.append(
            TemplateInfo(
                name=name,
                description=schema.description if schema else None,
                version=schema.version if schema else "1.0.0",
            )
        )

    return TemplatesResponse(
        templates=sorted(templates, key=lambda x: x.name),
        legacy_mappings=SchemaRegistry.LEGACY_NAME_MAPPING,
    )


@app.post("/validate", response_model=ValidationResult, tags=["Validation"])
async def validate_sdrf(
    file: UploadFile = File(..., description="SDRF file to validate (can be gzipped)"),
    template: list[str] = Query(
        default=["default"],
        description="Template(s) to validate against. Can specify multiple.",
    ),
    skip_ontology: bool = Query(
        default=False,
        description="Skip ontology term validation",
    ),
    use_ols_cache_only: bool = Query(
        default=True,
        description="Use only OLS cache for ontology validation (faster, offline)",
    ),
):
    """
    Validate an SDRF file against one or more templates.

    Upload an SDRF file (optionally gzipped) and validate it against the specified
    template(s). The validation checks:

    - Required columns are present
    - Column values match expected formats
    - Ontology terms are valid (if enabled)
    - Column order is correct
    - No duplicate entries where uniqueness is required

    **Templates:**
    - `default` or `ms-proteomics`: Standard mass spectrometry proteomics
    - `human`: Human-specific fields
    - `vertebrates`: Vertebrate organisms
    - `invertebrates`: Invertebrate organisms
    - `plants`: Plant-specific fields
    - `cell-lines`: Cell line experiments

    **File formats:**
    - Plain TSV (.tsv, .txt)
    - Gzipped TSV (.tsv.gz, .txt.gz)
    """
    # Validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024:.1f}MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded",
        )

    # Decompress if needed
    try:
        text_content = decompress_if_gzipped(content, file.filename or "")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to decode file as UTF-8: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process file: {str(e)}",
        )

    # Validate
    result = validate_sdrf_content(
        content=text_content,
        templates=template,
        skip_ontology=skip_ontology,
        use_ols_cache_only=use_ols_cache_only,
    )

    return result


@app.post("/validate/text", response_model=ValidationResult, tags=["Validation"])
async def validate_sdrf_text(
    content: str = Query(..., description="SDRF content as text"),
    template: list[str] = Query(
        default=["default"],
        description="Template(s) to validate against. Can specify multiple.",
    ),
    skip_ontology: bool = Query(
        default=False,
        description="Skip ontology term validation",
    ),
    use_ols_cache_only: bool = Query(
        default=True,
        description="Use only OLS cache for ontology validation",
    ),
):
    """
    Validate SDRF content provided as text.

    Alternative to file upload - provide the SDRF content directly as a query parameter.
    Useful for programmatic validation of small files.
    """
    if not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Empty content provided",
        )

    result = validate_sdrf_content(
        content=content,
        templates=template,
        skip_ontology=skip_ontology,
        use_ols_cache_only=use_ols_cache_only,
    )

    return result


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    workers = int(os.getenv("WORKERS", 2))

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        workers=workers,
        log_level=LOG_LEVEL.lower(),
    )
