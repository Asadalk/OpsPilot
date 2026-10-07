from services.rag import build_context, retrieve


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
