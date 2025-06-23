import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("antic", pathlib.Path(__file__).resolve().parents[1] / "antic.py")
antic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(antic)

load_hardware_data = antic.load_hardware_data
HARDWARE_DATA_PATH = antic.HARDWARE_DATA_PATH
load_laptop_models_data = antic.load_laptop_models_data
LAPTOP_MODELS_PATH = antic.LAPTOP_MODELS_PATH


def test_load_hardware_data(tmp_path, monkeypatch):
    # use a temporary path for hardware file
    temp_file = tmp_path / 'hardware.json'
    monkeypatch.setattr(antic, 'HARDWARE_DATA_PATH', str(temp_file))
    data = load_hardware_data()
    assert 'ASUS' in data
    assert 'laptop' in data['ASUS']
    assert 'mainboards' in data['ASUS']['laptop']


def test_load_laptop_models_data(tmp_path, monkeypatch):
    temp_dir = tmp_path / 'hardware'
    temp_dir.mkdir()
    temp_file = temp_dir / 'laptop_models.json'
    monkeypatch.setattr(antic, 'LAPTOP_MODELS_PATH', str(temp_file))
    data = load_laptop_models_data()
    assert 'ASUS' in data
    assert 'models' in data['ASUS']
