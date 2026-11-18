"""FastAPI dependency injection utilities for PCS services."""

from backend.services.pcs_data_service import PCSDataService


def get_pcs_service() -> PCSDataService:
    """Dependency injection helper returning the singleton PCSDataService instance."""
    return PCSDataService.get_instance()
