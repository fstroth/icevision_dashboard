# IceVisionDashboard



IceVisionDashboard is an extension to the [IceVision](https://github.com/airctic/icevision) object detection framework. This extension provides three things: 
    
- `utils`: Utility functions to create plots and aggregate data.
- `components`: Plots and functions that can be used as components of a dashboard.
- `dashboards`: Dashboards that can be used out of the box the gain insights into datasets and trainings.

# Contributing

If you want to contribute add the following lines to your `pre-commit` file to ensure the notebook cell output don't get pushed into the repo.

```bash
# ensure the oupt of the notebooks is empty
jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace nbs/*.ipynb
git add .
```
