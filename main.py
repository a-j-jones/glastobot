import logging
import math
import os
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from typing import Dict, Iterable, List, Optional

import screeninfo
import win32gui
import win32ui
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

# Global constants:
PROXY = None

# Global variables:
update_queue = Queue()

# Logging setup:
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('glastobot.log', mode='w')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


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


def threaded_execution_old(elements: Iterable, function: callable, debug_message="") -> None:
    """
    Execute a function in separate threads for each element.

    :param elements (Iterable): List of elements
    :param function (callable): Function to execute in threads
    :param debug_message (str): Optional debug message to print before starting each thread
    """
    threads = []
    debug_message = f"{debug_message} - " if debug_message else ""
    for element in elements:
        logger.debug(f"{debug_message}Starting thread for {element}")
        arguments = element if type(element) is tuple else (element,)
        t = threading.Thread(target=function, args=arguments, daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
        logger.debug(f"Thread {t.name} finished.")


class GlastoGUI(tk.Tk):
    base_count: str = "4"
    base_url: str = "https://www.glastonburyfestivals.co.uk/information/tickets/"
    x_pad: int = 10
    y_pad: int = 2

    def __init__(self) -> None:
        super(GlastoGUI, self).__init__()
        self._setup_attributes()
        self._setup_tkinter_window()
        self._create_controls()
        self.mainloop()

    def _setup_attributes(self) -> None:
        """Initializes class attributes."""
        self.manager: Optional[GlastoManager] = None
        self.execution_thread: Optional[threading.Thread] = None
        self.url_thread: Optional[threading.Thread] = None
        self.event: threading.Event = threading.Event()
        self.driver_info: List[dict] = []
        self.checkboxes = []
        self.checkvars = []

    def _setup_tkinter_window(self) -> None:
        """Configures the main tkinter window."""
        self.title("GlastoBot")
        self.wm_attributes("-topmost", 1)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_controls(self) -> None:
        """Creates and sets up GUI controls."""
        # URL entry and controls
        self._create_url_controls()

        # Checkbox area for URLs
        self._create_checkbox_area()

    def _create_url_controls(self) -> None:
        """Creates URL entry and related controls."""
        self.url_label = tk.Label(self, text="URL:")
        self.url_label.grid(row=0, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.url_entry = tk.Entry(self, width=55)
        self.url_entry.grid(row=0, column=1, columnspan=3, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.url_entry.insert(0, self.base_url)

        # Driver count selection (integer only) default 9
        self.driver_count_label = tk.Label(self, text="Driver Count:")
        self.driver_count_label.grid(row=1, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.driver_count_entry = tk.Entry(self)
        self.driver_count_entry.grid(row=1, column=1, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.driver_count_entry.insert(0, self.base_count)

        self.start_button = tk.Button(self, text="Start", command=self.start)
        self.start_button.grid(row=0, column=5, rowspan=2, padx=self.x_pad, pady=self.y_pad, sticky="W")

    def _create_checkbox_area(self) -> None:
        """Creates area with checkboxes to pause/resume browsing."""
        self.checkbox_label = tk.Label(self, text="If checked, the following URLs will pause the browser:")
        self.checkbox_label.grid(row=0, column=6, padx=self.x_pad, pady=self.y_pad, sticky="W")

        self.checkbox_canvas = tk.Canvas(self)
        self.checkbox_canvas.grid(row=1, column=6, rowspan=19, sticky="nsew")

        self.scrollbar = tk.Scrollbar(self, command=self.checkbox_canvas.yview)
        self.scrollbar.grid(row=0, column=7, rowspan=20, sticky="ns")

        self.checkbox_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.frame = tk.Frame(self.checkbox_canvas)
        self.checkbox_canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.checkbox_canvas.bind('<Configure>', self._on_canvas_configure)

    def _on_canvas_configure(self, event) -> None:
        """Updates the scroll region on configuration changes."""
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox('all'))

    def update_checkboxes(self, data: Dict) -> None:
        """
        Updates checkboxes based on input data.

        :param data (Dict): Dictionary with checkbox names and values
        """
        # Get latest value from existing checkboxes and update the data
        for i, checkbox in enumerate(self.checkboxes):
            data[checkbox.cget("text")] = bool(self.checkvars[i].get())
        self.manager.desired_page = data

        # Clear the frame first
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()
        self.checkvars.clear()

        # Create and update checkboxes
        for i, (checkbox_name, checked_value) in enumerate(data.items()):
            var = tk.IntVar(value=1 if checked_value else 0)
            cb = tk.Checkbutton(self.frame, text=checkbox_name, variable=var)
            cb.grid(row=i, column=0, sticky="w")
            self.checkboxes.append(cb)
            self.checkvars.append(var)

    def start_managers(self, driver_count: int, url: str) -> None:
        """
        Starts the manager with specified driver count and URL.

        :param driver_count (int): Number of drivers to start
        :param url (str): URL to start the drivers with
        """
        logger.debug("Manager started")
        self.manager = GlastoManager(interface=self, driver_count=driver_count)
        self.manager.start(url)
        logger.debug("Manager stopped")

    def monitor_urls(self) -> None:
        """Monitors and updates URLs continuously."""
        logger.debug("URL monitoring started")
        while not self.event.is_set():  # Check for the stop event here
            if self.manager:
                for index, driver in enumerate(self.manager.drivers):
                    try:
                        url = driver.current_url
                    except AttributeError:
                        url = "None"

                    try:
                        self.driver_info[index]["url"].config(text=url)
                    except (KeyError, IndexError) as e:
                        print(f"Error updating url for driver {index}: {e}")

                self.update_checkboxes(self.manager.desired_page)

            time.sleep(1)

        logger.debug("URL monitoring stopped")

    def start(self) -> None:
        """Starts execution and URL monitoring."""
        driver_count = int(self.driver_count_entry.get())
        url = self.url_entry.get()

        # Initialize driver_info list to avoid any previous data
        self.driver_info = []

        for driver in range(driver_count):
            label = tk.Label(self, text=f"Driver {driver + 1} - searching")
            label.grid(row=driver + 3, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
            url_label = tk.Label(self, text="")
            url_label.grid(row=driver + 3, column=1, columnspan=3, padx=self.x_pad, pady=self.y_pad, sticky="W")
            resume_button = tk.Button(self, text=f"Resume", command=lambda d=driver: self.manager.resume_searching(d))
            resume_button.grid(row=driver + 3, column=4, padx=self.x_pad, pady=self.y_pad, sticky="W")
            open_button = tk.Button(self, text=f"Open", command=lambda d=driver: self.manager.set_focus(d))
            open_button.grid(row=driver + 3, column=5, padx=self.x_pad, pady=self.y_pad, sticky="W")

            self.driver_info.append(
                {
                    "label": label,
                    "resume_button": resume_button,
                    "open_button": open_button,
                    "url": url_label  # Renamed this from 'url' to 'url_label' for clarity
                }
            )

        # Dynamic window geometry setup, if required
        self.geometry("")

        # Starting the execution and URL monitoring threads
        self.execution_thread = threading.Thread(target=self.start_managers, args=(driver_count, url))
        self.execution_thread.start()

        self.url_thread = threading.Thread(target=self.monitor_urls, daemon=True)
        self.url_thread.start()

        self.check_for_updates()

    def check_for_updates(self):
        """Checks for updates in the update_queue and updates the GUI accordingly."""
        try:
            while True:  # Process all pending updates
                driver_index, text = update_queue.get_nowait()
                self.driver_info[driver_index]["label"].config(text=text)
        except Empty:
            pass
        self.after(100, self.check_for_updates)  # Check again after 100ms

    def on_closing(self) -> None:
        """Handles the event when the window is closing."""
        # This will set the event flag and signal the threads to stop
        self.event.set()

        if self.manager:
            self.manager.quit()
            self.execution_thread.join()
            logger.debug(f"Thread {self.execution_thread.name} finished.")

        # Give threads a bit of time to gracefully exit
        self.destroy()


class GlastoManager:
    def __init__(self, interface: GlastoGUI, driver_count: int = 1) -> None:
        """
        Manager class for Glasto. Handles the creation and management of drivers.

        :param interface (GlastoGUI): The GUI interface to update
        :param driver_count (int): Number of drivers to start
        """
        self.drivers = []
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

    def start(self, url: str, refresh_time: int = 3) -> None:
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

    def resume_searching(self, driver_index: int) -> None:
        """Resumes the driver's searching."""
        self.drivers[driver_index].searching = True
        update_queue.put((driver_index, f"Driver {driver_index + 1} - searching"))

    def pause_searching(self, driver_index: int) -> None:
        """Pauses the driver's searching."""
        self.drivers[driver_index].searching = False
        update_queue.put((driver_index, f"Driver {driver_index + 1} - paused"))

    def set_focus(self, driver_index: int) -> None:
        """Sets the focus to the driver's window."""
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


if __name__ == '__main__':
    logger.debug("Starting GlastoBot")
    kill_chromedriver()
    gui = GlastoGUI()
