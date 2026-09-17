import logging
import math
import time

try:
    import board
except ImportError:
    board = None

try:
    import adafruit_dht
except ImportError:
    adafruit_dht = None

# Map GPIO pin configuration (e.g., GPIO 4 corresponds to board.D4)
PIN_MAPPING = {
    4: getattr(board, "D4", 4) if board is not None else 4,
}


class DHT11Sensor:
    def __init__(
        self, pin_number: int = 4, max_retries: int = 3, retry_delay: float = 2.0
    ):
        """
        Initializes the DHT11 sensor instance on a given GPIO pin.
        """
        self.pin_number = pin_number
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._dht_device = None

        if board is None or adafruit_dht is None:
            logging.warning(
                "DHT11 hardware libraries (board/adafruit_dht) are not installed; sensor reads are disabled. "
                "Install the Raspberry Pi hardware dependencies to enable readings."
            )
            return

        if pin_number not in PIN_MAPPING:
            raise ValueError(f"Pin {pin_number} is not configured in PIN_MAPPING.")

        self.pin = PIN_MAPPING[pin_number]
        self._dht_device = adafruit_dht.DHT11(self.pin)

    @staticmethod
    def calculate_vpd(temp_c: float, humidity: float) -> float:
        """
        Calculates Vapor Pressure Deficit (VPD) in kilopascals (kPa).
        Using Tetens equation for Saturation Vapor Pressure (SVP).
        """
        # Saturation Vapor Pressure (SVP) in kPa
        svp = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        # Actual Vapor Pressure (AVP) in kPa
        avp = svp * (humidity / 100.0)
        # VPD = SVP - AVP
        vpd = svp - avp
        return round(vpd, 2)

    def read(self) -> dict | None:
        """
        Reads temperature and humidity with retry logic for handling transient failures.
        Returns a dictionary with readings or None if all attempts fail.
        """
        if self._dht_device is None:
            logging.warning(
                "DHT11 device is unavailable because the hardware library is missing."
            )
            return None

        for attempt in range(1, self.max_retries + 1):
            try:
                temp_c = self._dht_device.temperature
                humidity = self._dht_device.humidity

                if temp_c is not None and humidity is not None:
                    temp_f = temp_c * (9 / 5) + 32
                    vpd = self.calculate_vpd(float(temp_c), float(humidity))

                    return {
                        "temperature_c": float(temp_c),
                        "temperature_f": round(float(temp_f), 1),
                        "humidity": float(humidity),
                        "vpd_kpa": vpd,
                    }

            except RuntimeError as err:
                # DHT11 sensors frequently throw error messages on minor timing failures
                logging.warning(
                    f"DHT11 read attempt {attempt}/{self.max_retries} failed: {err}"
                )
            except Exception as e:
                logging.error(f"Unexpected error while reading DHT11: {e}")
                break

            time.sleep(self.retry_delay)

        logging.error("Failed to retrieve valid data from DHT11 after maximum retries.")
        return None

    def exit(self):
        """Releases the hardware sensor reference clean-up."""
        if self._dht_device is None:
            return

        try:
            self._dht_device.exit()
        except Exception as e:
            logging.warning(f"Error releasing DHT11 device: {e}")


# Quick testing block when running this script directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing DHT11 Sensor...\n")

    sensor = DHT11Sensor(pin_number=4)
    try:
        data = sensor.read()

        border = "+-----------------+-----------------+"
        header = "| Metric          | Value           |"

        print(border)
        print(header)
        print(border)

        if data:
            temp_f_str = f"{data['temperature_f']}°F"
            humidity_str = f"{data['humidity']}%"
            vpd_str = f"{data['vpd_kpa']} kPa"

            print(f"| Temperature (F) | {temp_f_str:<15} |")
            print(f"| Humidity        | {humidity_str:<15} |")
            print(f"| VPD             | {vpd_str:<15} |")
        else:
            print("| Status          | Read Failed     |")

        print(border)

    finally:
        sensor.exit()
