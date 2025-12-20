import time
import hydra
from omegaconf import DictConfig, OmegaConf

import sys
from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem

def main(cfg):
    app = QApplication()
    tree = QTreeWidget()
    tree.setColumnCount(2)
    tree.setHeaderLabels(["Name", "Type"])

    items = []
    for key, values in cfg.items():
        item = QTreeWidgetItem([key])
        print(values)
        for k, v in values.items():
            if k[0] == '_':
                continue
            child = QTreeWidgetItem([k, str(v)])
            item.addChild(child)
        items.append(item)

    tree.insertTopLevelItems(0, items)
    tree.show()
    sys.exit(app.exec())

    print(cfg)

@hydra.main(version_base=None, config_path="../conf", config_name="config")
def my_app(cfg : DictConfig) -> None:
    main(cfg)

if __name__ == "__main__":
    my_app()
