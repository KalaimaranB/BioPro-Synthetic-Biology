"""API clients for retrieving biological parts from registries.

Uses Dependency Inversion Principle via the `RegistryClient` protocol.
"""

import contextlib
import xml.etree.ElementTree as ET
from typing import Any, Protocol

import requests
import sbol3

from ..parts.base import BiologicalPart
from ..parts.components import CDS, RBS, Insulator, Promoter, Terminator, sgRNA


class RegistryClient(Protocol):
    """Protocol for all biological part registries."""

    def fetch_part(self, part_id: str) -> BiologicalPart | None:
        """Fetch a part by its identifier.

        Args:
            part_id: The identifier (e.g., 'BBa_R0040').

        Returns:
            A BiologicalPart instance, or None if not found.
        """
        ...


class IGemClient:
    """Client for the iGEM Registry of Standard Biological Parts."""

    BASE_URL = "https://parts.igem.org/cgi/xml/part.cgi?part="

    def fetch_part(self, part_id: str) -> BiologicalPart | None:
        """Fetch and parse an iGEM part from its XML endpoint."""
        url = f"{self.BASE_URL}{part_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 BioPro-Plugin"
            )
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return self._parse_xml(response.text)
        except requests.RequestException:
            return None
        except ET.ParseError:
            return None

    def _parse_xml(self, xml_text: str) -> BiologicalPart | None:  # noqa: C901, PLR0911, PLR0912, PLR0915
        root = ET.fromstring(xml_text)
        part_elem = root.find(".//part_list/part")
        if part_elem is None:
            return None

        part_id = part_elem.findtext("part_name", "")
        short_desc = part_elem.findtext("part_short_desc", "")
        part_type = part_elem.findtext("part_type", "").lower()

        # Try to find the sequence
        sequence = ""
        seq_elem = part_elem.find(".//seq_data")
        if seq_elem is not None and seq_elem.text:
            sequence = seq_elem.text.strip().replace("\n", "")

        kwargs: dict[str, Any] = {
            "id": part_id,
            "name": short_desc,
            "description": part_elem.findtext("part_desc", ""),
            "sequence": sequence,
            "properties": {},
        }

        # Extract parameters (e.g. regulators, direction, etc.)
        for param in part_elem.findall(".//parameters/parameter"):
            p_name = param.findtext("name")
            p_val = param.findtext("value")
            if p_name and p_val:
                kwargs["properties"][p_name] = p_val

        # Fetch and inject rigorous quantitative metrics from the Cello Database
        from .kinetics import CelloKineticsDatabase

        cello_params = CelloKineticsDatabase.get_parameters(part_id).copy()

        # Move metadata into properties to avoid unexpected keyword args
        for meta_key in ["citation", "notes"]:
            if meta_key in cello_params:
                kwargs["properties"][meta_key] = cello_params.pop(meta_key)

        kwargs.update(cello_params)

        # Map iGEM part types to our domain model
        if "promoter" in part_type or "regulatory" in part_type:
            # Attempt to extract known regulator data if not explicitly set
            import re

            ctrl = kwargs["properties"].get("control", "").lower()
            desc = kwargs.get("name", "").lower() + " " + kwargs.get("description", "").lower()
            reps = kwargs.get("repressors", [])

            if ("laci" in ctrl or "laci" in desc) and "LacI" not in reps:
                reps.append("LacI")
            if ("tetr" in ctrl or "tetr" in desc) and "TetR" not in reps:
                reps.append("TetR")

            # Use word boundaries to prevent 'laci' from matching 'ci'
            if (
                re.search(r"\b(lambda|ci)\b", ctrl) or re.search(r"\b(lambda|ci)\b", desc)
            ) and "cI" not in reps:
                reps.append("cI")

            if reps:
                kwargs["repressors"] = reps
            return Promoter(**kwargs)  # type: ignore[arg-type]

        if "coding" in part_type or "cds" in part_type:
            # Attempt to extract product data if not explicitly set
            if "product" not in kwargs:
                protein = kwargs["properties"].get("protein")
                if protein:
                    kwargs["product"] = protein
            return CDS(**kwargs)  # type: ignore[arg-type]

        if "terminator" in part_type:
            # Attempt to extract efficiency (e.g. '0.984[CC]/0.97[JK]')
            if "termination_efficiency" not in kwargs:
                eff = kwargs["properties"].get("forward_efficiency")
                if eff:
                    import re

                    match = re.search(r"([0-9]*\.?[0-9]+)", eff)
                    if match:
                        kwargs["termination_efficiency"] = float(match.group(1))
            return Terminator(**kwargs)

        if "rbs" in part_type or "ribosome" in part_type:
            # Attempt to extract binding strength
            if "translation_initiation_rate" not in kwargs:
                eff = kwargs["properties"].get("efficiency")
                if eff:
                    with contextlib.suppress(ValueError):
                        kwargs["translation_initiation_rate"] = float(eff)
            return RBS(**kwargs)
        if "rna" in part_type or "sgrna" in part_type or "guide" in part_type:
            return sgRNA(**kwargs)  # type: ignore[arg-type]

        if "insulator" in part_type or "ribozyme" in part_type:
            return Insulator(**kwargs)  # type: ignore[arg-type]

        # Fallback to CDS if we don't know, or we could have a GenericPart
        # For now, default to CDS to ensure we return a valid part
        return CDS(**kwargs)


class SynBioHubClient:
    """Client for SynBioHub using pySBOL3."""

    def __init__(self, base_url: str = "https://synbiohub.org/public/igem/"):
        self.base_url = base_url

    def fetch_part(self, part_id: str) -> BiologicalPart | None:  # noqa: PLR0911
        """Fetch an SBOL part and parse it using sbol3."""
        # Note: In a real implementation, you'd query the SynBioHub SPARQL endpoint or
        # download the SBOL XML and parse it.
        # This is a simplified implementation that downloads the SBOL file.
        url = f"{self.base_url}{part_id}/1/sbol"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Create a temporary document and load the SBOL data
            doc = sbol3.Document()
            doc.read_string(
                response.text,
                sbol3.SORTED_NTRIPLES if url.endswith("nt") else sbol3.RDF_XML,
            )

            # Find the component definition
            components = [obj for obj in doc.objects if isinstance(obj, sbol3.Component)]
            if not components:
                return None

            comp = components[0]
            name = comp.name or comp.display_id or part_id
            description = comp.description or ""

            sequence = ""
            if comp.sequences:
                seq_obj = doc.find(comp.sequences[0])
                if isinstance(seq_obj, sbol3.Sequence):
                    sequence = seq_obj.elements or ""

            kwargs = {
                "id": part_id,
                "name": name,
                "description": description,
                "sequence": sequence,
            }

            # Map SO (Sequence Ontology) terms to part types
            roles = comp.roles
            # SO:0000167 is promoter
            if "http://identifiers.org/so/SO:0000167" in roles:
                return Promoter(**kwargs)  # type: ignore[arg-type]
            # SO:0000316 is CDS
            if "http://identifiers.org/so/SO:0000316" in roles:
                return CDS(**kwargs)  # type: ignore[arg-type]
            # SO:0000141 is terminator
            if "http://identifiers.org/so/SO:0000141" in roles:
                return Terminator(**kwargs)  # type: ignore[arg-type]
            # SO:0000139 is RBS
            if "http://identifiers.org/so/SO:0000139" in roles:
                return RBS(**kwargs)  # type: ignore[arg-type]
            return CDS(**kwargs)  # type: ignore[arg-type]

        except (requests.RequestException, sbol3.SBOLError, Exception):
            return None
