import asyncio
import math
import threading
import time

import screeninfo
import win32gui
import win32ui
from pyppeteer import launch


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
	def __init__(self, entry_url, driver_count=1):
		self.drivers = []
		self.driver_count = driver_count
		self.form_grid()
		self.url = entry_url
		self.viewed_pages = {}
		self.searching = None

	async def get_drivers(self) -> None:
		self.drivers = await asyncio.gather(*[launch(headless=False) for _ in range(self.driver_count)])

	async def start(self, refresh_time=3):
		self.searching = True

		for driver in self.drivers:
			driver.get(self.url)

		while self.searching:
			for driver in self.drivers:
				self.check_page(driver.current_url)
				driver.refresh()

			time.sleep(refresh_time)

	async def set_driver_position(self, index, driver):
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

	async def quit(self):
		threaded_execution(self.drivers, lambda x: x.quit())

	async 	def check_page(self, url):
		if url not in self.viewed_pages:
			self.viewed_pages[url] = True
			print(f"Page: {url}")


async def main():
	manager = GlastoManager(
		entry_url="https://www.glastonburyfestivals.co.uk/information/tickets/",
		driver_count=4
	)
	await manager.get_drivers()
	manager.form_grid()
	# manager.start(refresh_time=3)
	# manager.quit()

	print("All done!")


if __name__ == '__main__':
	asyncio.run(main())
