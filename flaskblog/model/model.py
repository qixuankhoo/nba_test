import pickle
import re
from pathlib import Path

__version__ = "0.1.0"

BASE_DIR = Path(__file__).resolve(strict=True).parent

with open(f"{BASE_DIR}/trained_ffnn.pkl", "rb") as f:
    ffnn = pickle.load(f)

def predict_ffnn(data):
    return ffnn.predict(data)