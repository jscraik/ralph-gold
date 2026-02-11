"""Persistence and schema validation for harness artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .atomic_file import atomic_write_json
from .harness import HARNESS_CASES_SCHEMA_V1, HARNESS_RUN_SCHEMA_V1


def validate_cases_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if payload.get("_schema") != HARNESS_CASES_SCHEMA_V1:
        errors.append(
            f"Invalid _schema for cases payload: {payload.get('_schema')!r}"
        )

    if not isinstance(payload.get("generated_at"), str):
        errors.append("cases payload missing generated_at string")

    if not isinstance(payload.get("source"), dict):
        errors.append("cases payload missing source object")

    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append("cases payload missing cases list")
        return errors

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"cases[{idx}] must be an object")
            continue
        for key in ("case_id", "task_id", "expected", "observed_history"):
            if key not in case:
                errors.append(f"cases[{idx}] missing {key}")

    return errors


def validate_run_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if payload.get("_schema") != HARNESS_RUN_SCHEMA_V1:
        errors.append(f"Invalid _schema for run payload: {payload.get('_schema')!r}")

    for key in ("run_id", "started_at", "completed_at"):
        if not isinstance(payload.get(key), str):
            errors.append(f"run payload missing {key} string")

    if not isinstance(payload.get("config"), dict):
        errors.append("run payload missing config object")

    if not isinstance(payload.get("dataset_ref"), dict):
        errors.append("run payload missing dataset_ref object")

    results = payload.get("results")
    if not isinstance(results, list):
        errors.append("run payload missing results list")
    else:
        for idx, result in enumerate(results):
            if not isinstance(result, dict):
                errors.append(f"results[{idx}] must be an object")
                continue
            for key in ("case_id", "status", "failure_category", "metrics"):
                if key not in result:
                    errors.append(f"results[{idx}] missing {key}")

    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, dict):
        errors.append("run payload missing aggregate object")
    elif "quality_score" not in aggregate:
        errors.append("run payload aggregate missing quality_score")

    return errors


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object at {path}")
    return payload


def load_cases(path: Path) -> Dict[str, Any]:
    payload = _read_json(path)
    errors = validate_cases_payload(payload)
    if errors:
        raise ValueError(f"Invalid harness cases payload: {'; '.join(errors)}")
    return payload


def save_cases(path: Path, payload: Dict[str, Any]) -> None:
    errors = validate_cases_payload(payload)
    if errors:
        raise ValueError(f"Invalid harness cases payload: {'; '.join(errors)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def load_run(path: Path) -> Dict[str, Any]:
    payload = _read_json(path)
    errors = validate_run_payload(payload)
    if errors:
        raise ValueError(f"Invalid harness run payload: {'; '.join(errors)}")
    return payload


def save_run(path: Path, payload: Dict[str, Any]) -> None:
    errors = validate_run_payload(payload)
    if errors:
        raise ValueError(f"Invalid harness run payload: {'; '.join(errors)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)

