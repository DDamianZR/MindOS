"""F2-T1: se puede crear un episodio, añadirle pasos y recuperarlo completo por id y por
node_id citado (knowledge_refs)."""
from fastapi.testclient import TestClient
from mindos_common.ids import new_id

from memory.src import main as memory_main
from memory.src.infrastructure.adapters.in_memory_thinking_graph import InMemoryThinkingGraph


async def test_create_episode_append_steps_and_get_by_id():
    graph = InMemoryThinkingGraph()
    episode_id = new_id()
    correlation_id = new_id()
    node_a = new_id()
    node_b = new_id()

    await graph.create_episode(episode_id, goal="Encontrar el puerto de Traefik",
                                correlation_id=correlation_id, agent="AgentsService")

    plan_step_id = new_id()
    await graph.append_step(
        step_id=plan_step_id, episode_id=episode_id, step_index=0, kind="plan",
        input_text="Meta: encontrar el puerto", output_text="Plan generado",
        knowledge_refs=[node_a],
    )
    execute_step_id = new_id()
    await graph.append_step(
        step_id=execute_step_id, episode_id=episode_id, step_index=1, kind="execute",
        input_text="Buscar en memoria", output_text="Encontrado: puerto 443",
        capability_name="search_knowledge", knowledge_refs=[node_a, node_b],
    )
    review_step_id = new_id()
    await graph.append_step(
        step_id=review_step_id, episode_id=episode_id, step_index=2, kind="review",
        input_text="¿Es correcto?", output_text="Sí", approved=True,
    )

    await graph.close_episode(episode_id, status="completed", final_output="El puerto es 443")

    episode = await graph.get_episode(episode_id)
    assert episode is not None
    assert episode["goal"] == "Encontrar el puerto de Traefik"
    assert episode["status"] == "completed"
    assert episode["final_output"] == "El puerto es 443"
    assert episode["ended_at"] is not None
    assert len(episode["steps"]) == 3
    # Orden cronológico por step_index, no por orden de inserción
    assert [s["kind"] for s in episode["steps"]] == ["plan", "execute", "review"]
    assert episode["steps"][1]["capability_name"] == "search_knowledge"
    assert episode["steps"][2]["approved"] is True


async def test_get_episodes_by_node_and_walk_reasoning():
    graph = InMemoryThinkingGraph()
    episode_id = new_id()
    node_cited = new_id()
    node_unrelated = new_id()

    await graph.create_episode(episode_id, goal="Meta", correlation_id=new_id(), agent="AgentsService")
    await graph.append_step(
        step_id=new_id(), episode_id=episode_id, step_index=0, kind="plan",
        input_text="in", output_text="out", knowledge_refs=[node_cited],
    )

    # Por el nodo citado: se recupera el episodio completo
    by_node = await graph.get_episodes_by_node(node_cited)
    assert len(by_node) == 1
    assert by_node[0]["id"] == episode_id
    assert len(by_node[0]["steps"]) == 1

    # Por un nodo no citado: nada
    assert await graph.get_episodes_by_node(node_unrelated) == []

    # walk_reasoning: vista aplanada de pasos con contexto del episodio
    trace = await graph.walk_reasoning(node_cited)
    assert len(trace) == 1
    assert trace[0]["episode_goal"] == "Meta"
    assert trace[0]["kind"] == "plan"


def test_thinking_router_http_create_append_close_and_get(monkeypatch):
    thinking_graph = InMemoryThinkingGraph()
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", thinking_graph)
    client = TestClient(memory_main.app)

    episode_id = str(new_id())
    correlation_id = str(new_id())
    node_id = str(new_id())

    create = client.post("/api/v1/thinking/episodes", json={
        "episode_id": episode_id, "goal": "Meta HTTP", "correlation_id": correlation_id,
        "agent": "AgentsService",
    })
    assert create.status_code == 201, create.text

    step = client.post(f"/api/v1/thinking/episodes/{episode_id}/steps", json={
        "step_id": str(new_id()), "step_index": 0, "kind": "plan",
        "input": "in", "output": "out", "knowledge_refs": [node_id],
    })
    assert step.status_code == 201, step.text

    close = client.post(f"/api/v1/thinking/episodes/{episode_id}/close", json={
        "status": "completed", "final_output": "listo",
    })
    assert close.status_code == 200, close.text

    get_ep = client.get(f"/api/v1/thinking/episodes/{episode_id}")
    assert get_ep.status_code == 200, get_ep.text
    body = get_ep.json()
    assert body["status"] == "completed"
    assert body["final_output"] == "listo"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["knowledge_refs"] == [node_id]

    by_node = client.get(f"/api/v1/thinking/episodes/by-node/{node_id}")
    assert by_node.status_code == 200
    assert len(by_node.json()["episodes"]) == 1
    assert by_node.json()["episodes"][0]["id"] == episode_id


def test_get_nonexistent_episode_returns_404(monkeypatch):
    monkeypatch.setattr(memory_main, "in_memory_thinking_graph", InMemoryThinkingGraph())
    client = TestClient(memory_main.app)
    resp = client.get(f"/api/v1/thinking/episodes/{new_id()}")
    assert resp.status_code == 404
