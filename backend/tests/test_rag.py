from pathlib import Path

from app.rag.ingest import ingest_directory
from app.rag.repository import KnowledgeRepository
from app.services.rag import build_context, retrieve


def test_production_payment_outage_retrieves_incident_guideline():
    results = retrieve("Production payment service is down and customers cannot complete checkout.")
    assert results
    assert "production" in results[0].text.lower()
    assert "incident" in results[0].text.lower()


def test_security_query_retrieves_security_guideline():
    results = retrieve("Credentials were accidentally exposed in a public repository.")
    assert results
    assert "security" in results[0].text.lower()


def test_deployment_query_retrieves_verification_guideline():
    results = retrieve("Deploy the new backend release to production.")
    assert results
    assert "deployment" in results[0].text.lower()
    assert "verification" in results[0].text.lower()


def test_irrelevant_query_does_not_retrieve_guidelines():
    results = retrieve("Schedule a team lunch next Friday.")
    assert results == []


def test_context_contains_source_and_relevance_metadata():
    result = retrieve("Production deployment verification")
    context = build_context(result)
    assert "post-deployment verification" in context
    assert "relevance=" in context


QUESTIONS = [
    ("What should I check when payments latency rises?", "runbooks/payment-latency.md"),
    ("How do I investigate a payment latency spike?", "runbooks/payment-latency.md"),
    ("What evidence correlates database timeouts with latency?", "runbooks/database-timeout.md"),
    ("How should a database timeout be escalated?", "runbooks/database-timeout.md"),
    ("When is a deployment rollback considered?", "runbooks/deployment-rollback.md"),
    ("What must be approved before rollback?", "runbooks/deployment-rollback.md"),
    ("What does degraded service health mean?", "runbooks/service-health.md"),
    ("Why pair health with metrics and logs?", "runbooks/service-health.md"),
    ("What caused the checkout 500 spike?", "postmortems/checkout-configuration-mismatch.md"),
    ("How do I investigate a PAYMENT_GATEWAY_URL mismatch?", "postmortems/checkout-configuration-mismatch.md"),
    ("What was the checkout configuration corrective procedure?", "postmortems/checkout-configuration-mismatch.md"),
    ("What evidence indicates a checkout configuration problem?", "postmortems/checkout-configuration-mismatch.md"),
    ("What caused notification provider failures?", "postmortems/notification-dependency-failure.md"),
    ("How should connection refused notification errors be diagnosed?", "postmortems/notification-dependency-failure.md"),
    ("What evidence identifies the notification dependency?", "postmortems/notification-dependency-failure.md"),
    ("What does the payments database connection pool affect?", "architecture/payments-dependency-boundary.md"),
    ("How should payment trace ids be correlated?", "architecture/payments-dependency-boundary.md"),
    ("Why are database timeout and latency together stronger evidence?", "architecture/payments-dependency-boundary.md"),
    ("What should be recorded for a database timeout?", "runbooks/database-timeout.md"),
    ("What is the safe response to a failed deployment?", "runbooks/deployment-rollback.md"),
]


def test_vector_retrieval_top_k_measurement(database_path):
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    repository = KnowledgeRepository(database_path)
    top_one = 0
    top_three = 0
    for question, expected_source in QUESTIONS:
        results = repository.search(question, top_k=3, mode="semantic")
        sources = [result["source"] for result in results]
        top_one += bool(sources and sources[0] == expected_source)
        top_three += expected_source in sources
    print(f"retrieval_top1={top_one}/{len(QUESTIONS)} retrieval_top3={top_three}/{len(QUESTIONS)}")
    assert top_three == len(QUESTIONS)


HYBRID_QUESTIONS = [
    ("PAY-442", "runbooks/payment-latency.md"),
    ("payments-api v3.8.2", "runbooks/payment-latency.md"),
    ("DB_TIMEOUT", "runbooks/database-timeout.md"),
    ("ECONNRESET", "runbooks/database-timeout.md"),
    ("PAY-451 CONFIG_MISMATCH", "postmortems/checkout-configuration-mismatch.md"),
    ("checkout-api v3.8.2", "postmortems/checkout-configuration-mismatch.md"),
    ("notification provider connection refused", "postmortems/notification-dependency-failure.md"),
    ("payments-api database connection pool", "architecture/payments-dependency-boundary.md"),
    ("what should I check for payment latency", "runbooks/payment-latency.md"),
    ("when should a rollback be considered", "runbooks/deployment-rollback.md"),
    ("what does degraded health mean", "runbooks/service-health.md"),
    ("record trace id for database timeout", "runbooks/database-timeout.md"),
]


def test_retrieval_mode_benchmark(database_path):
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    repository = KnowledgeRepository(database_path)
    hits = {mode: {"top1": 0, "top3": 0} for mode in ("semantic", "keyword", "hybrid")}
    for question, expected_source in HYBRID_QUESTIONS:
        for mode in hits:
            results = repository.search(question, top_k=3, mode=mode)
            sources = [result["source"] for result in results]
            hits[mode]["top1"] += bool(sources and sources[0] == expected_source)
            hits[mode]["top3"] += expected_source in sources
    print(f"retrieval_benchmark={hits}")
    assert hits["hybrid"]["top3"] >= hits["semantic"]["top3"]
    assert hits["hybrid"]["top3"] >= hits["keyword"]["top3"]
