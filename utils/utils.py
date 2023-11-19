import os
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

import win32gui
import win32ui

import logging

from utils.logs import setup_logger

logger = logging.getLogger(__name__)
logger = setup_logger(logger)


def kill_chromedriver() -> None:
    """Kill all running chromedriver processes."""
    os.system('taskkill /F /IM chromedriver.exe /T 2>nul')


def get_display_scaling() -> float:
    """Get the display scaling for the current monitor."""
    hdc = win32gui.GetDC(0)
    dpi = win32ui.GetDeviceCaps(hdc, 88)
    win32gui.ReleaseDC(0, hdc)
    return dpi / 96


def threaded_execution(elements: Iterable, function: callable, debug_message="") -> None:
    futures = []
    debug_message = f"{debug_message} - " if debug_message else ""
    with ThreadPoolExecutor(max_workers=12) as executor:
        for element in elements:
            logger.debug(f"{debug_message}Submitted {element} to thread pool.")
            arguments = element if type(element) is tuple else (element,)
            futures.append(executor.submit(function, *arguments))

    for future in futures:
        if future.exception():
            logger.error(f"Error in thread: {future.exception()}")
        else:
            logger.debug(f"{debug_message}Thread finished.")
