import json
import os
import pathlib
import pickle
from typing import List

import numpy as np
import tensorflow as tf
from tensorflow.keras import models
from tensorflow.python.keras.backend import set_session
from tensorflow.python.keras.preprocessing.sequence import pad_sequences

from credsweeper.common.constants import ThresholdPreset
from credsweeper.credentials import Candidate
from credsweeper.credentials.line_data import LineData
from credsweeper.logger.logger import logging
from credsweeper.ml_model import features


class MlValidator:
    @classmethod
    def __init__(cls, threshold_preset: ThresholdPreset = ThresholdPreset.balanced) -> None:
        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)  # To make TF logger quiet
        config = tf.compat.v1.ConfigProto()
        config.gpu_options.allow_growth = True  # dynamically grow the memory used on the GPU
        config.log_device_placement = True  # to log device placement (on which device the operation ran)
        sess = tf.compat.v1.Session(config=config)
        set_session(sess)
        dir_path = os.path.dirname(os.path.realpath(__file__))
        model_file_path = os.path.join(dir_path, "ml_model.h5")
        index_file_path = os.path.join(dir_path, "char_to_index.pkl")
        cls.model = models.load_model(model_file_path)
        with open(index_file_path, "rb") as index_file:
            cls.char_to_index = pickle.load(index_file)

        model_detail_path = f"{pathlib.Path(__file__).parent.absolute()}/model_config.json"
        with open(model_detail_path) as f:
            model_details = json.load(f)
        if "thresholds" in model_details:
            cls.threshold = model_details["thresholds"][threshold_preset.value]
        else:
            cls.threshold = 0.5
        cls.maxlen = model_details.get("max_len", 50)
        cls.common_feature_list = []
        cls.unique_feature_list = []
        logging.info(f'Init ML validator, model file path: {model_file_path} \tindex file path: {index_file_path}')
        logging.debug(f'ML validator details: {model_details}')
        for feature_definition in model_details["features"]:
            feature_class = feature_definition["type"]
            kwargs = feature_definition.get("kwargs", {})
            feature_constructor = getattr(features, feature_class, None)
            if feature_constructor is None:
                raise ValueError(f'Error while parsing model details. Cannot create feature "{feature_class}"')
            try:
                feature = feature_constructor(**kwargs)
            except TypeError:
                raise TypeError(
                    f'Error while parsing model details. Cannot create feature "{feature_class}" with kwargs "{kwargs}"'
                )
            if feature_definition["type"] in ["RuleName"]:
                cls.unique_feature_list.append(feature)
            else:
                cls.common_feature_list.append(feature)

    @classmethod
    def encode(cls, line, char_to_index) -> np.array:
        encoded = []
        for c in line:
            if c in char_to_index:
                encoded.append(char_to_index[c])
            else:
                encoded.append(char_to_index['NON_ASCII'])
        return pad_sequences([encoded], padding='post', maxlen=cls.maxlen)

    @classmethod
    def extract_common_features(cls, candidates: List[Candidate]):
        """Extract features that are guaranteed to be the same for all candidates on the same line with same value"""
        features = np.array([], dtype=float)
        # Extract features from credential candidate
        default_candidate = candidates[0]
        for feature in cls.common_feature_list:
            new_feature = feature([default_candidate])[0]
            if not isinstance(new_feature, np.ndarray):
                new_feature = np.array([new_feature])
            features = np.append(features, new_feature)
        return features

    @classmethod
    def extract_unique_features(cls, candidates: List[Candidate]):
        """Extract features that can by different between candidates. Join them with or operator"""
        features = np.array([], dtype=bool)
        default_candidate = candidates[0]
        for feature in cls.unique_feature_list:
            new_feature = feature([default_candidate])[0]
            if not isinstance(new_feature, np.ndarray):
                new_feature = np.array([new_feature])
            features = np.append(features, new_feature)
        for candidate in candidates[1:]:
            for feature in cls.unique_feature_list:
                new_feature = feature([candidate])[0]
                if not isinstance(new_feature, np.ndarray):
                    new_feature = np.array([new_feature])
                features = features | new_feature
        return features

    @classmethod
    def validate(cls, line_data: LineData, candidate: Candidate) -> bool:
        return cls.validate_group(line_data.value, [candidate])

    @classmethod
    def validate_group(cls, value: str, candidates: List[Candidate]):
        line_input = np.array(cls.encode(value, cls.char_to_index)).reshape(1, -1)

        common_features = cls.extract_common_features(candidates)
        unique_features = cls.extract_unique_features(candidates)
        features = np.hstack([common_features, unique_features])
        features = np.array([features])
        pred = cls.model([line_input, features]).numpy()[0][0]
        is_cred = pred > cls.threshold
        logging.debug(f"ML decision: {is_cred} with prediction: {round(pred, 3)} for value: {value}")
        return is_cred
