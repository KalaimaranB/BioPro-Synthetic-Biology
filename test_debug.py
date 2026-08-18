import os
from analysis.catalogue.repository import (
    JsonPartRepository,
)
from analysis.catalogue.service import (
    PartsCatalogueService,
)


def test_debug():
    if os.path.exists("debug_cat.json"):
        os.remove("debug_cat.json")
    repo = JsonPartRepository("debug_cat.json")
    service = PartsCatalogueService(repo)
    service.initialize_cello_parts()
    parts = service.get_all_parts()

    bba = [p for p in parts if p.id == "BBa_R0010"]
    if bba:
        print(f"BBa_R0010: Desc={bba[0].description!r}, Seq={bba[0].sequence!r}")
    else:
        print("BBa_R0010 not found!")

    pamtr = [p for p in parts if p.id == "pAmtR"]
    if pamtr:
        print(f"pAmtR: Desc={pamtr[0].description!r}, Seq={pamtr[0].sequence!r}")
    else:
        print("pAmtR not found!")


test_debug()
