# Workshop 3 (ML)

Machine learning on real oceanographic data. Teaches:

- **Classification**: Dolphin detection from acoustic data
- **Regression**: Wind prediction using time-series features
- **Clustering**: Ocean regime identification with unsupervised learning

## What you'll get

By the end of the ML Workshop, you will be able to:

1. Build a dolphin detector with proper evaluation
2. Predict wind conditions using time-series features
3. Identify ocean regimes with unsupervised learning
4. Understand why accuracy can be misleading
5. Know when one feature is enough (the 20 kHz trap)

## Prerequisites

- Basic ML knowledge (train/test split, features, targets)
- Familiarity with Python, pandas, numpy
- Should have completed Workshop 2 (or have equivalent experience)

## Notebooks

| # | Topic | Duration | Content |
|---|-------|----------|---------|
| 01 | ML Orientation | 10 min | Three problem types, real data sources |
| 02 | Classification | 15 min | Dolphin detection intro |
| 03 | Feature Importance | 15 min | The 20 kHz trap |
| 04 | Proper Evaluation | 20 min | Time-based splits |
| 05 | Beyond Accuracy | 15 min | Precision vs recall |
| 06 | Regression | 15 min | Wind prediction |
| 07 | Clustering | 15 min | Ocean regimes |
| 08 | Capstone | 20 min | Combine all techniques |
| 09 | ML Traps | 10 min | Common pitfalls |
| 10 | PyTorch (Bonus) | 10 min | Deep learning intro |

## Data Sources

- **NDBC 46092**: 784 daily wind measurements
- **GLORYS12V1**: 16,188 daily ocean profiles
- **SanctSound MB01**: 12,861 hourly dolphin detections

## Run the workshop

```bash
# Build the notebooks (render, no execution)
make notebook

# Or run with uv
uv run python scripts/build_notebooks.py --execute
```

## Workshop format

This is a **full-day workshop** (6-8 hours) covering:

1. Morning: Classification (dolphin detection)
2. Mid-morning: Feature importance and evaluation
3. Afternoon: Predictive analytics and clustering
4. Late afternoon: Capstone and ML traps

## Tools

- scikit-learn
- pandas
- numpy
- matplotlib
- seaborn
- (Optional) PyTorch, notebook 10 only — `make bonus`

### Notebook 10 needs PyTorch, which is not installed by default

Notebook 10 is a bonus and PyTorch is a ~200 MB download, so it is an opt-in extra rather
than a setup step — nobody should wait through that before starting. The notebook runs
either way and prints which case you are in.

```bash
make bonus              # or: uv sync --extra bonus
```

Notebooks 02 (classification) and 07 (clustering) cover the same ground with
scikit-learn, so skipping this costs you nothing the workshop depends on.

## Key Concepts

- **Classification**: Predict dolphin presence/absence
- **Regression**: Predict tomorrow's wind speed
- **Clustering**: Identify ocean regimes (upwelling, relaxed, transition)
- **Evaluation**: Time-based splits for time-series data
- **Traps**: Data leakage, baseline comparison, feature importance