import toml
import os;

directory = os.path.dirname(__file__)
cfg = toml.load(directory + "\pkg.cfg.toml")
print(cfg)