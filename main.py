import math
import os
import threading
import time
import tkinter as tk

import screeninfo
import win32gui
import win32ui
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

BASE_COUNT = "4"
BASE_URL = "https://www.glastonburyfestivals.co.uk/information/tickets/"


class GlastoGUI(tk.Tk):
    def __init__(self):
        super(GlastoGUI, self).__init__()

        # GlastoManager object:
        self.manager = None
        self.execution_thread = None
        self.url_thread = None

        # Driver info:
        self.driver_info = []

        # TKinter window setup:
        self.title("GlastoBot")

        self.x_pad = 10
        self.y_pad = 2

        # URL entry:
        self.url_label = tk.Label(self, text="URL:")
        self.url_label.grid(row=0, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.url_entry = tk.Entry(self, width=55)
        self.url_entry.grid(row=0, column=1, columnspan=3, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.url_entry.insert(0, BASE_URL)

        # Driver count selection (integer only) default 9:
        self.driver_count_label = tk.Label(self, text="Driver Count:")
        self.driver_count_label.grid(row=1, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.driver_count_entry = tk.Entry(self)
        self.driver_count_entry.grid(row=1, column=1, padx=self.x_pad, pady=self.y_pad, sticky="W")
        self.driver_count_entry.insert(0, BASE_COUNT)

        self.start_button = tk.Button(self, text="Start", command=self.start)
        self.start_button.grid(row=0, column=5, rowspan=2, padx=self.x_pad, pady=self.y_pad, sticky="W")

        # Window always on top:
        self.wm_attributes("-topmost", 1)

        # URL Checkboxes:
        self.checkbox_label = tk.Label(self, text="If checked, the following URLs will pause the browser:")
        self.checkbox_label.grid(row=0, column=6, padx=self.x_pad, pady=self.y_pad, sticky="W")

        self.checkbox_canvas = tk.Canvas(self)
        self.checkbox_canvas.grid(row=1, column=6, rowspan=19, sticky="nsew")

        self.scrollbar = tk.Scrollbar(self, command=self.checkbox_canvas.yview)
        self.scrollbar.grid(row=0, column=7, rowspan=20, sticky="ns")

        self.checkbox_canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create frame inside canvas to place checkbuttons
        self.frame = tk.Frame(self.checkbox_canvas)
        self.checkbox_canvas.create_window((0, 0), window=self.frame, anchor="nw")

        # Update the scroll region on configuration changes
        def on_configure(event):
            self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox('all'))

        self.checkbox_canvas.bind('<Configure>', on_configure)
        self.checkboxes = []
        self.checkvars = []

        self.geometry("")
        self.mainloop()

    def update_checkboxes(self, data):
        # Get latest value from existing checkboxes and update the data:
        for i, checkbox in enumerate(self.checkboxes):
            data[checkbox.cget("text")] = bool(self.checkvars[i].get())
        self.manager.desired_page = data

        # Clear the frame first
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.checkboxes = []
        self.checkvars = []

        # Now, create and update checkboxes based on input data
        for i, (checkbox_name, checked_value) in enumerate(data.items()):
            var = tk.IntVar(value=1 if checked_value else 0)
            cb = tk.Checkbutton(self.frame, text=checkbox_name, variable=var)
            cb.grid(row=i, column=0, sticky="w")  # Assuming self.x_pad and self.y_pad values can be used here
            self.checkboxes.append(cb)
            self.checkvars.append(var)

    def start_managers(self, driver_count, url):
        self.manager = GlastoManager(interface=self, driver_count=driver_count)
        self.manager.form_grid()
        self.manager.start(url)
        self.manager.quit()

    def monitor_urls(self):
        while True:
            if self.manager:
                # Get current URLs:
                for index, driver in enumerate(self.manager.drivers):
                    try:
                        url = driver.current_url
                    except Exception:
                        url = "None"

                    try:
                        self.driver_info[index]["url"].config(text=url)
                    except Exception as e:
                        print(f"Error updating url for driver {index}: {e}")

                # Get current list of URLs:
                self.update_checkboxes(self.manager.desired_page)

            time.sleep(0.5)

    def start(self):
        driver_count = int(self.driver_count_entry.get())
        entry_url = self.url_entry.get()

        # Start Chromedrivers:
        self.execution_thread = threading.Thread(target=self.start_managers, args=(driver_count, entry_url))
        self.execution_thread.start()

        self.driver_info = []
        for driver in range(driver_count):
            label = tk.Label(self, text=f"Driver {driver + 1} - searching")
            label.grid(row=driver + 3, column=0, padx=self.x_pad, pady=self.y_pad, sticky="W")
            url = tk.Label(self, text="")
            url.grid(row=driver + 3, column=1, columnspan=3, padx=self.x_pad, pady=self.y_pad, sticky="W")
            resume_button = tk.Button(self, text=f"Resume", command=lambda d=driver: self.manager.resume_searching(d))
            resume_button.grid(row=driver + 3, column=4, padx=self.x_pad, pady=self.y_pad, sticky="W")
            open_button = tk.Button(self, text=f"Open", command=lambda d=driver: self.manager.set_focus(d))
            open_button.grid(row=driver + 3, column=5, padx=self.x_pad, pady=self.y_pad, sticky="W")

            self.driver_info.append({
                "label": label,
                "resume_button": resume_button,
                "open_button": open_button,
                "url": url
            })

        self.geometry("")

        self.url_thread = threading.Thread(target=self.monitor_urls)
        self.url_thread.start()

    def destroy(self):
        if self.manager:
            self.manager.quit()

        if self.execution_thread:
            while self.execution_thread.is_alive():
                try:
                    self.execution_thread.join(timeout=1)
                except Exception as e:
                    print(f"Error in thread {self.execution_thread.name}: {e}")

        super(GlastoGUI, self).destroy()


def get_display_scaling():
    hdc = win32gui.GetDC(0)
    dpi = win32ui.GetDeviceCaps(hdc, 88)
    win32gui.ReleaseDC(0, hdc)
    return dpi / 96


def threaded_execution(elements, function):
    threads = []

    # Initialize driver objects in separate threads
    for element in elements:
        if type(element) is tuple:
            arguments = element
        else:
            arguments = (element,)

        t = threading.Thread(target=function, args=arguments)
        t.start()
        threads.append(t)

    # Ensure all threads have completed before proceeding
    for t in threads:
        while t.is_alive():
            try:
                t.join(timeout=1)
            except Exception as e:
                print(f"Error in thread {t.name}: {e}")


class GlastoManager:
    def __init__(self, interface, driver_count=1):
        self.drivers = []
        chrome_options = Options()
        chrome_options.add_argument(f"--proxy-server={PROXY}")
        threaded_execution(range(driver_count), lambda x: self.drivers.append(Glasto(self, options=chrome_options)))
        self.form_grid()
        self.desired_page = {}
        self.interface = interface

    def start(self, url, refresh_time=3):
        threads = []
        for driver in self.drivers:
            driver.set_entry_url(url)
            t = threading.Thread(target=driver.auto_run, args=(refresh_time,))
            t.start()
            threads.append(t)

        for t in threads:
            while t.is_alive():
                try:
                    t.join(timeout=1)
                except Exception as e:
                    print(f"Error in thread {t.name}: {e}")

    def set_driver_position(self, index, driver):
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

    def form_grid(self):
        threaded_execution(
            enumerate(self.drivers),
            self.set_driver_position
        )

    def resume_searching(self, driver_index):
        self.drivers[driver_index].searching = True
        self.interface.driver_info[driver_index]["label"].config(text=f"Driver {driver_index + 1} - searching")

    def pause_searching(self, driver_index):
        self.drivers[driver_index].searching = False
        self.interface.driver_info[driver_index]["label"].config(text=f"Driver {driver_index + 1} - paused")

    def set_focus(self, driver_index):
        self.drivers[driver_index].set_focus()

    def check_page(self, driver):
        url = driver.current_url
        driver_index = self.drivers.index(driver)

        if url not in self.desired_page or self.desired_page.get(url):
            self.pause_searching(driver_index)
            self.desired_page[url] = True

    def quit(self):
        for driver in self.drivers:
            driver.quit_flag = True


class Glasto(Chrome):
    def __init__(self, manager, **kwargs):
        super(Glasto, self).__init__(**kwargs)
        self.url = None
        self.searching = False
        self.manager = manager
        self.quit_flag = False

    def set_entry_url(self, url):
        self.url = url

    def set_focus(self):
        self.manager.form_grid()
        self.maximize_window()
        self.switch_to.window(self.current_window_handle)

    def auto_run(self, refresh_time=3):
        self.get(self.url)
        self.manager.check_page(self)
        self.searching = True

        while True:
            if self.quit_flag:
                self.quit()
                break
            elif self.searching:
                self.refresh()
                time.sleep(refresh_time)
                self.manager.check_page(self)
            else:
                time.sleep(refresh_time)


if __name__ == '__main__':
    os.system('taskkill /F /IM chromedriver.exe /T')
    gui = GlastoGUI()
    print("All done!")
