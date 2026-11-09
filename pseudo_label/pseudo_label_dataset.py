"""Read an explicit manifest of paired imagery and accepted pseudo masks."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from torch.utils.data import Dataset


class PseudoLabelDataset(Dataset):
    """Load 4-channel uint8 pseudo masks; pair loading stays with existing code."""

    def __init__(self, manifest: Path, allow_synthetic_smoke: bool = False):
        value = json.loads(Path(manifest).read_text(encoding="utf-8"))
        if value.get("split") != "unlabeled_train" or not value.get("items"):
            raise ValueError("Expected nonempty unlabeled_train manifest")
        if not value.get("training_eligible") and not allow_synthetic_smoke:
            raise ValueError("Pseudo labels are technical smoke output, not eligible for training")
        self.root = Path(manifest).parent
        self.items = value["items"]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        item = self.items[index]
        mask = np.load(self.root / item["pseudo_mask"], allow_pickle=False)
        if mask.ndim != 3 or mask.shape[0] != 4 or mask.dtype != np.uint8:
            raise ValueError("Pseudo mask must be uint8 4×H×W")
        if not np.isin(mask, (0, 1, 255)).all():
            raise ValueError("Pseudo mask contains unsupported labels")
        return {"sample_id": item["sample_id"], "pre_image": self.root / item["pre_image"],
                "post_image": self.root / item["post_image"], "pseudo_mask": mask}
