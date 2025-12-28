from servo import Servo
import time


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

        self._apply_bin(self.script[0])

    def stop(self):
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

        target_idx = elapsed // self.bin_ms

        while self.idx < target_idx:
            self.idx += 1
            if self.idx >= len(self.script):
                # script finished
                self.running = False
                self.servo.set_angle(self.base_angle)
                return
            self._apply_bin(self.script[self.idx])


if __name__ == "__main__":
    SERVO_PIN = 16
    BASE_ANGLE = 150
    CLICK_ANGLE = 180
    BIN_MS = 75

    servo = Servo(SERVO_PIN)
    clicker = Clicker(servo, base_angle=BASE_ANGLE, click_angle=CLICK_ANGLE)

    script = [0] * 100
    script[0] = 1
    script[21] = 1
    script[42] = 1
    script[62:85] = [1] * 23

    clicker.load(script, bin_ms=BIN_MS)
    clicker.start()

    while clicker.is_running():
        clicker.tick()
        time.sleep_ms(1)

    print("done")
