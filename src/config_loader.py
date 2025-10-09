import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    """从指定路径加载 YAML 配置文件并返回一个字典"""
    config_path = Path(path)

    # 如果路径不是绝对路径,尝试从项目根目录查找
    if not config_path.is_absolute():
        # 获取当前文件所在目录的父目录(项目根目录)
        root_dir = Path(__file__).parent.parent
        config_path = root_dir / path

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"配置文件为空或格式错误: {path}")

    return config
