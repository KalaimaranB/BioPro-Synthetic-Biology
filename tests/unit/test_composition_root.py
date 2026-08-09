from unittest.mock import patch

# pyrefly: ignore [missing-import]
from analysis.state import SynBioState
from ui.composition_root import ServiceFactory


def test_service_factory_build_all_handles_root_cwd(tmp_path):
    # Mock os.getcwd to return root '/'
    with patch("os.getcwd", return_value="/"):
        factory = ServiceFactory(SynBioState())
        # Should not raise OSError: Read-only file system
        test_cat_path = tmp_path / "catalogue.json"
        factory.build_all(catalogue_path=str(test_cat_path))

        service = factory.get("parts_catalogue")
        assert service is not None
        assert len(service.get_all_parts()) > 0


def test_service_factory_fallback_to_user_dir(tmp_path):
    def mock_expanduser(path):
        if path.startswith("~"):
            return path.replace("~", str(tmp_path), 1)
        return path

    with (
        patch("os.getcwd", return_value="/"),
        patch("os.path.expanduser", side_effect=mock_expanduser),
    ):
        factory = ServiceFactory(SynBioState())
        factory.build_all()

        service = factory.get("parts_catalogue")
        assert service is not None
        assert (tmp_path / ".biopro" / "synthetic_biology" / "catalogue.json").exists()
