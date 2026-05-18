from dataclasses import dataclass, field
from typing import List


@dataclass
class RecordSettings:
    service_name: str = "nvx136"
    stream_name: str = "eeg"
    records_folder: str = "data"
    subject: str = "S001"
    record_name: str = "record"
    save_hdf: bool = True
    activate_bat: bool = True
    bat_file: str = r"C:\Users\hodor\Documents\lab-MSU\Works\2025.10_TMS\dist_2024_11_13_imp\control_hands.bat"


@dataclass
class StimuliSettings:
    monitor: int = 2
    stimulus_type: str = "руки"
    stimulus_type_curr: int = 0
    stimulus_types: List[str] = field(default_factory=lambda: ["руки", "фигуры"])
    isi_s: float = 1.5
    isi_range_enabled: bool = False
    isi_min_s: float = 1.5
    isi_max_s: float = 3.0
    stimulus_ms: int = 3000
    blank_ms: int = 500
    background_image: str = r"resources\background.png"
    cross_image: str = r"resources\cross_image.png"
    stimuli_folder: str = r"resources\stimuli\HLJT images"
    hands_stimuli_folder: str = r"resources\stimuli\HLJT images"
    figures_stimuli_folder: str = r"resources\stimuli\MentalRotation images"
    extensions: List[str] = field(default_factory=lambda: [".png", ".jpg", ".jpeg", ".bmp"])


@dataclass
class AppSettings:
    app_service_name: str = "econoMI"
    record: RecordSettings = field(default_factory=RecordSettings)
    stimuli: StimuliSettings = field(default_factory=StimuliSettings)
