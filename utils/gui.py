import logging
import threading
import time
import tkinter as tk
from queue import Empty
from typing import Dict, List, Optional

from utils.glasto import GlastoManager
from utils.globals import update_queue
from utils.logs import setup_logger

logger = logging.getLogger(__name__)
logger = setup_logger(logger)


class GlastoGUI(tk.Tk):
    base_count: str = "4"
    base_url: str
    x_pad: int = 10
    y_pad: int = 2

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
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
        self.url_label.grid(
            row=0, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )
        self.url_entry = tk.Entry(self, width=55)
        self.url_entry.grid(
            row=0, column=1, columnspan=3, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )
        self.url_entry.insert(0, self.base_url)

        # Driver count selection (integer only) default 9
        self.driver_count_label = tk.Label(self, text="Driver Count:")
        self.driver_count_label.grid(
            row=1, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )
        self.driver_count_entry = tk.Entry(self)
        self.driver_count_entry.grid(
            row=1, column=1, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )
        self.driver_count_entry.insert(0, self.base_count)

        self.start_button = tk.Button(self, text="Start", command=self.start)
        self.start_button.grid(
            row=0, column=5, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )

    def _create_checkbox_area(self) -> None:
        """Creates area with checkboxes to pause/resume browsing."""
        self.checkbox_label = tk.Label(
            self, text="If checked, the following URLs will pause the browser:"
        )
        self.checkbox_label.grid(
            row=0, column=6, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )

        self.checkbox_canvas = tk.Canvas(self)
        self.checkbox_canvas.grid(row=1, column=6, rowspan=19, sticky="nsew")

        self.scrollbar = tk.Scrollbar(self, command=self.checkbox_canvas.yview)
        self.scrollbar.grid(row=0, column=7, rowspan=20, sticky="ns")

        self.checkbox_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.frame = tk.Frame(self.checkbox_canvas)
        self.checkbox_canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.checkbox_canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event) -> None:
        """Updates the scroll region on configuration changes."""
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))

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
        self.start_button.config(text="Restart all", command=self.manager.resume_all)
        self.pause_button = tk.Button(
            self, text="Pause all", command=self.manager.pause_all
        )
        self.pause_button.grid(
            row=1, column=5, padx=self.x_pad, pady=self.y_pad, sticky="W"
        )

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
            label.grid(
                row=driver + 3, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W"
            )
            url_label = tk.Label(self, text="")
            url_label.grid(
                row=driver + 3,
                column=1,
                columnspan=3,
                padx=self.x_pad,
                pady=self.y_pad,
                sticky="W",
            )
            resume_button = tk.Button(
                self,
                text="Resume",
                command=lambda d=driver: self.manager.resume_searching(d),
            )
            resume_button.grid(
                row=driver + 3, column=4, padx=self.x_pad, pady=self.y_pad, sticky="W"
            )
            open_button = tk.Button(
                self, text="Open", command=lambda d=driver: self.manager.set_focus(d)
            )
            open_button.grid(
                row=driver + 3, column=5, padx=self.x_pad, pady=self.y_pad, sticky="W"
            )

            self.driver_info.append(
                {
                    "label": label,
                    "resume_button": resume_button,
                    "open_button": open_button,
                    "url": url_label,  # Renamed this from 'url' to 'url_label' for clarity
                }
            )

        # Dynamic window geometry setup, if required
        self.geometry("")

        # Starting the execution and URL monitoring threads
        self.execution_thread = threading.Thread(
            target=self.start_managers, args=(driver_count, url)
        )
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
