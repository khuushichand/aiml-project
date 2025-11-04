import os
from typing import Any

import httpx

import tldw_Server_API.app.core.http_client as http_client
from tldw_Server_API.app.core.Third_Party import PMC_OAI as pmc_oai


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_pmc_oai_identify(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "pmc.ncbi.nlm.nih.gov")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "pmc.ncbi.nlm.nih.gov"
        assert request.url.path == "/api/oai/v1/mh/"
        assert request.url.params.get("verb") == "Identify"
        xml = (
            b"""
            <OAI-PMH xmlns=\"http://www.openarchives.org/OAI/2.0/\">
              <responseDate>2024-01-01T00:00:00Z</responseDate>
              <request verb=\"Identify\">https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/</request>
              <Identify>
                <repositoryName>PMC OAI</repositoryName>
                <baseURL>https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/</baseURL>
                <protocolVersion>2.0</protocolVersion>
                <earliestDatestamp>2000-01-01</earliestDatestamp>
                <deletedRecord>no</deletedRecord>
                <granularity>YYYY-MM-DD</granularity>
              </Identify>
            </OAI-PMH>
            """
        )
        return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml, request=request)

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    monkeypatch.setattr(http_client, "create_client", fake_create_client)

    info, err = pmc_oai.pmc_oai_identify()
    assert err is None and info is not None
    assert info["repositoryName"] == "PMC OAI"
    assert info["protocolVersion"] == "2.0"


def test_pmc_oai_listsets_with_resumption(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "pmc.ncbi.nlm.nih.gov")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "pmc.ncbi.nlm.nih.gov"
        assert request.url.path == "/api/oai/v1/mh/"
        if request.url.params.get("verb") == "ListSets" and request.url.params.get("resumptionToken") is None:
            xml = (
                b"""
                <OAI-PMH xmlns=\"http://www.openarchives.org/OAI/2.0/\">
                  <ListSets>
                    <set>
                      <setSpec>pmc</setSpec>
                      <setName>PMC</setName>
                    </set>
                    <resumptionToken>RT1</resumptionToken>
                  </ListSets>
                </OAI-PMH>
                """
            )
            return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml, request=request)
        # Second page
        if request.url.params.get("verb") == "ListSets" and request.url.params.get("resumptionToken") == "RT1":
            xml2 = (
                b"""
                <OAI-PMH xmlns=\"http://www.openarchives.org/OAI/2.0/\">
                  <ListSets>
                    <set>
                      <setSpec>pmc-open</setSpec>
                      <setName>PMC Open</setName>
                    </set>
                  </ListSets>
                </OAI-PMH>
                """
            )
            return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml2, request=request)
        return httpx.Response(400, request=request)

    def fake_create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return httpx.Client(transport=_mock_transport(handler))

    monkeypatch.setattr(http_client, "create_client", fake_create_client)

    sets1, token, err = pmc_oai.pmc_oai_list_sets()
    assert err is None and token == "RT1"
    assert sets1 and sets1[0]["setSpec"] == "pmc"
    sets2, token2, err2 = pmc_oai.pmc_oai_list_sets(resumption_token=token)
    assert err2 is None and token2 is None
    assert sets2 and sets2[0]["setSpec"] == "pmc-open"
