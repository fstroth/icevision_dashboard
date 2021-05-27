# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/data.ipynb (unless otherwise specified).

__all__ = ['RecordDataframeParser', 'BboxRecordDataframeParser', 'MaskRecordDataframeParser', 'RecordDataset',
           'DataDescriptorBbox', 'StatsDescriptorBbox', 'ImageStatsDescriptorBbox', 'ClassStatsDescriptorBbox',
           'GalleryStatsDescriptorBbox', 'BboxRecordDataset', 'PrecisionRecallMetricsDescriptorObjectDetection',
           'ObjectDetectionResultsDataset']

# Cell
import datetime
from typing import Union, Optional, List
import os
import shutil
import json
from copy import deepcopy
import random

import numpy as np
import pandas as pd
from PIL import Image
import panel as pn

from icevision.core.record import BaseRecord
from icevision.core.record_defaults import ObjectDetectionRecord, InstanceSegmentationRecord
import icevision.parsers as parsers
from icevision.data.data_splitter import RandomSplitter
from icevision.core.bbox import BBox
from icevision.core.class_map import ClassMap

from fastprogress import master_bar, progress_bar

from .plotting.utils import draw_record_with_bokeh
from .metrics import APObjectDetectionFast, APObjectDetection
from .core.data import *

# Cell
class RecordDataframeParser(parsers.Parser):
    """IceVision parser for pandas datagrames. This parser is mostly used by the RecordDataset to load records from a saved RecordDataset."""
    def __init__(self, record_template):
        super().__init__(record_template)

    def __iter__(self):
        for group in self.record_dataframe.groupby("filepath"):
            yield group[1]

    def __len__(self):
        return self.record_dataframe["filepath"].nunique

    def record_id(self, o):
        return o.iloc[0]["id"]

    def parse_fields(self, o, record, is_new):
        width, height = o.iloc[0]["width"], o.iloc[0]["height"]
        record.set_filepath(o.iloc[0]["filepath"])
        record.set_img_size((width, height))
        record.detection.set_class_map(self.class_map)
        record.detection.add_labels(o["label"])

# Cell
class BboxRecordDataframeParser(RecordDataframeParser):
    """Extends the RecordDataframeParser for object detection"""
    def __init__(self, record_dataframe, class_map):
        super().__init__(ObjectDetectionRecord())
        self.record_dataframe = record_dataframe
        self.class_map = class_map

    def parse_fields(self, o, record, is_new):
        super().parse_fields(o, record, is_new)
        record.detection.add_bboxes([BBox(annot[1]["bbox_xmin"], annot[1]["bbox_ymin"], annot[1]["bbox_xmax"], annot[1]["bbox_ymax"]) for annot in o.iterrows()])

# Cell
class MaskRecordDataframeParser(RecordDataframeParser):
    """Extends the RecordDataframeParser for instance segmentation"""
    def __init__(self, record_dataframe, class_map):
        super().__init__(InstanceSegmentationRecord())
        self.record_dataframe = record_dataframe
        self.class_map = class_map

    def iscrowds(self, o):
        raise NotImplementedError()

    def masks(self, o):
        raise NotImplementedError()

# Cell
class RecordDataset(GenericDataset):
    """Base class dashboard datasets that are based on IceVision records."""
    def __init__(self, records: Union[List[BaseRecord], ObservableList, str], class_map, name=None, description=None):
        if isinstance(records, str):
            self.load_from_file(records)
        else:
            self.records = records if isinstance(records, ObservableList) else ObservableList(records)
            self.class_map = class_map
        super().__init__(self.records, name=name, description=description)
        self.records.register_callback(self.reset_infered_data)

    def __repr__(self):
        base_string = ""
        for col in self.stats_dataset.columns:
            base_string += str(col) + ": " + str(self.stats_dataset[col][0]) + " | "
        base_string = base_string[:-2]
        return base_string

    def __getitem__(self, index):
        return self.records[index]

    def __len__(self):
        return len(self.records)

    def split_in_train_and_val(self, train_fraction):
        records = list(self.records)
        if train_fraction > 1:
            train_fraction /= len(records)
        train, val = records[:int(len(records)*train_fraction)], records[int(len(records)*train_fraction):]
        return train, val

    @property
    def num_images(self):
        return len(self)

    @classmethod
    def load_from_record_dataframe(cls, record_data_df: pd.DataFrame, class_map=None, name=None, description=None):
        records = cls.parse_df_to_records(record_data_df, class_map)
        if class_map is None:
            class_map = cls.create_class_map_from_record_df(record_data_df)
        return cls(records, class_map=class_map, name=name, description=description)

    @staticmethod
    def create_class_map_from_record_df(record_df):
        sorted_labels = record_df["label"].unique()[np.argsort(record_df["label_num"].unique())].tolist()
        sorted_label_nums = sorted(record_df["label_num"].unique())
        label_map = {key: value for key, value in zip(sorted_label_nums, sorted_labels)}
        return ClassMap([label_map[i] if i in label_map.keys() else "unknown_"+str(i) for i in range(max(sorted_label_nums))])

    @staticmethod
    def parse_df_to_records(record_data_df):
        raise NotImplementedError()

    def load_from_file(self, path):
        data = json.load(open(path))
        df = pd.DataFrame(data["data"])
        self.class_map = ClassMap(data["class_map"])
        self._name = data["name"]
        self._description = data["description"]
        records = self.parse_df_to_records(df, self.class_map)
        self.records = ObservableList(records)

    def save(self, save_path):
        if not os.path.isdir(save_path):
            os.makedirs(save_path, exist_ok=True)
        save_name = "dataset" if self.name == "" or self.name is None else self.name
        if not os.path.isfile(os.path.join(save_path, save_name+".json")):
            save_name = save_name+".json"
        else:
            counter = 1
            while True:
                save_name = save_name+"("+str(counter)+").json"
                if os.path.isfile(os.path.join(save_path, save_name)):
                    counter += 1
                else:
                    break

        class_map = self.class_map if self.class_map is not None else self.create_class_map_from_record_df(self.data)
        save_data = {"name": self.name, "description": self.description, "data": self.data.to_dict(), "class_map": class_map._id2class}

        json.dump(save_data, open(os.path.join(save_path, save_name), "w"), default=str)

    def get_image_by_index(self, index, width, height):
        return draw_record_with_bokeh(self[index], class_map=self.class_map, width=None, height=height, return_figure=True)

    @classmethod
    def create_new_from_mask(cls, cls_instance, mask):
        selection = cls_instance.data[mask]
        filepaths = np.unique(selection["filepath"]).tolist()
        new_records = [record for record in cls_instance.records if str(record.filepath) in filepaths]
        return cls(new_records, cls_instance.class_map)

# Cell
class DataDescriptorBbox(DatasetDescriptor):
    """Dashboard dataset for object detection"""
    def calculate_description(self, obj):
        """Aggregates stats from a list of records and returns a pandas dataframe with the aggregated stats. The creation time is not necessarily the real creation time.
        This depends on the OS, for more information see: https://docs.python.org/3/library/os.html#os.stat_result."""
        data = []
        for index,record in enumerate(obj.records):
            record_commons, record_detections = record.as_dict()["common"], record.aggregate_objects()["detection"]
            for label, bbox in zip(record_detections["labels"], record_detections["bboxes"]):
                file_stats = record.filepath.stat()
                bbox_width = bbox["bbox_width"]
                bbox_height = bbox["bbox_height"]
                area = bbox_width*bbox_height
                area_normalized = area / (record.width * record.height)
                bbox_ratio = bbox_width / bbox_height
                data.append(
                    {
                        "id": record_commons["record_id"], "width": record.width, "height": record.height, "label": label, "area_square_root": bbox["bbox_sqrt_area"], "area_square_root_normalized": area_normalized**0.5,
                        "bbox_xmin": bbox["bbox_x"], "bbox_xmax": bbox["bbox_x"]+bbox["bbox_width"], "bbox_ymin": bbox["bbox_y"], "bbox_ymax": bbox["bbox_y"]+bbox["bbox_height"], "area": area,
                        "area_normalized": area_normalized, "bbox_ratio": bbox_ratio, "record_index": index, "bbox_width": bbox_width,
                        "bbox_height": bbox_height, "filepath": str(record.filepath), "creation_date": datetime.datetime.fromtimestamp(file_stats.st_ctime),
                        "modification_date": datetime.datetime.fromtimestamp(file_stats.st_mtime), "num_annotations": len(record_detections["bboxes"])
                    }
                )
        data = pd.DataFrame(data)
        data["label_num"] = data["label"]
        if obj.class_map is not None:
            data["label"] = data["label"].apply(obj.class_map.get_by_id)
        return data

# Cell
class StatsDescriptorBbox(DatasetDescriptor):
    def calculate_description(self, obj):
        stats_dict = {}
        stats_dict["no_imgs"] = [obj.data["filepath"].nunique()]
        stats_dict["no_classes"] = [obj.data["label"].nunique()]
        stats_dict["classes"] = [list(obj.data["label"].unique())]
        stats_dict["area_min"] = [obj.data["area"].min()]
        stats_dict["area_max"] = [obj.data["area"].max()]
        stats_dict["num_annotations_min"] = [obj.data["num_annotations"].min()]
        stats_dict["num_annotations_max"] = [obj.data["num_annotations"].max()]
        stats_dict["name"] = [obj._name]
        stats_dict["description"] = [obj._description]
        return pd.DataFrame(stats_dict)

# Cell
class ImageStatsDescriptorBbox(DatasetDescriptor):
    def calculate_description(self, obj):
        """Creates a dataframe containing stats about the images."""
        stats_dict = {}
        stats_dict["Num. imgs."] = obj.data["filepath"].nunique()
        stats_dict["Min Num. Objects"] = obj.data["num_annotations"].min()
        stats_dict["Max Num. Objects"] = obj.data["num_annotations"].max()
        stats_dict["Avg. Objects/Img"] = round(obj.data["num_annotations"].mean(),2)
        df = pd.DataFrame.from_dict(stats_dict, orient="index").T
        return df

# Cell
class ClassStatsDescriptorBbox(DatasetDescriptor):
    def calculate_description(self, obj):
        """Creates a dataframe containing stats about the object classes."""
        stats_dict = {}
        label_group = obj.data.groupby("label")
        for label, group in label_group:
            label_stats = {}
            label_stats["imgs"] = group["filepath"].nunique()
            label_stats["objects"] = group.shape[0]
            label_stats["avg_objects_per_img"] = label_stats["objects"]/label_stats["imgs"]
            label_stats["frac_of_labels"] = round(label_stats["objects"]/obj.data.shape[0], 2)
            stats_dict[label] = label_stats
        df = pd.DataFrame(stats_dict).T
        df = df.rename_axis('Class').reset_index()
        return df

# Cell
class GalleryStatsDescriptorBbox(DatasetDescriptor):
    def calculate_description(self, obj):
        """Creates a dataframe containing the data for a gallery."""
        df = obj.data[["id", "area", "num_annotations", "label", "bbox_ratio", "bbox_width", "bbox_height", "width", "height"]].drop_duplicates().reset_index(drop=True)
        return df

# Cell
class BboxRecordDataset(RecordDataset):
    data = DataDescriptorBbox()
    gallery_data = GalleryStatsDescriptorBbox()
    stats_dataset = StatsDescriptorBbox()
    stats_image = ImageStatsDescriptorBbox()
    stats_class = ClassStatsDescriptorBbox()
    stats = StatsDescriptorBbox()

    def __init__(self, records: Union[List[BaseRecord], ObservableList, str], class_map=None, name=None, description=None):
        super().__init__(records, class_map, name, description)
        self.record_index_image_id_map = {str(record.filepath): index for index, record in enumerate(self.records)}
        self.data = None
        self.gallery_data = None
        self.stats_dataset = None
        self.stats_image = None
        self.stats_class = None
        self.stats = None

    @staticmethod
    def parse_df_to_records(record_data_df, class_map):
        return BboxRecordDataframeParser(record_data_df, class_map).parse(RandomSplitter([1]))[0]

    def get_image_by_image_id(self, image_id, width, height):
        index = self.record_index_image_id_map[image_id]
        return draw_record_with_bokeh(self[index], display_bbox=True, class_map=self.class_map, width=None, height=height, return_figure=True)

# Cell
class PrecisionRecallMetricsDescriptorObjectDetection(DatasetDescriptor):
    def __init__(self, ious=None):
        if ious is None:
            self.ious = np.arange(0.5, 1, 0.05).round(2)
        else:
            self.ious = ious

    def calculate_description(self, obj):
        return APObjectDetectionFast(obj.base_data, self.ious).metric_data

# Cell
class ObjectDetectionResultsDataset(GenericDataset):
    """Dashboard dataset for the results of and object detection system."""
    metric_data_ap = PrecisionRecallMetricsDescriptorObjectDetection()

    def __init__(self, dataframe, name=None, description=None):
        super().__init__(dataframe, name, description)
        # instanciate metric data and preload it
        self.metric_data_ap = None
        self.class_map = ClassMap(self.base_data[["label", "label_num"]].drop_duplicates().sort_values("label_num")["label"].tolist())

    def save(self, path):
        if not os.path.exists(os.path.join(*path.split("/")[:-1])):
            os.makedirs(os.path.join(*path.split("/")[:-1]))
        self.base_data.to_csv(path)

    def get_image_by_image_id(self, image_id, width=None, height=None):
        """For gallery dashboards"""
        df_pred = self.base_data[(self.base_data["filepath"] == image_id) & (self.base_data["is_prediction"] == True)]
        df_gt = self.base_data[(self.base_data["filepath"] == image_id) & (self.base_data["is_prediction"] == False)]

        parser_pred = BboxRecordDataframeParser(df_pred, self.class_map)
        parser_gt = BboxRecordDataframeParser(df_gt, self.class_map)
        res_gt = parser_gt.parse(show_pbar=False, autofix=False)[1][0]
        res_pred = parser_pred.parse(show_pbar=False, autofix=False)[1]
        if len(res_pred) == 0:
            res_pred = deepcopy(res_gt)
            res_pred["labels"] = []
            res_pred["bboxes"] = []
        else:
            res_pred = res_pred[0]
        plot_gt = draw_record_with_bokeh(res_gt, display_bbox=True, return_figure=True, width=width, height=height)
        plot_pred = draw_record_with_bokeh(res_pred, display_bbox=True, return_figure=True, width=width, height=height)
        return pn.Row(pn.Column(pn.Row("<b>Ground Truth</b>",  align="center"), plot_gt), pn.Column(pn.Row("<b>Prediction</b>",  align="center"), plot_pred))

    @classmethod
    def load(cls, path):
        df = pd.read_csv(path)
        return cls(df, None, None)

    @classmethod
    def init_from_preds_and_samples(cls, predictions, samples_plus_losses, padded_along_shortest=True, class_map=None, name=None, description=None):
        """The input_records are required because they are the only information source with the image stats(width, etc.) for the image on the disk."""
        data = []
        for index, (prediction, sample_plus_loss) in enumerate(zip(predictions, samples_plus_losses)):
            # TODO: At the moment only resize_and_pad or resize are handelt. Check if there are other edge cases that need to be included
            # The correction requires that the sample_plus_loss has the scaled image sizes (not the padded ones or the original ones)
            # correct the width and height to the values of the original image
            img = Image.open(sample_plus_loss["filepath"])
            width = img.size[0]
            height = img.size[1]
            # use bool to int for padded_along_shortest and int(sample_plus_loss["width"] < sample_plus_loss["height"]) to avoid if branches
            factor = max(width, height)/max(sample_plus_loss["width"], sample_plus_loss["height"])
            padding = max(sample_plus_loss["width"], sample_plus_loss["height"]) - min(sample_plus_loss["width"], sample_plus_loss["height"])
            # at the end /2 due to symmetric padding
            correct_x = lambda x: factor * (x - int(padded_along_shortest) * int(sample_plus_loss["width"] < sample_plus_loss["height"]) * padding/2)
            correct_y = lambda y: factor * (y - int(padded_along_shortest) * int(sample_plus_loss["width"] > sample_plus_loss["height"]) * padding/2)
            for label, bbox, score in zip(prediction["labels"], prediction["bboxes"], prediction["scores"]):
                xmin, xmax, ymin, ymax = correct_x(bbox.xmin), correct_x(bbox.xmax), correct_y(bbox.ymin), correct_y(bbox.ymax)
                file_stats = sample_plus_loss["filepath"].stat()
                bbox_width = xmax - xmin
                bbox_height = ymax - ymin
                area = bbox_width * bbox_height
                area_normalized = area / (width * height)
                bbox_ratio = bbox_width / bbox_height
                data.append(
                    {
                        "id": sample_plus_loss["imageid"], "width": width, "height": height, "label": label, "area_square_root": area**2, "area_square_root_normalized": area_normalized**2,
                        "score": score, "bbox_xmin": xmin, "bbox_xmax": xmax, "bbox_ymin": ymin, "bbox_ymax": ymax, "area": area,
                        "area_normalized": area_normalized, "bbox_ratio": bbox_ratio, "record_index": index, "bbox_width": bbox_width,
                        "bbox_height": bbox_height, "filepath": str(sample_plus_loss["filepath"]), "filename": str(sample_plus_loss["filepath"]).split("/")[-1], "creation_date": datetime.datetime.fromtimestamp(file_stats.st_ctime),
                        "modification_date": datetime.datetime.fromtimestamp(file_stats.st_mtime), "num_annotations": len(prediction["bboxes"]), "is_prediction": True,
                        "loss_classifier": sample_plus_loss["loss_classifier"], "loss_box_reg": sample_plus_loss["loss_box_reg"], "loss_objectness": sample_plus_loss["loss_objectness"],
                        "loss_rpn_box_reg": sample_plus_loss["loss_rpn_box_reg"], "loss_total": sample_plus_loss["loss_total"]
                    }
                )
            for label, bbox in zip(sample_plus_loss["labels"], sample_plus_loss["bboxes"]):
                xmin, xmax, ymin, ymax = correct_x(bbox.xmin), correct_x(bbox.xmax), correct_y(bbox.ymin), correct_y(bbox.ymax)
                file_stats = sample_plus_loss["filepath"].stat()
                bbox_width = xmax - xmin
                bbox_height = ymax - ymin
                area = bbox_width * bbox_height
                area_normalized = area / (width * height)
                bbox_ratio = bbox_width / bbox_height
                data.append(
                    {
                        "id": sample_plus_loss["imageid"], "width": width, "height": height, "label": label,
                        "score": 999, "bbox_xmin": xmin, "bbox_xmax": xmax, "bbox_ymin": ymin, "bbox_ymax": ymax, "area": area, "area_square_root": area**2, "area_square_root_normalized": area_normalized**2,
                        "area_normalized": area_normalized, "bbox_ratio": bbox_ratio, "record_index": index, "bbox_width": bbox_width,
                        "bbox_height": bbox_height, "filepath": str(sample_plus_loss["filepath"]), "filename": str(sample_plus_loss["filepath"]).split("/")[-1], "creation_date": datetime.datetime.fromtimestamp(file_stats.st_ctime),
                        "modification_date": datetime.datetime.fromtimestamp(file_stats.st_mtime), "num_annotations": len(prediction["bboxes"]), "is_prediction": False,
                        "loss_classifier": sample_plus_loss["loss_classifier"], "loss_box_reg": sample_plus_loss["loss_box_reg"], "loss_objectness": sample_plus_loss["loss_objectness"],
                        "loss_rpn_box_reg": sample_plus_loss["loss_rpn_box_reg"], "loss_total": sample_plus_loss["loss_total"]
                    }
                )
        data = pd.DataFrame(data)
        data["label_num"] = data["label"]
        if class_map is not None:
            data["label"] = data["label"].apply(class_map.get_id)

        return cls(data, name, description)