from pathlib import Path

import pandas as pd


ALLOWED_EXTENSIONS = {".csv", ".xlsx"}

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def save_and_read_file(filename: str, content: bytes):
    """
    Save an uploaded file and read it with Pandas.

    Args:
        filename: Original filename.
        content: Uploaded file content.

    Returns:
        Tuple containing the saved file path and Pandas DataFrame.

    Raises:
        ValueError: If the file format is unsupported or invalid.
    """

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file format. Only CSV and XLSX are allowed.")

    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(content)

    try:
        if extension == ".csv":
            dataframe = pd.read_csv(file_path)
        else:
            dataframe = pd.read_excel(file_path)

    except Exception as error:
        file_path.unlink(missing_ok=True)
        raise ValueError("The uploaded file could not be read.") from error

    if dataframe.empty:
        file_path.unlink(missing_ok=True)
        raise ValueError("The uploaded file is empty.")

    return file_path, dataframe