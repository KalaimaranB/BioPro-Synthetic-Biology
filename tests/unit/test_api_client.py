"""Unit tests for the API clients."""

from unittest.mock import patch

from biopro.plugins.synthetic_biology.analysis.api.client import IGemClient
from biopro.plugins.synthetic_biology.analysis.parts.components import Promoter


class TestIGemClient:
    """Tests for the IGemClient."""

    @patch("analysis.api.client.requests.get")
    def test_fetch_part_success(self, mock_get):
        # Mock the requests response
        mock_response = mock_get.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <rsbpml>
          <part_list>
            <part>
              <part_id>187</part_id>
              <part_name>BBa_R0040</part_name>
              <part_short_name>R0040</part_short_name>
              <part_short_desc>TetR repressible promoter</part_short_desc>
              <part_type>Regulatory</part_type>
              <part_desc>TetR repressible promoter</part_desc>
              <seq_data>tccctatcagtgatagagattgacatccctatcagtgatagagatactgagcac</seq_data>
            </part>
          </part_list>
        </rsbpml>
        """

        client = IGemClient()
        part = client.fetch_part("BBa_R0040")

        assert part is not None
        assert isinstance(part, Promoter)
        assert part.id == "BBa_R0040"
        assert part.name == "TetR repressible promoter"
        assert part.sequence == "tccctatcagtgatagagattgacatccctatcagtgatagagatactgagcac"

    @patch("analysis.api.client.requests.get")
    def test_fetch_part_not_found(self, mock_get):
        # Mock a failed response
        import requests

        mock_get.side_effect = requests.RequestException("Not Found")

        client = IGemClient()
        part = client.fetch_part("INVALID_PART")

        assert part is None
