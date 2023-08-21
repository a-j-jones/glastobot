import math
import threading
import time

import screeninfo
import win32gui
import win32ui
from selenium.webdriver import Chrome


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
	def __init__(self, driver_count=1):
		self.drivers = []
		threaded_execution(range(driver_count), lambda x: self.drivers.append(Glasto(self)))
		self.form_grid()
		self.viewed_pages = {}
		self.searching = False

	def start(self, url, refresh_time=3):
		self.searching = True
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

	def quit(self):
		threaded_execution(self.drivers, lambda x: x.quit())


class Glasto(Chrome):
	def __init__(self, manager, **kwargs):
		super(Glasto, self).__init__(**kwargs)
		self.url = None
		self.searching = False
		self.manager = manager

	def set_entry_url(self, url):
		self.url = url

	def check_page(self, url):
		if url not in self.manager.viewed_pages:
			self.manager.viewed_pages[url] = True
			self.manager.searching = False

			# Allow other windows to finish loading:
			print(f"Page: {url}")

			# Maximize the window
			self.maximize_window()

			time.sleep(1)
			self.switch_to.window(self.current_window_handle)

			# Pause the execution and ask for input
			input("New page detected! Press Enter to continue...")

			# Resume
			driver_index = self.manager.drivers.index(self)
			self.manager.set_driver_position(driver_index, self)
			self.manager.searching = True

	def auto_run(self, refresh_time=3):
		self.get(self.url)
		self.check_page(self.url)

		while True:
			if self.manager.searching:
				self.refresh()
				time.sleep(refresh_time)
				self.check_page(self.current_url)
			else:
				time.sleep(refresh_time)


if __name__ == '__main__':
	manager = GlastoManager(driver_count=9)
	manager.form_grid()
	manager.start("https://www.glastonburyfestivals.co.uk/information/tickets/")
	manager.quit()
	print("All done!")