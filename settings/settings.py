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
    bat_file: str = r"D:\Resonance\dist_2025\control_econoMI.bat"


@dataclass
class StimuliSettings:
    monitor: int = 2
    stimulus_type: str = "руки"
    stimulus_type_curr: int = 0
    stimulus_types: List[str] = field(default_factory=lambda: ["руки", "фигуры", "стрелки"])
    isi_s: float = 1.5
    isi_range_enabled: bool = False
    isi_min_s: float = 1.5
    isi_max_s: float = 3.0
    stimulus_ms: int = 4000
    blank_s: float = 1.0
    blank_range_enabled: bool = False
    blank_min_s: float = 0.5
    blank_max_s: float = 1.0
    blank_ms: int = 500
    background_image: str = r"resources\base images\base_white_barred_lightGrey.png"
    stimulus_background_image: str = r"resources\base images\base_black_barred_lightGrey.png"
    cross_image: str = r"resources\base images\base_cross_white_barred_lightGrey.png"
    welcome_image: str = r"resources\base images\base_welcome_barred_lightGrey.png"
    welcome_ms: int = 2000
    intro_video: str = r"resources\base images\countdownLight__whiteTrigger.mp4"
    final_images_folder: str = r"resources\final_images"
    stimuli_folder: str = r"resources\stimuli\HLJT images"
    hands_stimuli_folder: str = r"resources\stimuli\HLJT images"
    figures_stimuli_folder: str = r"resources\stimuli\MentalRotation images"
    arrows_stimuli_folder: str = r"resources\stimuli\RT"
    response_keys_file: str = r"settings\response_keys.json"
    hands_bundle: str = ""
    figures_bundle: str = ""
    show_figure_response_labels: bool = True
    use_all_stimuli: bool = True
    stimulus_count: int = 1
    extensions: List[str] = field(default_factory=lambda: [".png", ".jpg", ".jpeg", ".bmp"])


@dataclass
class AppSettings:
    app_service_name: str = "econoMI"
    record: RecordSettings = field(default_factory=RecordSettings)
    stimuli: StimuliSettings = field(default_factory=StimuliSettings)
