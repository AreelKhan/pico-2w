from machine import Pin, PWM
import time

class Servo:
    def __init__(self, pin, freq=50):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(freq)
        self.last_angle = None

    def _angle_to_duty(self, degrees):
        degrees = max(0, min(180, degrees))
        return int(1638 + (degrees / 180) * (8192 - 1638))

    def set_angle(self, degrees):
        # Avoid redundant PWM writes (reduces jitter)
        if degrees != self.last_angle:
            self.pwm.duty_u16(self._angle_to_duty(degrees))
            self.last_angle = degrees


class Clicker:
    """
    Executes a 0/1 binned script with deterministic timing.
    0 -> BASE_ANGLE (finger up)
    1 -> CLICK_ANGLE (finger down)
    """
    def __init__(self, servo, base_angle=70, click_angle=30):
        self.servo = servo
        self.base_angle = base_angle
        self.click_angle = click_angle

        self.script = None
        self.bin_ms = None
        self.idx = 0
        self.running = False
        self.stop_requested = False
        self.t0 = None

        # Start in safe state
        self.servo.set_angle(self.base_angle)

    def load(self, script, bin_ms):
        """
        script: list[int] (0/1)
        bin_ms: int
        """
        self.script = script
        self.bin_ms = bin_ms
        self.idx = 0

    def start(self):
        if self.script is None:
            raise ValueError("No script loaded.")
        self.running = True
        self.stop_requested = False
        self.idx = 0
        self.t0 = time.ticks_ms()

        # Immediately apply bin 0
        self._apply_bin(self.script[0])

    def stop(self):
        # immediate safe stop
        self.stop_requested = True
        self.running = False
        self.servo.set_angle(self.base_angle)

    def is_running(self):
        return self.running

    def _apply_bin(self, val):
        if val == 1:
            self.servo.set_angle(self.click_angle)
        else:
            self.servo.set_angle(self.base_angle)

    def tick(self):
        """
        Call this frequently (e.g., every 1-5ms).
        Advances the script based on time.
        """
        if not self.running:
            return

        if self.stop_requested:
            self.stop()
            return

        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self.t0)

        # Determine which bin we *should* be on
        target_idx = elapsed // self.bin_ms

        # Advance bins if needed
        while self.idx < target_idx:
            self.idx += 1
            if self.idx >= len(self.script):
                # script finished
                self.running = False
                self.servo.set_angle(self.base_angle)
                return
            self._apply_bin(self.script[self.idx])


# -------------------------
# Example usage:
# -------------------------
servo = Servo(16)
clicker = Clicker(servo, base_angle=150, click_angle=180)

# Example: tap at bin 5-6 then hold at bin 20-30
script = [0] * 50
script[5] = 1
script[6] = 0
for i in range(20, 31):
    script[i] = 1


clicker.load(script, bin_ms=50)
clicker.start()

while clicker.is_running():
    clicker.tick()
    time.sleep_ms(1)

print("done")
