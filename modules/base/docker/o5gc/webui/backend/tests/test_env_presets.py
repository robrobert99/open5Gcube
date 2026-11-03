import os
from pathlib import Path

import pytest


@pytest.fixture
def presets_client(tmp_path, client):
    # Minimal modules/<module>/stacks/<stack> layout, as used by get_stacks()
    modules_dir = tmp_path / "modules"
    for module_name, stack_name in [("mod_a", "stack_a1"), ("mod_a", "stack_a2"), ("mod_b", "stack_b1")]:
        (modules_dir / module_name / "stacks" / stack_name).mkdir(parents=True)

    client.application.config["MODULES_DIR"] = modules_dir
    client.application.config["ENV_PRESETS_DIR"] = tmp_path / "var" / "env-presets"
    return client


def preset_path(client, module_name, stack_name, preset_name) -> Path:
    return client.application.config["ENV_PRESETS_DIR"] / module_name / stack_name / f"{preset_name}.env"


def test_get_env_presets_lists_all_stacks_without_presets(presets_client):
    response = presets_client.get('/api/env-presets')

    assert response.status_code == 200
    assert response.json == {"stacks": [
        {"module_name": "mod_a", "stack_name": "stack_a1", "presets": []},
        {"module_name": "mod_a", "stack_name": "stack_a2", "presets": []},
        {"module_name": "mod_b", "stack_name": "stack_b1", "presets": []},
    ]}


def test_get_env_presets_lists_sorted_presets(presets_client):
    presets_client.put('/api/stack/stack_a2/env-presets/zeta', data="A=1\n")
    presets_client.put('/api/stack/stack_a2/env-presets/alpha', data="B=2\n")
    # Files that are not presets are ignored
    (preset_path(presets_client, "mod_a", "stack_a2", "x").parent / "notes.txt").write_text("x")

    response = presets_client.get('/api/env-presets')

    assert response.status_code == 200
    stacks = {s["stack_name"]: s for s in response.json["stacks"]}
    assert stacks["stack_a2"]["presets"] == ["alpha", "zeta"]
    assert stacks["stack_a1"]["presets"] == []


def test_env_preset_save_get_overwrite_delete_roundtrip(presets_client):
    content = "# Comment\nNSSAI_SD=0\nFIVEG_CIPHERING_ORDER=\"NEA0\"\n"

    response = presets_client.put('/api/stack/stack_b1/env-presets/nea0-sd0', data=content)
    assert response.status_code == 201
    assert preset_path(presets_client, "mod_b", "stack_b1", "nea0-sd0").read_text() == content

    response = presets_client.get('/api/stack/stack_b1/env-presets/nea0-sd0')
    assert response.status_code == 200
    assert response.content_type.startswith("text/x-sh")
    assert response.get_data(as_text=True) == content

    response = presets_client.put('/api/stack/stack_b1/env-presets/nea0-sd0', data="NSSAI_SD=1\n")
    assert response.status_code == 200
    assert presets_client.get('/api/stack/stack_b1/env-presets/nea0-sd0').get_data(as_text=True) == "NSSAI_SD=1\n"

    response = presets_client.delete('/api/stack/stack_b1/env-presets/nea0-sd0')
    assert response.status_code == 200
    assert not preset_path(presets_client, "mod_b", "stack_b1", "nea0-sd0").exists()

    assert presets_client.get('/api/stack/stack_b1/env-presets/nea0-sd0').status_code == 404
    assert presets_client.delete('/api/stack/stack_b1/env-presets/nea0-sd0').status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_env_preset_unknown_stack(presets_client, method):
    response = getattr(presets_client, method)('/api/stack/no_such_stack/env-presets/name', data="A=1\n")
    assert response.status_code == 404


@pytest.mark.parametrize("name", ["..", ".", "a b", "a;b", "x" * 65, "%2e%2e", "..%2Fx", "a%2Fb"])
@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_env_preset_invalid_names(presets_client, tmp_path, method, name):
    response = getattr(presets_client, method)(f'/api/stack/stack_a1/env-presets/{name}', data="A=1\n")
    # Names with an encoded slash are not matched by the route at all (404), all others are rejected (400)
    assert response.status_code in (400, 404)
    assert response.status_code == 400 or "%2F" in name
    # Nothing was written anywhere below tmp_path except the (possibly empty) presets dir
    assert not any(p.is_file() for p in (tmp_path / "var").rglob("*"))


def test_env_preset_max_length_name_is_valid(presets_client):
    assert presets_client.put('/api/stack/stack_a1/env-presets/' + "x" * 64, data="A=1\n").status_code == 201


def test_env_preset_put_chowns_to_host_user(presets_client, monkeypatch):
    chowned = []
    monkeypatch.setattr(os, "chown", lambda path, uid, gid: chowned.append((Path(path), uid, gid)))
    presets_client.application.config["HOST_USER_GROUP_ID"] = "1234:5678"

    assert presets_client.put('/api/stack/stack_a1/env-presets/p1', data="A=1\n").status_code == 201

    presets_dir = presets_client.application.config["ENV_PRESETS_DIR"]
    assert (presets_dir / "mod_a" / "stack_a1" / "p1.env", 1234, 5678) in chowned
    assert (presets_dir / "mod_a" / "stack_a1", 1234, 5678) in chowned
    assert (presets_dir / "mod_a", 1234, 5678) in chowned


@pytest.mark.parametrize("host_user_group_id", [None, "", "garbage", "1:x"])
def test_env_preset_put_without_valid_host_user_skips_chown(presets_client, monkeypatch, host_user_group_id):
    chowned = []
    monkeypatch.setattr(os, "chown", lambda path, uid, gid: chowned.append(path))
    presets_client.application.config["HOST_USER_GROUP_ID"] = host_user_group_id

    assert presets_client.put('/api/stack/stack_a1/env-presets/p1', data="A=1\n").status_code == 201
    assert chowned == []
