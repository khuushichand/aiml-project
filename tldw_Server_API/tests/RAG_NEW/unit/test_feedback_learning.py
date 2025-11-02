from tldw_Server_API.app.core.RAG.rag_service.user_personalization_store import UserPersonalizationStore


class Doc:
    def __init__(self, id, score):
        self.id = id
        self.score = score
        self.content = f"content for {id}"


def test_personalization_boost(tmp_path, monkeypatch):
    # Isolate user DB under tmp
    monkeypatch.chdir(tmp_path)
    store = UserPersonalizationStore("tester")
    # Record implicit click on d2 with impression [d1,d2,d3]
    store.record_event(event_type="click", doc_id="d2", impression=["d1", "d2", "d3"], corpus="demo")
    docs = [Doc("d1", 0.6), Doc("d2", 0.59), Doc("d3", 0.58)]
    boosted = store.boost_documents(docs, corpus="demo")
    # d2 should be ranked first after boost
    assert boosted[0].id == "d2"
