from embodied_simops.api import get_catalog
from embodied_simops.integrations.motrixsim import _motrixsim_source


def test_motrixsim_does_not_inherit_docs_license():
    source = _motrixsim_source(version="unverified")
    assert source["license"] == "NOASSERTION"
    assert source["license_status"] == "requires_installed_version_and_asset_review"
    assert source["license_url"] == "https://motphys.com/en/motrixsim"


def test_catalog_preserves_unverified_motrixsim_license():
    simulator = next(item for item in get_catalog()["simulators"] if item["id"] == "motrixsim")
    assert simulator["license"] == "NOASSERTION"
