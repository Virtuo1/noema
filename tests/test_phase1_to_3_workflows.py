"""End-to-end tests for Phase 1 core prototype, Phase 2 retrieval/provenance, and Phase 3 temporal/ownership."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from noema.fixtures.synthetic_dataset import RETRIEVAL_EVAL_CASES, SYNTHETIC_CONVERSATIONS
from noema.main import create_app
from noema.persistence.db import init_db


def _make_client(tmp_path: Path) -> TestClient:
    db_file = tmp_path / "noema_e2e.db"
    db_url = f"sqlite:///{db_file}"
    os.environ["NOEMA_DATABASE_URL"] = db_url
    os.environ["NOEMA_EXPORT_DIR"] = str(tmp_path / "exports")
    os.environ["NOEMA_SECRETS_FILE"] = str(tmp_path / "secrets.json")
    init_db(db_url)
    app = create_app()
    return TestClient(app)


def test_phase1_worked_example_and_acceptance_criteria(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    # 1. Create a conversation and exchange messages
    conv_res = client.post("/api/v1/conversations", json={"title": "Learning theory"})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Turn 1: Ask about backpropagation and chain rule with Idempotency-Key
    turn1_res = client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        headers={"Idempotency-Key": "idem-turn-1"},
        json={
            "content": "How does backpropagation use the chain rule?",
            "context_mode": "personalized",
        },
    )
    assert turn1_res.status_code == 202
    turn1_data = turn1_res.json()
    assert turn1_data["status"] == "succeeded"
    assert turn1_data["assistant_message_id"] is not None

    # Verify idempotency returns same turn without duplicating message
    dup_res = client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        headers={"Idempotency-Key": "idem-turn-1"},
        json={
            "content": "How does backpropagation use the chain rule?",
            "context_mode": "personalized",
        },
    )
    assert dup_res.status_code == 202
    assert dup_res.json()["turn_id"] == turn1_data["turn_id"]

    # Verify SSE stream works
    stream_res = client.get(turn1_data["stream_url"])
    assert stream_res.status_code == 200
    assert "event: turn.completed" in stream_res.text

    # 2. User continues conversation and attaches #aha inline
    turn2_res = client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={
            "content": "I think I get it: the chain rule lets the error signal flow backward through the network. #aha",
            "context_mode": "personalized",
        },
    )
    assert turn2_res.status_code == 202
    turn2_data = turn2_res.json()
    user_msg_2_id = turn2_data["user_message"]["id"]
    assert len(turn2_data["applied_annotations"]) == 1
    assert turn2_data["applied_annotations"][0]["tag"] == "aha"
    assert turn2_data["applied_annotations"][0]["origin"] == "user_explicit"

    # Drain background jobs to ensure extraction & discovery completed
    client.post("/api/v1/worker/drain")

    # 3. Inspect graph: Backpropagation, Chain rule, and Hebbian learning should exist
    graph_res = client.get("/api/v1/knowledge/graph?layers=user,world,suggested")
    assert graph_res.status_code == 200
    graph = graph_res.json()
    nodes_by_label = {n["label"]: n for n in graph["nodes"]}
    assert "Backpropagation" in nodes_by_label
    assert "Chain rule" in nodes_by_label
    assert "Hebbian learning" in nodes_by_label

    bp_node = nodes_by_label["Backpropagation"]
    hb_node = nodes_by_label["Hebbian learning"]
    assert bp_node["signals"]["self_assessment"] == "self_reports_understanding"
    assert bp_node["signals"]["demonstration_status"] == "none"
    # Hebbian learning must NOT be marked understood
    assert hb_node["signals"]["self_assessment"] == "unknown"

    # Check edges: provisional world claim (Backpropagation -> Chain rule) and pending suggestion (Backpropagation -> Hebbian learning)
    world_edges = [e for e in graph["edges"] if e["layer"] == "world"]
    suggested_edges = [e for e in graph["edges"] if e["layer"] == "suggested"]
    user_edges = [e for e in graph["edges"] if e["layer"] == "user_established"]

    assert len(world_edges) >= 1
    assert world_edges[0]["status"] == "provisional"
    assert len(suggested_edges) >= 1
    assert suggested_edges[0]["status"] == "pending"
    assert len(user_edges) == 0

    # Record timestamp BEFORE accepting the suggestion for Phase 3 historical `as_of` test
    time.sleep(0.01)
    before_accept_ts = client.get("/api/v1/knowledge/graph").json()["as_of"]
    time.sleep(0.01)

    # 4. Accept the pending suggestion (Backpropagation contrasts_with_learning Hebbian learning)
    suggestion_id = suggested_edges[0]["suggestion_id"]
    accept_res = client.post(f"/api/v1/suggestions/{suggestion_id}/accept")
    assert accept_res.status_code == 200
    rel_data = accept_res.json()
    assert rel_data["origin"] == "accepted_suggestion"
    assert rel_data["source_suggestion_id"] == suggestion_id

    # Verify graph after acceptance: now has user_established edge, and Hebbian learning is STILL not marked understood!
    graph_after = client.get("/api/v1/knowledge/graph?layers=user,world,suggested").json()
    user_edges_after = [
        e for e in graph_after["edges"] if e["layer"] == "user_established"
    ]
    assert len(user_edges_after) == 1
    hb_after = {n["label"]: n for n in graph_after["nodes"]}["Hebbian learning"]
    assert hb_after["signals"]["self_assessment"] == "unknown"
    assert hb_after["signals"]["demonstration_status"] == "none"

    # Verify historical `as_of` graph before acceptance still shows suggestion pending and 0 user edges!
    hist_graph = client.get(
        f"/api/v1/knowledge/graph?layers=user,world,suggested&as_of={before_accept_ts}"
    ).json()
    assert len([e for e in hist_graph["edges"] if e["layer"] == "user_established"]) == 0
    assert len([e for e in hist_graph["edges"] if e["layer"] == "suggested"]) >= 1

    # 5. Subsequent conversation retrieves prior passage and links to its source
    conv2_res = client.post(
        "/api/v1/conversations", json={"title": "Comparing learning rules"}
    )
    conv2_id = conv2_res.json()["id"]
    turn_later = client.post(
        f"/api/v1/conversations/{conv2_id}/turns",
        json={
            "content": "How does the chain rule in backpropagation compare to local Hebbian updates?",
            "context_mode": "personalized",
        },
    )
    assert turn_later.status_code == 202
    later_asst = turn_later.json()["assistant_message"]
    assert later_asst is not None
    assert len(later_asst["sources"]) >= 1
    assert later_asst["sources"][0]["conversation_id"] == conv_id

    # 6. Verify non-monotonic revision in timeline: user adds #confused annotation to message, then undoes it
    conf_res = client.post(
        f"/api/v1/messages/{user_msg_2_id}/annotations",
        json={
            "tag": "confused",
            "span": {"start_offset": 0, "end_offset": 20, "offset_unit": "unicode_codepoint"},
        },
    )
    assert conf_res.status_code == 201
    conf_ann_id = conf_res.json()["id"]

    bp_detail = client.get(f"/api/v1/concepts/{bp_node['id']}").json()
    assert bp_detail["signals"]["self_assessment"] == "confused"

    # Undo the #confused annotation; self_assessment reverts to self_reports_understanding from #aha
    del_res = client.delete(f"/api/v1/annotations/{conf_ann_id}")
    assert del_res.status_code == 204
    bp_detail_reverted = client.get(f"/api/v1/concepts/{bp_node['id']}").json()
    assert bp_detail_reverted["signals"]["self_assessment"] == "self_reports_understanding"

    # Timeline preserves all revisions
    events_res = client.get(f"/api/v1/concepts/{bp_node['id']}/history")
    assert events_res.status_code == 200
    event_types = [e["event_type"] for e in events_res.json()["items"]]
    assert "self_assessment_changed" in event_types


def test_separate_chat_and_extraction_failure_modes(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    conv_id = client.post("/api/v1/conversations", json={"title": "Resilience test"}).json()["id"]

    # 1. Simulate chat provider failure: user message is preserved, turn is failed, retry recovers
    fail_turn = client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"content": "Explain backpropagation [simulate_chat_error]"},
    )
    assert fail_turn.status_code == 202
    fail_data = fail_turn.json()
    assert fail_data["status"] == "failed"
    user_msg_id = fail_data["user_message"]["id"]

    # User message is safely stored in history
    msgs = client.get(f"/api/v1/conversations/{conv_id}/messages").json()["items"]
    assert any(m["id"] == user_msg_id for m in msgs)

    # Retry turn succeeds without duplicating the user message
    retry_res = client.post(f"/api/v1/turns/{fail_data['turn_id']}/retry")
    assert retry_res.status_code == 202
    assert retry_res.json()["status"] == "succeeded"
    msgs_after = client.get(f"/api/v1/conversations/{conv_id}/messages").json()["items"]
    user_msgs = [m for m in msgs_after if m["role"] == "user"]
    assert len(user_msgs) == 1

    # 2. Simulate extraction failure: chat turn succeeds, extraction fails separately
    ext_fail_turn = client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"content": "How does gradient descent work? [simulate_extraction_error]"},
    )
    assert ext_fail_turn.status_code == 202
    ext_turn_id = ext_fail_turn.json()["turn_id"]
    assert ext_fail_turn.json()["status"] == "succeeded"

    # Drain retries until job marks failed
    client.post("/api/v1/worker/drain")
    t_status = client.get(f"/api/v1/turns/{ext_turn_id}").json()
    assert t_status["status"] == "succeeded"
    assert t_status["extraction_status"] == "failed"
    assert t_status["extraction_error_code"] == "extraction_provider_failed"


def test_phase2_hybrid_retrieval_eval_and_concept_merge_and_hypotheses(
    tmp_path: Path,
) -> None:
    client = _make_client(tmp_path)

    slug_to_conv_id: dict[str, str] = {}
    for s_conv in SYNTHETIC_CONVERSATIONS:
        c_id = client.post(
            "/api/v1/conversations", json={"title": s_conv.title}
        ).json()["id"]
        slug_to_conv_id[s_conv.slug] = c_id
        for turn in s_conv.turns:
            if turn.role == "user":
                client.post(
                    f"/api/v1/conversations/{c_id}/turns",
                    json={"content": turn.content},
                )
    client.post("/api/v1/worker/drain")

    # Run evaluation cases against hybrid search
    for eval_case in RETRIEVAL_EVAL_CASES:
        s_res = client.get(
            "/api/v1/search",
            params={"q": eval_case.query, "kind": "message_chunk", "limit": 5},
        )
        assert s_res.status_code == 200
        hits = s_res.json()["items"]
        assert len(hits) >= 1
        matched_convs = {h["conversation_id"] for h in hits}
        assert slug_to_conv_id[eval_case.expected_conversation_slug] in matched_convs

    # Test concept merge and hypothesis revision
    graph = client.get("/api/v1/knowledge/graph").json()
    assert len(graph["nodes"]) >= 3
    c1 = graph["nodes"][0]["id"]
    c2 = graph["nodes"][1]["id"]

    # Create a user relation then merge concepts
    rel_res = client.post(
        f"/api/v1/concepts/{c1}/relations",
        json={"target_concept_id": c2, "predicate": "related_to", "explanation": "Testing direct relation"},
    )
    assert rel_res.status_code == 201

    merge_res = client.post(
        f"/api/v1/concepts/{c1}/merge",
        json={"target_concept_id": c2},
    )
    assert merge_res.status_code == 200
    assert graph["nodes"][0]["label"] in merge_res.json()["aliases"]

    # Test hypothesis creation and revision
    first_conv_id = next(iter(slug_to_conv_id.values()))
    first_msg_id = client.get(f"/api/v1/conversations/{first_conv_id}/messages").json()["items"][0]["id"]
    hyp_res = client.post(
        f"/api/v1/messages/{first_msg_id}/hypotheses",
        json={"statement": "Local synaptic rules can approximate credit assignment under feedback alignment."},
    )
    assert hyp_res.status_code == 201
    hyp_id = hyp_res.json()["id"]

    rev_res = client.post(
        f"/api/v1/hypotheses/{hyp_id}/revise",
        json={
            "statement": "Local synaptic rules require auxiliary feedback pathways to scale to deep networks.",
            "message_id": first_msg_id,
        },
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["supersedes_hypothesis_id"] == hyp_id
    old_hyp = client.get(f"/api/v1/hypotheses/{hyp_id}").json()
    assert old_hyp["status"] == "revised"


def test_phase3_export_delete_and_privacy_settings(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    # AI settings & SSRF validation
    ai_res = client.get("/api/v1/settings/ai")
    assert ai_res.status_code == 200
    assert ai_res.json()["remote_transfer_active"] is False

    # Reject non-loopback local endpoint URL (SSRF protection)
    bad_put = client.put(
        "/api/v1/settings/ai",
        json={"local_endpoint_url": "http://169.254.169.254/latest/meta-data"},
    )
    assert bad_put.status_code == 422
    assert bad_put.json()["error"]["code"] == "invalid_local_endpoint"

    val_res = client.post(
        "/api/v1/settings/ai/validate",
        json={"provider": "local_heuristic"},
    )
    assert val_res.status_code == 200
    assert val_res.json()["valid"] is True

    # Connect API key and configure big chat model + small background organizer model via UI endpoint
    key_res = client.put(
        "/api/v1/settings/ai",
        json={
            "conversation_provider": "openai",
            "conversation_model": "gpt-4o",
            "extraction_provider": "openai",
            "extraction_model": "gpt-4o-mini",
            "hosted_data_consent": True,
            "api_keys": {"openai": "sk-test-secret-key-9876"},
        },
    )
    assert key_res.status_code == 200
    key_json_text = key_res.text
    assert "sk-test-secret-key-9876" not in key_json_text
    openai_cap = next(
        p for p in key_res.json()["providers"] if p["provider"] == "openai"
    )
    assert openai_cap["has_configured_secret"] is True
    assert openai_cap["masked_secret_hint"] == "sk-••••9876"

    # Reset back to local_heuristic for local turn execution below
    client.put(
        "/api/v1/settings/ai",
        json={
            "conversation_provider": "local_heuristic",
            "extraction_provider": "local_heuristic",
            "hosted_data_consent": False,
        },
    )

    # Create conversation, turn, export, then delete conversation and verify cleanup
    conv_id = client.post(
        "/api/v1/conversations", json={"title": "Export and delete test"}
    ).json()["id"]
    client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"content": "How does backpropagation use the chain rule? #aha"},
    )
    client.post("/api/v1/worker/drain")

    exp_res = client.post("/api/v1/export")
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert exp_data["status"] == "completed"
    assert exp_data["counts"]["conversations"] == 1
    assert exp_data["counts"]["messages"] == 2
    assert Path(exp_data["file_path"]).exists()

    # Delete conversation and verify search documents are removed
    del_res = client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_res.status_code == 204
    search_after = client.get(
        "/api/v1/search", params={"q": "backpropagation", "kind": "message_chunk"}
    ).json()
    assert len(search_after["items"]) == 0


def test_phase3_vector_and_graph_scale_benchmark(tmp_path: Path) -> None:
    """Profile exact cosine search and bounded graph projection on a realistic personal corpus."""
    client = _make_client(tmp_path)
    conv_id = client.post("/api/v1/conversations", json={"title": "Benchmark"}).json()["id"]

    # Seed 25 turns (50 messages + chunks + embeddings + concepts)
    topics = [
        "How does backpropagation use the chain rule in neural networks?",
        "Why does gradient descent converge on convex loss functions?",
        "How does Hebbian learning compare to global backpropagation?",
        "Why does L2 regularization act like a Gaussian Bayesian prior?",
        "How does the attention mechanism route information in a transformer?",
    ]
    for idx in range(15):
        prompt = f"{topics[idx % len(topics)]} (iteration {idx})"
        client.post(f"/api/v1/conversations/{conv_id}/turns", json={"content": prompt})

    client.post("/api/v1/worker/drain")

    t0 = time.perf_counter()
    search_res = client.get("/api/v1/search", params={"q": "chain rule gradient descent hebbian", "limit": 10})
    search_ms = (time.perf_counter() - t0) * 1000.0
    assert search_res.status_code == 200
    assert len(search_res.json()["items"]) >= 3
    assert search_ms < 250.0

    t1 = time.perf_counter()
    graph_res = client.get("/api/v1/knowledge/graph?node_limit=80&edge_limit=120")
    graph_ms = (time.perf_counter() - t1) * 1000.0
    assert graph_res.status_code == 200
    assert graph_ms < 250.0

