import logging
import math
import threading
import time
import json
from typing import List

import screeninfo
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome

from utils.globals import PROXY, update_queue
from utils.logs import setup_logger
from utils.utils import get_display_scaling, threaded_execution

logger = logging.getLogger(__name__)
logger = setup_logger(logger)


class GlastoManager:
    def __init__(self, interface, driver_count: int = 1) -> None:
        """
        Manager class for Glasto. Handles the creation and management of drivers.

        :param interface: The GUI interface to update
        :param driver_count (int): Number of drivers to start
        """
        self.drivers: List[Glasto] = []
        self.threads = []
        self.stop_event = threading.Event()  # Using an event for clean thread termination

        chrome_options = Options()
        if PROXY:
            chrome_options.add_argument(f"--proxy-server={PROXY}")

        logger.debug("Launching drivers")
        threaded_execution(
            range(driver_count),
            lambda x: self.drivers.append(Glasto(self, options=chrome_options)),
            debug_message="Driver launch"
        )
        self.form_grid()
        self.desired_page = {}
        self.interface = interface

    def start(self, url: str, refresh_time: int = 5) -> None:
        """
        Starts the drivers with the specified URL.
        :param url (str): URL to start the drivers with
        :param refresh_time (int): Time to wait between refreshes
        """

        logger.debug("Starting drivers")
        for driver in self.drivers:
            driver.set_entry_url(url)
            t = threading.Thread(target=driver.auto_run, args=(refresh_time,))
            t.start()
            self.threads.append(t)

    def set_driver_position(self, index: int, driver: 'Glasto') -> None:
        """
        Sets the position of the driver window on the screen.

        :param index: The index of the driver in the list
        :param driver: Driver object
        """

        monitor = screeninfo.get_monitors()[0]

        grid_width = math.ceil(math.sqrt(len(self.drivers)))
        grid_height = math.ceil(len(self.drivers) / grid_width)

        scaling = get_display_scaling()
        driver_width = int(monitor.width / grid_width / scaling)
        driver_height = int(monitor.height / grid_height / scaling)

        x = (index % grid_width) * driver_width
        y = (index // grid_width) * driver_height

        driver.set_window_position(x, y)
        driver.set_window_size(driver_width, driver_height)

    def form_grid(self) -> None:
        """Forms a grid of drivers on the screen."""
        threaded_execution(
            enumerate(self.drivers),
            self.set_driver_position
        )

    def resume_all(self) -> None:
        """Resumes all drivers."""
        for driver_index in range(len(self.drivers)):
            self.resume_searching(driver_index)

    def pause_all(self) -> None:
        """Resumes all drivers."""
        for driver_index in range(len(self.drivers)):
            self.pause_searching(driver_index)

    def resume_searching(self, driver_index: int) -> None:
        """Resumes the driver's searching."""
        self.drivers[driver_index].resume()
        update_queue.put((driver_index, f"Driver {driver_index + 1} - searching"))

    def pause_searching(self, driver_index: int) -> None:
        """Pauses the driver's searching."""
        self.drivers[driver_index].pause()
        update_queue.put((driver_index, f"Driver {driver_index + 1} - paused"))

    def set_focus(self, driver_index: int) -> None:
        """Sets the focus to the driver's window."""
        self.drivers[driver_index].pause()
        self.drivers[driver_index].set_focus()

    def check_page(self, driver: 'Glasto') -> None:
        """Checks if the driver has reached the desired page."""
        url = driver.current_url
        driver_index = self.drivers.index(driver)

        if url not in self.desired_page or self.desired_page.get(url):
            self.pause_searching(driver_index)
            self.desired_page[url] = True

    def quit(self) -> None:
        """Quits all drivers."""
        self.stop_event.set()  # Setting the stop event which signals all threads to terminate


class Glasto(Chrome):
    def __init__(self, manager: GlastoManager, **kwargs) -> None:
        """
        Glasto driver class. Inherits from Chrome.
        :param manager:
        :param kwargs:
        """

        logger.debug(f"Initializing driver - {id(self)}")
        super(Glasto, self).__init__(**kwargs)
        self.url = None
        self.searching = False
        self.manager = manager
        logger.debug(f"Driver initialized - {id(self)}")

    def pause(self):
        """Pauses the driver's searching."""
        self.searching = False

    def resume(self):
        """Resumes the driver's searching."""
        self.searching = True

    def set_entry_url(self, url) -> None:
        """Sets the URL to start the driver with."""
        self.url = url

    def set_focus(self) -> None:
        """Sets the focus to the driver's window."""
        self.manager.form_grid()
        self.maximize_window()
        self.switch_to.window(self.current_window_handle)

    def auto_run(self, refresh_time=3) -> None:
        """
        Starts the driver and automatically refreshes the page.
        :param refresh_time:
        """
        self.get(self.url)
        self.manager.check_page(self)
        self.searching = True

        while not self.manager.stop_event.is_set():  # Check for the stop event
            if self.searching:
                self.refresh()
                time.sleep(refresh_time)
                self.manager.check_page(self)
            else:
                time.sleep(refresh_time)

        self.quit()  # Clean up after receiving the stop signal
