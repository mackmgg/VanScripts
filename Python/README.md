# Python
The Python scripts running on a Raspberry Pi in the van.

## battery.py
A script for reading from a Renogy smart battery. I have only tested it with the 200Ah Bluetooth Smart Lithium, but with minor tweaks I'm sure it would work with an RS485 battery as well. Sends the data to Telegraf, which I think have going to InfluxDB for Grafana.

Usage: `python3 battery.py [ADDRESS]`

