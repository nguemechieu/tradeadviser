"""Train an ML model from the project's feature dataset."""

import sys
from pathlib import Path

from src.quant.ml.training_pipeline import TrainingPipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main():
    """Run the model training pipeline and persist the resulting model."""
    data_path = REPO_ROOT / "data" / "features" / "features.csv"

    pipeline = TrainingPipeline()
    pipeline.train(str(data_path))

    print("Model training complete")


if __name__ == "__main__":
    main()