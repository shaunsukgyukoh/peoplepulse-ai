from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from peoplepulse.nlp.labels import LABELS, derive_active_labels, normalize_scores


@dataclass(frozen=True)
class Prediction:
    scores: dict[str, float]
    active_labels: tuple[str, ...]
    thresholds: dict[str, float]
    model_name: str
    model_version: str
    device: str


class Predictor(Protocol):
    def predict(self, text: str) -> Prediction: ...


def _default_thresholds(value: float) -> dict[str, float]:
    return {label: float(value) for label in LABELS}


def _load_thresholds(model_dir: Path, fallback: float) -> dict[str, float]:
    path = model_dir / "thresholds.json"
    if not path.exists():
        return _default_thresholds(fallback)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("thresholds", payload)
    missing = [label for label in LABELS if label not in raw]
    if missing:
        raise RuntimeError(f"thresholds.json is missing labels: {missing}")
    thresholds = {label: float(raw[label]) for label in LABELS}
    if any(not 0.0 < value < 1.0 for value in thresholds.values()):
        raise RuntimeError("all runtime thresholds must be between 0 and 1")
    return thresholds


class BaselinePredictor:
    def __init__(self, model_path: str, threshold: float = 0.5) -> None:
        import joblib

        path = Path(model_path)
        bundle = joblib.load(path)
        self.pipeline = bundle["pipeline"]
        self.labels = tuple(bundle["labels"])
        self.thresholds = _load_thresholds(path.parent, threshold)
        self.model_name = str(bundle.get("model_name", "tfidf-logreg"))
        self.model_version = str(bundle.get("model_version", "1"))
        self.device = "cpu"

    def predict(self, text: str) -> Prediction:
        probs = self.pipeline.predict_proba([text])[0]
        scores = normalize_scores(
            {label: float(prob) for label, prob in zip(self.labels, probs, strict=True)}
        )
        return Prediction(
            scores=scores,
            active_labels=derive_active_labels(scores, self.thresholds),
            thresholds=self.thresholds,
            model_name=self.model_name,
            model_version=self.model_version,
            device=self.device,
        )


class TransformerPredictor:
    def __init__(self, model_path: str, threshold: float = 0.5, device: str = "auto") -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = Path(model_path)
        if not path.exists():
            raise RuntimeError(
                f"Transformer checkpoint not found at {model_path}. "
                "Train/promote a STEP 3 model first or mount a selected checkpoint."
            )
        self.torch = torch
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device_obj = torch.device(device)
        self.device = str(self.device_obj)
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self.model.to(self.device_obj)
        self.model.eval()
        self.thresholds = _load_thresholds(path, threshold)
        self.model_name = str(
            getattr(
                self.model.config,
                "peoplepulse_base_model",
                getattr(self.model.config, "_name_or_path", path.name),
            )
        )
        self.model_version = str(getattr(self.model.config, "peoplepulse_model_version", "1"))

    def predict(self, text: str) -> Prediction:
        batch = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
        )
        batch = {key: value.to(self.device_obj) for key, value in batch.items()}
        with self.torch.inference_mode():
            logits = self.model(**batch).logits[0]
            probs = self.torch.sigmoid(logits).detach().cpu().tolist()
        scores = normalize_scores(
            {label: float(prob) for label, prob in zip(LABELS, probs, strict=True)}
        )
        return Prediction(
            scores=scores,
            active_labels=derive_active_labels(scores, self.thresholds),
            thresholds=self.thresholds,
            model_name=self.model_name,
            model_version=self.model_version,
            device=self.device,
        )
