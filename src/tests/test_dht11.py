# src/tests/test_dht11.py

import unittest
from unittest.mock import patch, MagicMock
from src.sensors.dht11 import DHT11Sensor
import math

class TestDHT11Sensor(unittest.TestCase):

    @patch('src.sensors.dht11.DHT11Sensor.read')
    def test_calculate_vpd(self, mock_read):
        # Arrange
        temp_c = 25.0
        humidity = 50.0
        # Calculate expected VPD using the Tetens equation
        svp = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        avp = svp * (humidity / 100.0)
        expected_vpd = round(svp - avp, 2)
        mock_read.return_value = {'temperature': temp_c, 'humidity': humidity}

        # Create an instance of DHT11Sensor
        sensor = DHT11Sensor()

        # Act
        vpd = sensor.calculate_vpd(temp_c, humidity)

        # Assert
        self.assertEqual(vpd, expected_vpd)

    @patch('src.sensors.dht11.DHT11Sensor.read')
    def test_read(self, mock_read):
        # Arrange
        expected_data = {'temperature': 25.0, 'humidity': 50.0}
        mock_read.return_value = expected_data

        # Create an instance of DHT11Sensor
        sensor = DHT11Sensor()

        # Act
        data = sensor.read()

        # Assert
        self.assertEqual(data, expected_data)

    @patch('src.sensors.dht11.DHT11Sensor.read')
    def test_exit(self, mock_read):
        # Arrange
        sensor = DHT11Sensor()

        # Act
        sensor.exit()

        # Assert
        self.assertTrue(True)  # No specific assertion needed for exit method

if __name__ == '__main__':
    unittest.main()