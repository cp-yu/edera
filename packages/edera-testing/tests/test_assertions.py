from __future__ import annotations

from types import SimpleNamespace

import pytest

from edera_testing import assert_handler_signature, assert_manifest_valid


def test_assert_handler_signature_valid() -> None:
    def run(ctx):
        return ctx

    assert_handler_signature(SimpleNamespace(run=run))


def test_assert_handler_signature_invalid() -> None:
    def run(ctx, extra):
        return ctx, extra

    with pytest.raises(AssertionError):
        assert_handler_signature(SimpleNamespace(run=run))


def test_assert_manifest_valid_complete(tmp_path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("name: demo\nversion: 0.1.0\nhandlers: []\n")

    assert_manifest_valid(manifest)


def test_assert_manifest_valid_missing_fields(tmp_path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("name: demo\nhandlers: []\n")

    with pytest.raises(AssertionError):
        assert_manifest_valid(manifest)
