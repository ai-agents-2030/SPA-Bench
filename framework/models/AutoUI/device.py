"""
This file is used to connect to the device and interact with it.
This file was borrowed from https://github.com/LlamaTouch/AgentEnv , with some modifications.
"""

import logging
from typing import List
import time
import uiautomator2 as u2
import subprocess


def get_available_devices():
    """
    Get a list of device serials connected via adb
    :return: list of str, each str is a device serial number
    """
    import subprocess

    r = subprocess.check_output(["adb", "devices"])
    if not isinstance(r, str):
        r = r.decode()
    devices = []
    for line in r.splitlines():
        segs = line.strip().split()
        if len(segs) == 2 and segs[1] == "device":
            devices.append(segs[0])
    return devices


class Device(object):

    def __init__(self, device_serial: str = None) -> None:
        """
        Initialize a device connection with the bare minimum requirements.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        if device_serial is None:
            all_devices = get_available_devices()
            if len(all_devices) == 0:
                raise Exception("No device connected.")
            device_serial = all_devices[0]
            self.logger.info(f"Using device {device_serial}")
        self.serial = device_serial
        self.width, self.height = None, None

    def _activate_uiautomator2(self) -> None:
        try:
            self.logger.info("Initializing uiautomator2...")
            subprocess.check_call(["python", "-m", "uiautomator2", "init", "--serial", self.serial])
            time.sleep(5)

        except subprocess.CalledProcessError as e:
            print("Failed to initialize uiautomator2 with error:", e)


    def connect(self) -> None:
        """
        Connect to the device. Set up the DroidBot app and Minicap.
        """
        self._activate_uiautomator2()
        time.sleep(5)
        self.u2d = u2.connect(self.serial)
        self.logger.info("Connected to device.")

    def disconnect(self) -> None:
        """
        Disconnect from the device.
        """
        self.u2d.stop_uiautomator()
        self.logger.info("Disconnected from device.")

    def get_viewhierachy(self) -> None:
        viewhierachy = self.u2d.dump_hierarchy(
            compressed=False, pretty=False, max_depth=50
        )
        return viewhierachy

    def get_screenshot(self) -> None:
        screenshot = self.u2d.screenshot()
        return screenshot

    def get_screen_size(self) -> tuple[int, int]:
        if self.width is None or self.height is None:
            self.width, self.height = self.u2d.window_size()
        return self.width, self.height

    def get_top_activity_name(self) -> str:
        current = self.u2d.app_current()
        return current["activity"]

    def get_installed_apps(self) -> List[str]:
        return self.u2d.app_list()

    def click(self, x: int, y: int):
        status = self.u2d.click(x, y)
        return status

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration=0.5):
        status = self.u2d.swipe(x1, y1, x2, y2, duration)
        return status

    def is_keyboard_shown(self) -> bool:
        output, exit_code = self.u2d.shell(
            "dumpsys input_method | grep mInputShown", timeout=120
        )  
        # If the output shows mInputShown=true, 
        # it means that the current input method is in the display state, 
        # which usually means that there is an input box focused.
        return "mInputShown=true" in output

    def input_text(self, text: str, smart_enter=True, clear_first=True):
        status = self.u2d.send_keys(
            text, clear=clear_first
        )  # adb broadcasts the input and clears the contents of the input box before typing

        if smart_enter:
            self.u2d.send_action()  
            # Automatically execute enter, 
            # search and other commands according to the needs of the input box, 
            # Added in version 3.1

        return status

    def enter(self):
        status = self.u2d.press("enter")
        return status

    def home(self):
        status = self.u2d.press("home")
        return status

    def back(self):
        status = self.u2d.press("back")
        return status
