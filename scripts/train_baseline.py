from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline

from peoplepulse.nlp.labels import LABELS
from peoplepulse.nlp.metrics import benchmark_latency, multilabel_metrics


def load_split(path: Path, split: str):
    df = pd.read_csv(path)
    df = df[df["split"] == split].reset_index(drop=True)
    y = df[list(LABELS)].to_numpy(dtype=int)
    return df["text"].astype(str).tolist(), y


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic/nlp/workplace_messages_v01.csv")
    parser.add_argument("--output", default="artifacts/models/tfidf-logreg")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    data_path = Path(args.data)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    x_train, y_train = load_split(data_path, "train")
    x_test, y_test = load_split(data_path, "test")

    features = FeatureUnion([
        (
            "char",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                min_df=2,
                max_features=30000,
                sublinear_tf=True,
            ),
        ),
        (
            "word",
            TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                min_df=2,
                max_features=15000,
                sublinear_tf=True,
            ),
        ),
    ])
    pipeline = Pipeline([
        ("tfidf", features),
        ("clf", OneVsRestClassifier(LogisticRegression(max_iter=2500, class_weight="balanced"))),
    ])
    pipeline.fit(x_train, y_train)
    probs = pipeline.predict_proba(x_test)
    metrics = multilabel_metrics(y_test, np.asarray(probs), threshold=args.threshold)
    metrics.update(benchmark_latency(lambda text: pipeline.predict_proba([text]), x_test))
    metrics.update({
        "model_name": "tfidf-logreg",
        "model_family": "baseline",
        "dataset": str(data_path),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
    })

    joblib.dump({
        "pipeline": pipeline,
        "labels": list(LABELS),
        "model_name": "tfidf-logreg",
        "model_version": "step3-v1",
    }, out / "model.joblib")
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
