import logging

import chromedriver_autoinstaller

from utils.gui import GlastoGUI
from utils.logs import setup_logger
from utils.utils import kill_chromedriver

chromedriver_autoinstaller.install()
logger = logging.getLogger(__name__)
logger = setup_logger(logger)

# Global constants:
PROXY = None

if __name__ == "__main__":
    logger.debug("Starting GlastoBot")
    kill_chromedriver()
    gui = GlastoGUI(base_url="")
