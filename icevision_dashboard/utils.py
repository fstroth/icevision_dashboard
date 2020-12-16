# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/utils.ipynb (unless otherwise specified).

__all__ = ['convert_rgb_image_to_bokeh_rgb_image', 'draw_record_with_bokeh', 'aggregate_record_data',
           'draw_class_based_barplot', 'histogram']

# Cell
import numpy as np
from bokeh.plotting import figure
import panel as pn
import pandas as pd

from icevision.visualize.draw_data import draw_record, draw_pred
from icevision.core.class_map import ClassMap

# Cell
def convert_rgb_image_to_bokeh_rgb_image(img: np.ndarray):
    """Convertes a image in the form of a numpy array to an array that can be shown by bokeh."""
    img = np.flipud(img)
    img = img.astype(np.uint8)
    bokeh_img = np.empty((img.shape[0],img.shape[1]), dtype=np.uint32)
    view = bokeh_img.view(dtype=np.uint8).reshape((img.shape[0],img.shape[1], 4))
    view[:,:, 0] = img[:,:,0]
    view[:,:, 1] = img[:,:,1]
    view[:,:, 2] = img[:,:,2]
    view[:,:, 3] = 255
    return bokeh_img

# Cell
def draw_record_with_bokeh(
    record,
    class_map=None,
    display_label=True,
    display_bbox=False,
    display_mask=False,
    display_keypoints=False,
    return_figure=False,
):
    """Draws a record or returns a bokeh figure containing the image."""
    img = draw_record(
            record=record,
            class_map=class_map,
            display_label=display_label,
            display_bbox=display_bbox,
            display_mask=display_mask,
            display_keypoints=display_keypoints,
        )

    # create bokeh figure with the plot
    bokeh_img = convert_rgb_image_to_bokeh_rgb_image(img)

    p = figure(tools="hover, reset, wheel_zoom, box_zoom, save, pan", plot_width=img.shape[1], plot_height=img.shape[0], x_range=(0, img.shape[1]), y_range=(img.shape[0], 0), x_axis_location="above")
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    p.image_rgba([bokeh_img], x=0, y=img.shape[0], dw=img.shape[1], dh=img.shape[0], level="image")
    if return_figure:
        return p
    else:
        show(p)

# Cell
def aggregate_record_data(records):
    """Aggregates stats from a list of records and returns a pandas dataframe with the aggregated stats."""
    data = []
    for record in records:
        for label, bbox in zip(record["labels"], record["bboxes"]):
            area = (bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin)
            area_normalized = area / (record["width"] * record["height"])
            bbox_ratio = (bbox.xmax - bbox.xmin) / (bbox.ymax - bbox.ymin)
            data.append(
                {
                    "id": record["imageid"], "width": record["width"], "height": record["height"], "label": label, "bbox_xmin": bbox.xmin,
                    "bbox_xmax": bbox.xmax, "bbox_ymin": bbox.ymin, "bbox_ymax": bbox.ymax, "area": area, "area_normalized": area_normalized,
                    "bbox_ratio": bbox_ratio
                }
            )
    return data

# Cell
def draw_class_based_barplot(counts, values, class_map=None, bar_type="horizontal", width=500, height=500):
    """Creates a figure with a histogram."""
    if class_map is None:
        values = [str(entry) for entry in values]
    else:
        values = [class_map.get_id(entry) for entry in values]
    p = figure(width=width, height=height, y_range=values)
    if bar_type == "horizontal":
        p.hbar(y=values, left=0, right=counts, height=0.9)
    elif bar_type == "vertical":
        p.vbar(x=values, bottom=0, top=counts, width=0.9)
    else:
        raise ValueError("hist_type has to be of 'horizontal' or 'vertical'")
    return p

# Cell
def histogram(values, bins=10, range=None, density=False, plot_figure=None, width=500, height=500):
    "Creates a histogram"
    if plot_figure is None:
        p = figure(width=width, height=height)
    else:
        p = plot_figure
    counts, edges = np.histogram(values, bins=bins, range=range, density=density)
    p.quad(top=counts, bottom=0, left=edges[:-1], right=edges[1:])
    return p