import logging

from utils.gui import GlastoGUI
from utils.logs import setup_logger
from utils.utils import kill_chromedriver

logger = logging.getLogger(__name__)
logger = setup_logger(logger)

# Global constants:
PROXY = None

if __name__ == "__main__":
    logger.debug("Starting GlastoBot")
    kill_chromedriver()
    gui = GlastoGUI(base_url="")
