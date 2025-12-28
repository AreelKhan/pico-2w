import cv2
import time

DEVICE = 0
WIDTH = 640
HEIGHT = 480
TARGET_FPS = 30

cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)

# Use MJPEG if supported (often much faster than raw formats)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

# Optional: reduce buffering (helps latency)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


print("Actual width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
print("Actual height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print("Actual fps:", cap.get(cv2.CAP_PROP_FPS))
print("Actual fourcc:", cap.get(cv2.CAP_PROP_FOURCC))

if not cap.isOpened():
    raise RuntimeError("Could not open camera")

last_time = time.time()
frame_count = 0
fps = 0

print("Press q to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame read failed")
        continue

    frame_count += 1
    now = time.time()
    if now - last_time >= 1.0:
        fps = frame_count / (now - last_time)
        frame_count = 0
        last_time = now
        print(f"FPS: {fps:.1f}")

    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )

    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
