import os
from collections.abc import Sequence

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
LABEL_EXTENSIONS = (".json",)


def get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def get_data_dir() -> str:
    return os.path.join(get_project_root(), "data")


def get_image_dir() -> str:
    return os.path.join(get_data_dir(), "images")


def get_label_dir() -> str:
    return os.path.join(get_data_dir(), "labels")


def get_image_list(dir_path: str, extension: tuple[str, ...] = IMAGE_EXTENSIONS) -> list:
    file_list = [
        os.path.join(dir_path, file)
        for file in os.listdir(dir_path)
        if validate_ext(file, extension)
    ]
    return file_list


def validate_image_ext(image_name: str, extention: tuple[str, ...] = IMAGE_EXTENSIONS) -> bool:
    image_ext = os.path.splitext(image_name)[1]
    if image_ext.lower() in extention:
        return True
    return False


def validate_label_ext(label_name: str, extention: tuple[str, ...] = LABEL_EXTENSIONS) -> bool:
    label_ext = os.path.splitext(label_name)[1]
    if label_ext.lower() in extention:
        return True
    return False


def validate_ext(label_name: str, extention: Sequence[str]) -> bool:
    label_ext = os.path.splitext(label_name)[1]
    if label_ext.lower() in extention:
        return True
    return False


def return_mattching(sorce_list: list, target_list: list) -> list:
    return [item for item in sorce_list if item in target_list]
