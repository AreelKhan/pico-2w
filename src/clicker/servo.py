from machine import Pin, PWM


class Servo:
    def __init__(self, pin, freq=50):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(freq)
        self.last_angle = None

    def _angle_to_duty(self, degrees):
        degrees = max(0, min(180, degrees))
        return int(1638 + (degrees / 180) * (8192 - 1638))

    def set_angle(self, degrees):
        if degrees != self.last_angle:
            self.pwm.duty_u16(self._angle_to_duty(degrees))
            self.last_angle = degrees
