from machine import Pin
import time
led = Pin(16, Pin.OUT)

led.value(1)
time.sleep(3)
led.value(0)
time.sleep(3)
led.value(1)