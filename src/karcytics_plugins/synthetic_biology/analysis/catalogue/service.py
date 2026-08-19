import json
import os
import urllib.request

from ..api.kinetics import CelloKineticsDatabase
from ..parts.base import BiologicalPart
from ..parts.components import CDS, Promoter
from .repository import PartRepository


class PartsCatalogueService:
    """Service layer for managing the parts catalogue.

    Adheres to the Dependency Inversion Principle by depending on the
    PartRepository abstraction rather than a concrete implementation.
    """

    def __init__(self, repository: PartRepository):
        self._repository = repository

    def add_part(self, part: BiologicalPart) -> None:
        """Add a new part or update an existing one."""
        self._repository.save(part)

    def get_part(self, part_id: str) -> BiologicalPart | None:
        """Retrieve a part by ID."""
        return self._repository.get(part_id)

    def get_all_parts(self) -> list[BiologicalPart]:
        """Get all parts in the catalogue."""
        return self._repository.get_all()

    def delete_part(self, part_id: str) -> None:
        """Delete a part from the catalogue by ID."""
        self._repository.delete(part_id)

    def remove_part(self, part_id: str) -> None:
        """Remove a part from the catalogue (alias for delete_part)."""
        self.delete_part(part_id)

    def predict_part_parameters(
        self, sequence: str, part_type: str = "promoter", k: int = 3
    ) -> dict:
        """Predict transfer curve parameters for a novel DNA sequence.

        Adheres to DIP and Strategy Pattern:
        - Promoters: Routed to PromoterBiophysicsStrategy (sigma-70 PWM motif scanning
          for -35/-10 boxes + spacer length strain energy mapping to K_d, y_max,
          y_min, n).
          Falls back safely to KNNPredictionStrategy if sequence length is insufficient.
        - Other Parts (CDS, RBS, etc.): Routed to KNNPredictionStrategy.

        Args:
            sequence: The novel DNA sequence string.
            part_type: Part type (e.g. "promoter", "cds").
            k: Number of nearest neighbors to consider if k-NN fallback is triggered.

        Returns:
            Dictionary containing predicted parameter values and prediction metadata.
        """
        from ..prediction.sequence_predictor import SequencePredictor

        all_parts = self._repository.get_all()
        return SequencePredictor.predict(
            query_sequence=sequence,
            candidate_parts=all_parts,
            part_type=part_type,
            k=k,
        )

    def _enrich_part(self, part: BiologicalPart):
        """Fetch description from UniProt and image from RCSB PDB."""
        if not isinstance(part, CDS):
            return

        gene = part.name

        # 1. Fetch description & PDB cross-references
        url = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene}+AND+taxonomy_id:2&format=json&size=1"  # noqa: E501
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.load(response)
                if data.get("results"):
                    res = data["results"][0]
                    # Description
                    funcs = [
                        c for c in res.get("comments", []) if c.get("commentType") == "FUNCTION"
                    ]
                    if funcs and funcs[0].get("texts"):
                        part.description = funcs[0]["texts"][0]["value"]

                    # PDB IDs
                    pdbs = [
                        x["id"]
                        for x in res.get("uniProtKBCrossReferences", [])
                        if x["database"] == "PDB"
                    ]
                    if pdbs:
                        pdb_id = pdbs[0].lower()
                        # 2. Fetch image from RCSB PDB
                        img_url = f"https://cdn.rcsb.org/images/structures/{pdb_id}_assembly-1.jpeg"
                        img_path = os.path.join(
                            os.path.dirname(__file__), "images", f"{part.id}.jpeg"
                        )
                        try:
                            img_req = urllib.request.Request(img_url)
                            with (
                                urllib.request.urlopen(img_req, timeout=3) as img_resp,
                                open(img_path, "wb") as f,
                            ):
                                f.write(img_resp.read())
                            # Store relative path or absolute path.
                            # Relative is better for portability.
                            part.properties["image_path"] = f"images/{part.id}.jpeg"
                        except Exception:
                            pass
        except Exception:
            pass

    def initialize_cello_parts(self) -> None:  # noqa: C901, PLR0912
        """Seed the repository with default Cello gates if it's empty."""
        # Only initialize if empty
        if self._repository.get_all():
            return

        # Trigger loading of Cello parameters
        dummy_id = "AmtR"
        CelloKineticsDatabase.get_parameters(dummy_id)

        # 1. Load sequence data from UCF JSON
        ucf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api", "cello_ucf.json")
        sequences = {}
        if os.path.exists(ucf_path):
            try:
                with open(ucf_path) as f:
                    ucf_data = json.load(f)
                    for item in ucf_data:
                        if item.get("collection") == "parts":
                            sequences[item.get("name")] = item.get("dnasequence", "")
            except Exception:
                pass

        # Fetch UCF data directly to ensure we have all 14 parts
        classic_params = CelloKineticsDatabase._classic_params
        for part_id, params in classic_params.items():
            name = part_id
            desc = params.get("description", f"{part_id} logic gate part (Cello 2.0)")
            seq = params.get("sequence", "")

            # Determine if it's a CDS or Promoter based on params
            part: BiologicalPart
            if "y_max" in params or "y_min" in params:
                part = Promoter(
                    id=part_id,
                    name=name,
                    description=desc,
                    sequence=seq,
                    is_custom=False,
                    y_max=params.get("y_max"),
                    y_min=params.get("y_min"),
                    K_d=params.get("K_d"),
                    n=params.get("n"),
                )
            else:
                part = CDS(
                    id=part_id,
                    name=name,
                    description=desc,
                    sequence=seq,
                    is_custom=False,
                    translation_rate=params.get("translation_rate"),
                    degradation_rate=params.get("degradation_rate"),
                    product=params.get("product", ""),
                )

            if isinstance(part, CDS):
                self._enrich_part(part)

            self._repository.save(part)

        ucf_params = CelloKineticsDatabase._ucf.parameters
        for part_id, params in ucf_params.items():
            if self._repository.get(part_id):
                continue

            name = part_id
            desc = f"{part_id} from Cello UCF"
            seq = sequences.get(part_id, "")

            part: BiologicalPart  # type: ignore[no-redef]
            if "y_max" in params or "y_min" in params:
                part = Promoter(
                    id=part_id,
                    name=name,
                    description=desc,
                    sequence=seq,
                    is_custom=False,
                    y_max=params.get("y_max"),
                    y_min=params.get("y_min"),
                    K_d=params.get("K_d"),
                    n=params.get("n"),
                )
            else:
                part = CDS(
                    id=part_id,
                    name=name,
                    description=desc,
                    sequence=seq,
                    is_custom=False,
                    translation_rate=params.get("translation_rate"),
                    degradation_rate=params.get("degradation_rate"),
                    product=params.get("product", ""),
                )

            if isinstance(part, CDS):
                self._enrich_part(part)

            self._repository.save(part)
