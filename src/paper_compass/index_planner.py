from __future__ import annotations

from dataclasses import dataclass, field

from paper_compass.index_manifest import diff_manifest_v2


@dataclass(frozen=True)
class PaperIndexPlan:
    new: list[str] = field(default_factory=list)
    content_changed: list[str] = field(default_factory=list)
    metadata_only: list[str] = field(default_factory=list)
    path_only: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    missing_in_store: list[str] = field(default_factory=list)
    orphan_in_store: list[str] = field(default_factory=list)
    prune_deleted: bool = False

    @property
    def requires_embedding(self) -> list[str]:
        return sorted(set(self.new) | set(self.content_changed) | set(self.missing_in_store))

    @property
    def process_keys(self) -> list[str]:
        return self.requires_embedding

    @property
    def delete_keys(self) -> list[str]:
        if not self.prune_deleted:
            return []
        return sorted(set(self.deleted) | set(self.orphan_in_store))


def plan_paper_index(
    current_items: dict[str, dict],
    manifest_items: dict[str, dict],
    store_item_keys: set[str],
    *,
    prune_deleted: bool,
) -> PaperIndexPlan:
    diff = diff_manifest_v2(current_items, manifest_items)
    current_keys = set(current_items.keys())
    manifest_keys = set(manifest_items.keys())
    store_keys = {str(key) for key in store_item_keys if key}
    missing_in_store = sorted((current_keys & manifest_keys) - store_keys)
    unchanged = sorted(set(diff["unchanged"]) - set(missing_in_store))
    return PaperIndexPlan(
        new=diff["new"],
        content_changed=diff["content_changed"],
        metadata_only=diff["metadata_only"],
        path_only=diff["path_only"],
        unchanged=unchanged,
        deleted=diff["deleted"],
        missing_in_store=missing_in_store,
        orphan_in_store=sorted(store_keys - current_keys),
        prune_deleted=prune_deleted,
    )
