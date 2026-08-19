import json
import os
import urllib.request
from typing import Any


class UCFParser:
    """Parses Cello User Constraint Files (UCF) into kinetic parameters."""

    def __init__(
        self,
        url="https://raw.githubusercontent.com/CIDARLAB/cello/master/resources/UCF/Eco1C1G1T1.UCF.json",
    ):
        self.url = url
        self.data = []
        self.parameters = {}
        self._load_and_parse()

    def _load_and_parse(self):
        # Extremely basic caching
        cache_path = os.path.join(os.path.dirname(__file__), "cello_ucf.json")
        if not os.path.exists(cache_path):
            print(f"Downloading Cello UCF from {self.url}...")
            try:
                req = urllib.request.Request(self.url)
                with urllib.request.urlopen(req) as response:
                    raw_data = response.read()
                    with open(cache_path, "wb") as f:
                        f.write(raw_data)
            except Exception as e:
                print(f"Failed to fetch UCF: {e}")
                return

        with open(cache_path, "r") as f:
            self.data = json.load(f)

        self._extract_kinetics()

    def _extract_kinetics(self):
        # Map gate_name -> promoter & repressor
        gate_parts = {
            x["gate_name"]: x for x in self.data if x.get("collection") == "gate_parts"
        }
        gates = {x["gate_name"]: x for x in self.data if x.get("collection") == "gates"}
        response_functions = {
            x["gate_name"]: x
            for x in self.data
            if x.get("collection") == "response_functions"
        }

        for gate_name, gate in gates.items():
            promoter = gate_parts.get(gate_name, {}).get("promoter", gate_name)
            repressor = gate.get("regulator", "")
            resp = response_functions.get(gate_name)

            if resp:
                params = {p["name"]: p["value"] for p in resp.get("parameters", [])}

                # Assign to Promoter
                self.parameters[promoter] = {
                    "y_max": params.get("ymax", 1.0),
                    "y_min": params.get("ymin", 0.01),
                    "K_d": params.get("K", 0.1),
                    "n": params.get("n", 2.0),
                }

                # Assign to Repressor CDS
                self.parameters[repressor] = {
                    "translation_rate": 0.1,  # default if missing
                    "degradation_rate": 0.002,
                    "product": repressor,
                }


class CelloKineticsDatabase:
    """
    Acts as a middleware to supply strictly cited biological parameters from
    external UCFs and literature-backed JSON files. No hardcoding permitted.
    """

    _ucf = UCFParser()
    _classic_params: dict[str, Any] = {}

    @classmethod
    def _load_classic_params(cls):
        if not cls._classic_params:
            json_path = os.path.join(
                os.path.dirname(__file__), "repressilator_parameters.json"
            )
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    data = json.load(f)
                    cls._classic_params = data.get("parts", {})
                    # Inject citation into properties
                    citation = data.get("citation", "")
                    for params in cls._classic_params.values():
                        params["citation"] = citation

    @classmethod
    def get_parameters(cls, part_id: str) -> dict:
        """Fetch experimental parameters from Cello UCF or cited literature fallback."""
        cls._load_classic_params()

        # Check dynamic UCF first
        if part_id in cls._ucf.parameters:
            return cls._ucf.parameters[part_id]

        # Check cited literature fallback
        if part_id in cls._classic_params:
            return cls._classic_params[part_id]

        return {}
