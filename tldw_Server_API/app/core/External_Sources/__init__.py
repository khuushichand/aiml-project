from .connector_base import BaseConnector
from .connectors_service import get_connector_by_name
from .gmail import GmailConnector
from .google_drive import GoogleDriveConnector
from .notion import NotionConnector
from .onedrive import OneDriveConnector
from .policy import evaluate_policy_constraints, get_default_policy_from_env
from .reference_manager_dedupe import ReferenceItemMatch, build_metadata_fingerprint, rank_reference_item_match
from .sync_adapter import FileSyncAdapter, FileSyncChange, FileSyncWebhookSubscription
from .reference_manager_adapter import ReferenceManagerAdapter
from .reference_manager_types import (
    NormalizedReferenceCollection,
    NormalizedReferenceItem,
    ReferenceAttachmentCandidate,
)
from .zotero import ZoteroConnector

__all__ = [
    "BaseConnector",
    "FileSyncAdapter",
    "FileSyncChange",
    "FileSyncWebhookSubscription",
    "GmailConnector",
    "GoogleDriveConnector",
    "NormalizedReferenceCollection",
    "NormalizedReferenceItem",
    "NotionConnector",
    "OneDriveConnector",
    "ReferenceItemMatch",
    "ReferenceAttachmentCandidate",
    "ReferenceManagerAdapter",
    "ZoteroConnector",
    "build_metadata_fingerprint",
    "get_default_policy_from_env",
    "evaluate_policy_constraints",
    "get_connector_by_name",
    "rank_reference_item_match",
]
