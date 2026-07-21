import json
import pytest
from biopro.plugins.synthetic_biology.analysis.catalogue.repository import JsonPartRepository
from biopro.plugins.synthetic_biology.analysis.catalogue.service import PartsCatalogueService
from biopro.plugins.synthetic_biology.analysis.parts.components import Promoter, CDS

def test_json_part_repository_saves_and_retrieves(tmp_path):
    repo_path = tmp_path / "catalogue.json"
    repo = JsonPartRepository(str(repo_path))
    
    promoter = Promoter(id="test_promoter", name="Test Promoter", y_max=10.0)
    repo.save(promoter)
    
    retrieved = repo.get("test_promoter")
    assert retrieved is not None
    assert isinstance(retrieved, Promoter)
    assert retrieved.name == "Test Promoter"
    assert retrieved.y_max == 10.0

def test_json_part_repository_get_all(tmp_path):
    repo_path = tmp_path / "catalogue.json"
    repo = JsonPartRepository(str(repo_path))
    
    repo.save(Promoter(id="p1", name="P1"))
    repo.save(CDS(id="c1", name="C1"))
    
    all_parts = repo.get_all()
    assert len(all_parts) == 2
    ids = {p.id for p in all_parts}
    assert ids == {"p1", "c1"}

def test_service_initializes_cello_parts(tmp_path):
    repo_path = tmp_path / "catalogue.json"
    repo = JsonPartRepository(str(repo_path))
    service = PartsCatalogueService(repo)
    
    service.initialize_cello_parts()
    
    all_parts = service.get_all_parts()
    assert len(all_parts) > 0
    
    # Ensure classic parts (like BBa_R0010) are enriched
    bba = next((p for p in all_parts if p.id == "BBa_R0010"), None)
    assert bba is not None, "BBa_R0010 not found in initialized parts"
    assert "laci regulated" in bba.description.lower(), f"Description not populated for BBa_R0010: {bba.description}"
    assert len(bba.sequence) > 10, "Sequence not populated for BBa_R0010"
    
    # Ensure Cello UCF parts (like pAmtR) are enriched
    pamtr = next((p for p in all_parts if p.id == "pAmtR"), None)
    assert pamtr is not None, "pAmtR not found in initialized parts"
    assert "Cello UCF" in pamtr.description, f"Description not populated for pAmtR: {pamtr.description}"
    assert len(pamtr.sequence) > 10, "Sequence not extracted from UCF for pAmtR"
